"""
proxy/routers/proxy.py

OpenAI-compatible proxy endpoints (proxy-key authenticated).

Auth: Authorization: Bearer <proxy-key>  (NOT the JWT session token)

The proxy key identifies the key owner. The system loads and decrypts their
BackendConfig transiently, forwards the request, and records usage.

GET  /v1/models
POST /v1/chat/completions
"""

from __future__ import annotations

import collections
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from proxy.backends.base import ChatRequest, UsageData
from proxy.backends.openai_compat import OpenAICompatAdapter
from proxy.crypto import decrypt_credential
from proxy.db.models import BackendConfig, ProxyKey, UsageRecord
from proxy.db.session import get_session
from proxy.metering import compute_cost

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory rate limiter (sliding window, per proxy key ID)
# ---------------------------------------------------------------------------

# Maps proxy_key_id (str) → deque of request timestamps (float, monotonic)
_rate_windows: dict[str, collections.deque] = collections.defaultdict(
    lambda: collections.deque()
)


def _check_rate_limit(key_id: str, requests_per_minute: int | None) -> bool:
    """Return True if the request is allowed, False if rate limit exceeded."""
    if not requests_per_minute:
        return True
    now = time.monotonic()
    window = _rate_windows[key_id]
    cutoff = now - 60.0
    while window and window[0] < cutoff:
        window.popleft()
    if len(window) >= requests_per_minute:
        return False
    window.append(now)
    return True


# ---------------------------------------------------------------------------
# Proxy-key auth helpers
# ---------------------------------------------------------------------------

def _hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def _extract_bearer(authorization_header: str | None) -> str | None:
    if not authorization_header:
        return None
    parts = authorization_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


async def _get_user_and_backend(
    raw_key: str, session: AsyncSession
) -> tuple[uuid.UUID, ProxyKey, BackendConfig] | None:
    """Lookup key owner and their backend config.

    Returns (user_id, proxy_key, backend_config) or None on any failure.
    """
    key_hash = _hash_key(raw_key)
    result = await session.exec(
        select(ProxyKey).where(
            ProxyKey.key_hash == key_hash,
            ProxyKey.is_active == True,  # noqa: E712
        )
    )
    proxy_key = result.first()
    if proxy_key is None:
        return None

    bc_result = await session.exec(
        select(BackendConfig).where(BackendConfig.user_id == proxy_key.user_id)
    )
    backend_config = bc_result.first()
    if backend_config is None:
        return None  # signals "no backend configured"

    return proxy_key.user_id, proxy_key, backend_config


def _make_adapter(backend_config: BackendConfig, encrypt_key: bytes):
    """Instantiate the correct backend adapter; decrypt credential transiently."""
    api_key: str | None = None
    if backend_config.credential_ciphertext:
        # Decrypted in memory for this request only — not stored, not logged
        api_key = decrypt_credential(backend_config.credential_ciphertext, encrypt_key)

    if backend_config.backend_type == "openai_compat":
        return OpenAICompatAdapter(
            base_url=backend_config.base_url,
            api_key=api_key,
        )
    if backend_config.backend_type == "ollama":
        from proxy.backends.ollama import OllamaAdapter
        return OllamaAdapter(base_url=backend_config.base_url)
    raise ValueError(f"Unknown backend type: {backend_config.backend_type!r}")


def _get_encrypt_key(request: Request) -> bytes:
    import os
    key = os.environ.get("RELAY_ENCRYPT_KEY")
    if not key:
        raise RuntimeError("RELAY_ENCRYPT_KEY not set")
    return key.encode()


# ---------------------------------------------------------------------------
# Usage recording
# ---------------------------------------------------------------------------

def _extract_tokens_per_second(body: dict[str, Any], usage: UsageData, elapsed: float | None) -> float | None:
    """Extract tokens/sec from response body, or calculate from elapsed time."""
    # Open WebUI / some providers return this directly
    tps = body.get("usage", {}).get("response_token/s")
    if tps is not None:
        try:
            return float(tps)
        except (TypeError, ValueError):
            pass
    # Ollama native: eval_duration is in nanoseconds
    eval_ns = body.get("usage", {}).get("eval_duration")
    eval_count = body.get("usage", {}).get("eval_count")
    if eval_ns and eval_count:
        try:
            return float(eval_count) / (float(eval_ns) / 1e9)
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    # Fallback: output tokens / wall-clock elapsed seconds
    if elapsed and elapsed > 0 and usage.output_tokens > 0:
        return usage.output_tokens / elapsed
    return None


async def _write_record(
    *,
    user_id: uuid.UUID,
    proxy_key_id: uuid.UUID,
    proxy_key_label: str | None,
    model: str,
    backend_type: str,
    usage: UsageData,
    cost: float,
    status_code: int,
    tokens_per_second: float | None = None,
) -> None:
    record = UsageRecord(
        user_id=user_id,
        timestamp=datetime.now(timezone.utc),
        proxy_key_id=proxy_key_id,
        proxy_key_label=proxy_key_label or "",
        backend_type=backend_type,
        model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost=cost,
        token_count_source=usage.source,
        status_code=status_code,
        tokens_per_second=tokens_per_second,
    )
    async with get_session() as session:
        session.add(record)


_UNAUTHORIZED = Response(
    content='{"error":{"message":"Unauthorized","type":"auth_error"}}',
    status_code=401,
    media_type="application/json",
)

_NO_BACKEND = Response(
    content='{"error":{"message":"No backend configured","type":"config_error"}}',
    status_code=400,
    media_type="application/json",
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/models")
async def list_models(request: Request) -> Response:
    raw_key = _extract_bearer(request.headers.get("Authorization"))
    if raw_key is None:
        return _UNAUTHORIZED

    encrypt_key = _get_encrypt_key(request)
    now = int(time.time())

    bt: str | None = None
    bu: str | None = None
    bc: str | None = None

    async with get_session() as session:
        kh = _hash_key(raw_key)
        kr = await session.exec(
            select(ProxyKey).where(ProxyKey.key_hash == kh, ProxyKey.is_active == True)  # noqa: E712
        )
        pk = kr.first()
        if pk is None:
            return _UNAUTHORIZED
        if not pk.backend_config_id:
            return _NO_BACKEND
        bcr = await session.exec(
            select(BackendConfig).where(
                BackendConfig.id == pk.backend_config_id,
                BackendConfig.user_id == pk.user_id,
            )
        )
        bco = bcr.first()
        if bco is None:
            return _NO_BACKEND
        bt = bco.backend_type
        bu = bco.base_url
        bc = bco.credential_ciphertext

    api_key = decrypt_credential(bc, encrypt_key) if bc else None

    if bt == "ollama":
        try:
            headers: dict[str, str] = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{bu}/api/tags", headers=headers)
            tags = resp.json()
            models = [
                {"id": m["name"], "object": "model", "created": now, "owned_by": "ollama"}
                for m in tags.get("models", [])
            ]
        except Exception as exc:
            logger.warning("Could not fetch Ollama /api/tags: %s", exc)
            models = []
        return Response(
            content=json.dumps({"object": "list", "data": models}),
            media_type="application/json",
        )

    # openai_compat — proxy GET /models upstream
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{bu}/models", headers=headers)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type="application/json",
        )
    except Exception as exc:
        logger.warning("Could not proxy /models to upstream: %s", exc)
        return Response(
            content=json.dumps({"object": "list", "data": []}),
            media_type="application/json",
        )


@router.post("/chat/completions")
async def chat_completions(request: Request) -> Response:
    raw_key = _extract_bearer(request.headers.get("Authorization"))
    if raw_key is None:
        return _UNAUTHORIZED

    # Validate key and load backend atomically; capture needed data before session closes
    proxy_key_user_id: uuid.UUID | None = None
    proxy_key_id_val: uuid.UUID | None = None
    proxy_key_label_val: str | None = None
    backend_type_val: str | None = None
    backend_base_url: str | None = None
    backend_ciphertext: str | None = None

    async with get_session() as session:
        kh = _hash_key(raw_key)
        kr = await session.exec(
            select(ProxyKey).where(ProxyKey.key_hash == kh, ProxyKey.is_active == True)  # noqa: E712
        )
        proxy_key = kr.first()
        if proxy_key is None:
            return _UNAUTHORIZED

        # Rate limit check (before any backend work)
        if not _check_rate_limit(str(proxy_key.id), proxy_key.requests_per_minute):
            return Response(
                content='{"error":{"message":"Rate limit exceeded","type":"rate_limit_error"}}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"},
            )

        # Capture before session closes
        proxy_key_user_id = proxy_key.user_id
        proxy_key_id_val = proxy_key.id
        proxy_key_label_val = proxy_key.label

        if not proxy_key.backend_config_id:
            return _NO_BACKEND

        bc_result = await session.exec(
            select(BackendConfig).where(
                BackendConfig.id == proxy_key.backend_config_id,
                BackendConfig.user_id == proxy_key.user_id,
            )
        )
        backend_config = bc_result.first()
        if backend_config is None:
            return _NO_BACKEND

        # Eagerly copy all needed fields before session closes
        backend_type_val = backend_config.backend_type
        backend_base_url = backend_config.base_url
        backend_ciphertext = backend_config.credential_ciphertext

    encrypt_key = _get_encrypt_key(request)

    # Build a thin object for _make_adapter
    class _BackendData:
        backend_type = backend_type_val
        base_url = backend_base_url
        credential_ciphertext = backend_ciphertext

    adapter = _make_adapter(_BackendData(), encrypt_key)  # type: ignore[arg-type]
    # app.state.config is set by lifespan; fall back to empty config in tests
    try:
        config = request.app.state.config
    except AttributeError:
        from proxy.config import RelayConfig
        config = RelayConfig()

    body: dict[str, Any] = await request.json()
    model: str = body.get("model", "unknown")
    is_stream: bool = bool(body.get("stream", False))

    if is_stream:
        return await _handle_streaming(
            adapter=adapter,
            body=body,
            model=model,
            user_id=proxy_key_user_id,
            proxy_key_id=proxy_key_id_val,
            proxy_key_label=proxy_key_label_val,
            backend_type=backend_type_val,
            rates=config.cost_rates,
        )

    chat_req = ChatRequest(body=body, model=model)
    t0 = time.monotonic()
    try:
        chat_resp, usage = await adapter.chat_complete(chat_req)
    except Exception as exc:
        logger.error("Backend error: %s", exc)
        error_usage = UsageData(input_tokens=0, output_tokens=0, source="exact")
        await _write_record(
            user_id=proxy_key_user_id,
            proxy_key_id=proxy_key_id_val,
            proxy_key_label=proxy_key_label_val,
            model=model,
            backend_type=backend_type_val,
            usage=error_usage,
            cost=0.0,
            status_code=502,
        )
        return Response(
            content='{"error":{"message":"Bad gateway","type":"backend_error"}}',
            status_code=502,
            media_type="application/json",
        )

    elapsed = time.monotonic() - t0
    tps = _extract_tokens_per_second(chat_resp.body, usage, elapsed)
    cost = compute_cost(model, usage, config.cost_rates)
    await _write_record(
        user_id=proxy_key_user_id,
        proxy_key_id=proxy_key_id_val,
        proxy_key_label=proxy_key_label_val,
        model=model,
        backend_type=backend_type_val,
        usage=usage,
        cost=cost,
        status_code=chat_resp.status_code,
        tokens_per_second=tps,
    )

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
    user_id: uuid.UUID,
    proxy_key_id: uuid.UUID,
    proxy_key_label: str | None,
    backend_type: str,
    rates,
):
    chat_req = ChatRequest(body=body, model=model)
    final_usage: UsageData | None = None
    t0 = time.monotonic()

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
            elapsed = time.monotonic() - t0
            resolved_usage = final_usage or UsageData(
                input_tokens=0, output_tokens=0, source="estimated"
            )
            tps = (resolved_usage.output_tokens / elapsed) if elapsed > 0 and resolved_usage.output_tokens > 0 else None
            cost = compute_cost(model, resolved_usage, rates)
            await _write_record(
                user_id=user_id,
                proxy_key_id=proxy_key_id,
                proxy_key_label=proxy_key_label,
                model=model,
                backend_type=backend_type,
                usage=resolved_usage,
                cost=cost,
                status_code=200,
                tokens_per_second=tps,
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
