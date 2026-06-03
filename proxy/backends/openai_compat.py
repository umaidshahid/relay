"""
proxy/backends/openai_compat.py

Backend adapter for OpenAI-compatible HTTP APIs (OpenAI, Together, Groq, etc.).

Non-streaming: reads usage.prompt_tokens / usage.completion_tokens from the
response body → UsageData(source="exact").

Streaming: injects stream_options.include_usage=true so the final SSE chunk
contains usage data → UsageData(source="exact") from the final chunk.

Falls back to tiktoken estimation when usage is absent.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from proxy.backends.base import BackendAdapter, ChatRequest, ChatResponse, UsageData
from proxy.metering import estimate_tokens_tiktoken

logger = logging.getLogger(__name__)

# Satisfy the Protocol type-checker
_ = BackendAdapter


class OpenAICompatAdapter:
    """Adapter for OpenAI-compatible REST APIs."""

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat_complete(
        self, request: ChatRequest
    ) -> tuple[ChatResponse, UsageData]:
        """Forward a non-streaming chat-completion request."""
        url = f"{self.base_url}/chat/completions"
        body = dict(request.body)
        body.pop("stream", None)  # ensure non-streaming

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url,
                json=body,
                headers=self._headers(),
            )

        resp_body: dict[str, Any] = {}
        try:
            resp_body = response.json()
        except Exception:
            resp_body = {"error": response.text}

        usage = _extract_usage_from_body(resp_body)
        if usage is None:
            messages = body.get("messages", [])
            usage = estimate_tokens_tiktoken(messages)
            logger.debug("No usage in response — falling back to tiktoken estimate")

        chat_response = ChatResponse(body=resp_body, status_code=response.status_code)
        return chat_response, usage

    async def chat_complete_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[tuple[str, UsageData | None]]:
        """Forward a streaming chat-completion request, yielding SSE chunks."""
        url = f"{self.base_url}/chat/completions"
        body = dict(request.body)
        body["stream"] = True
        # Request usage in the final chunk
        body.setdefault("stream_options", {})
        body["stream_options"]["include_usage"] = True

        usage: UsageData | None = None
        messages = body.get("messages", [])

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST", url, json=body, headers=self._headers()
            ) as response:
                async for raw_line in response.aiter_lines():
                    if not raw_line:
                        continue

                    # Forward the raw SSE line (with data: prefix) to the caller
                    line = raw_line if raw_line.startswith("data:") else f"data: {raw_line}"
                    sse_line = f"{line}\n\n"

                    # Try to extract usage from the final chunk
                    chunk_usage = _extract_usage_from_sse_line(raw_line)
                    if chunk_usage is not None:
                        usage = chunk_usage

                    yield sse_line, None

        # After the stream, yield final None chunk with resolved usage
        if usage is None:
            usage = estimate_tokens_tiktoken(messages)
            logger.debug("No usage in stream — falling back to tiktoken estimate")

        yield "", usage


def _extract_usage_from_body(body: dict[str, Any]) -> UsageData | None:
    """Extract token counts from a non-streaming response body."""
    usage_obj = body.get("usage")
    if not isinstance(usage_obj, dict):
        return None
    prompt = usage_obj.get("prompt_tokens")
    completion = usage_obj.get("completion_tokens")
    if prompt is None or completion is None:
        return None
    return UsageData(
        input_tokens=int(prompt),
        output_tokens=int(completion),
        source="exact",
    )


def _extract_usage_from_sse_line(raw_line: str) -> UsageData | None:
    """Extract token counts from a single SSE data line, if present."""
    data = raw_line.removeprefix("data:").strip()
    if data in ("[DONE]", ""):
        return None
    try:
        chunk = json.loads(data)
    except json.JSONDecodeError:
        return None
    usage_obj = chunk.get("usage")
    if not isinstance(usage_obj, dict):
        return None
    prompt = usage_obj.get("prompt_tokens")
    completion = usage_obj.get("completion_tokens")
    if prompt is None or completion is None:
        return None
    return UsageData(
        input_tokens=int(prompt),
        output_tokens=int(completion),
        source="exact",
    )
