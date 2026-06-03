"""
proxy/routers/proxy.py

OpenAI-compatible proxy endpoints:

  GET  /v1/models               — model list (Ollama: derived from /api/tags;
                                  OpenAI-compat: proxied or static fallback)
  POST /v1/chat/completions     — chat completion with usage metering

Auth: Authorization: Bearer <key> on all endpoints.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from proxy.auth import authenticate_key
from proxy.backends.base import ChatRequest, UsageData
from proxy.backends.openai_compat import OpenAICompatAdapter
from proxy.db.models import UsageRecord
from proxy.db.session import get_session
from proxy.metering import compute_cost

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_adapter(request: Request):
    """Instantiate the correct backend adapter from app config."""
    config = request.app.state.config
    backend = config.backend
    if backend.type == "openai_compat":
        return OpenAICompatAdapter(
            base_url=backend.base_url,
            api_key=backend.api_key,
        )
    if backend.type == "ollama":
        from proxy.backends.ollama import OllamaAdapter
        return OllamaAdapter(base_url=backend.base_url)
    raise ValueError(f"Unknown backend type: {backend.type!r}")


async def _write_record(
    *,
    api_key_label: str,
    model: str,
    backend_type: str,
    usage: UsageData,
    cost: float,
    status_code: int,
) -> None:
    record = UsageRecord(
        timestamp=datetime.now(timezone.utc),
        api_key_label=api_key_label,
        backend=backend_type,
        model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost=cost,
        token_count_source=usage.source,
        status_code=status_code,
    )
    async with get_session() as session:
        session.add(record)


@router.get("/models")
async def list_models(request: Request) -> Response:
    """Return an OpenAI-shaped model list so OpenWebUI's dropdown populates.

    - Ollama backend: fetches /api/tags and converts each entry to an OpenAI
      model object.
    - OpenAI-compat backend: proxies GET /models to the upstream; falls back
      to a minimal static list if the upstream doesn't support it.
    """
    import json

    config = request.app.state.config

    auth_header = request.headers.get("Authorization")
    api_key = authenticate_key(auth_header, config.api_keys)
    if api_key is None:
        return Response(
            content='{"error":{"message":"Unauthorized","type":"auth_error"}}',
            status_code=401,
            media_type="application/json",
        )

    backend = config.backend
    now = int(time.time())

    if backend.type == "ollama":
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{backend.base_url}/api/tags")
            tags = resp.json()
            models = [
                {
                    "id": m["name"],
                    "object": "model",
                    "created": now,
                    "owned_by": "ollama",
                }
                for m in tags.get("models", [])
            ]
        except Exception as exc:
            logger.warning("Could not fetch Ollama /api/tags: %s", exc)
            models = []
        return Response(
            content=json.dumps({"object": "list", "data": models}),
            media_type="application/json",
        )

    # OpenAI-compat: proxy GET /models upstream
    headers: dict[str, str] = {}
    if backend.api_key:
        headers["Authorization"] = f"Bearer {backend.api_key}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{backend.base_url}/models", headers=headers)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type="application/json",
        )
    except Exception as exc:
        logger.warning("Could not proxy /models to upstream: %s", exc)
        # Minimal fallback so OWUI at least shows something
        return Response(
            content=json.dumps({"object": "list", "data": []}),
            media_type="application/json",
        )


@router.post("/chat/completions")
async def chat_completions(request: Request) -> Response:
    config = request.app.state.config

    # --- Authentication ---
    auth_header = request.headers.get("Authorization")
    api_key = authenticate_key(auth_header, config.api_keys)
    if api_key is None:
        return Response(
            content='{"error":{"message":"Unauthorized","type":"auth_error"}}',
            status_code=401,
            media_type="application/json",
        )

    body: dict[str, Any] = await request.json()
    model: str = body.get("model", "unknown")
    is_stream: bool = bool(body.get("stream", False))

    adapter = _get_adapter(request)
    backend_type = config.backend.type

    if is_stream:
        return await _handle_streaming(
            adapter=adapter,
            body=body,
            model=model,
            api_key_label=api_key.label,
            backend_type=backend_type,
            rates=config.cost_rates,
        )

    # --- Non-streaming ---
    chat_req = ChatRequest(body=body, model=model)
    try:
        chat_resp, usage = await adapter.chat_complete(chat_req)
    except Exception as exc:
        logger.error("Backend error: %s", exc)
        error_usage = UsageData(input_tokens=0, output_tokens=0, source="exact")
        await _write_record(
            api_key_label=api_key.label,
            model=model,
            backend_type=backend_type,
            usage=error_usage,
            cost=0.0,
            status_code=502,
        )
        return Response(
            content='{"error":{"message":"Bad gateway","type":"backend_error"}}',
            status_code=502,
            media_type="application/json",
        )

    cost = compute_cost(model, usage, config.cost_rates)

    await _write_record(
        api_key_label=api_key.label,
        model=model,
        backend_type=backend_type,
        usage=usage,
        cost=cost,
        status_code=chat_resp.status_code,
    )

    import json
    return Response(
        content=json.dumps(chat_resp.body),
        status_code=chat_resp.status_code,
        media_type="application/json",
    )


async def _handle_streaming(
    *,
    adapter,
    body: dict[str, Any],
    model: str,
    api_key_label: str,
    backend_type: str,
    rates,
):
    """Stream SSE chunks to the client; write record after stream completes."""
    chat_req = ChatRequest(body=body, model=model)
    final_usage: UsageData | None = None

    async def generate():
        nonlocal final_usage
        try:
            async for chunk, usage in adapter.chat_complete_stream(chat_req):
                if usage is not None:
                    final_usage = usage
                if chunk:
                    yield chunk
        except Exception as exc:
            logger.error("Streaming backend error: %s", exc)
            yield "data: [DONE]\n\n"
        finally:
            resolved_usage = final_usage or UsageData(
                input_tokens=0, output_tokens=0, source="estimated"
            )
            cost = compute_cost(model, resolved_usage, rates)
            await _write_record(
                api_key_label=api_key_label,
                model=model,
                backend_type=backend_type,
                usage=resolved_usage,
                cost=cost,
                status_code=200,
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
