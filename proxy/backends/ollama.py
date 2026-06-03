"""
proxy/backends/ollama.py

Backend adapter for Ollama (local model server).

Non-streaming: POST /api/chat, extract prompt_eval_count and eval_count
from the response → UsageData(source="exact"). Falls back to tiktoken when
fields are absent.

Streaming: POST /api/chat with stream=true, Ollama returns NDJSON lines;
the final line contains prompt_eval_count / eval_count.

Ollama response shape is mapped to an OpenAI-compatible response body
so the proxy router can return it unchanged.
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

_ = BackendAdapter  # satisfy Protocol type-checker


class OllamaAdapter:
    """Adapter for the Ollama local model server."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _extract_usage(self, body: dict[str, Any]) -> UsageData | None:
        """Extract exact token counts from an Ollama response body."""
        prompt_tokens = body.get("prompt_eval_count")
        completion_tokens = body.get("eval_count")
        if prompt_tokens is None or completion_tokens is None:
            return None
        return UsageData(
            input_tokens=int(prompt_tokens),
            output_tokens=int(completion_tokens),
            source="exact",
        )

    def _to_openai_response(
        self, ollama_body: dict[str, Any], model: str
    ) -> dict[str, Any]:
        """Convert an Ollama response to an OpenAI-compatible response shape."""
        message = ollama_body.get("message", {})
        return {
            "id": f"ollama-{ollama_body.get('created_at', 'unknown')}",
            "object": "chat.completion",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": message.get("role", "assistant"),
                        "content": message.get("content", ""),
                    },
                    "finish_reason": "stop" if ollama_body.get("done") else None,
                }
            ],
        }

    async def chat_complete(
        self, request: ChatRequest
    ) -> tuple[ChatResponse, UsageData]:
        """Forward a non-streaming chat-completion request to Ollama."""
        url = f"{self.base_url}/api/chat"
        body: dict[str, Any] = {
            "model": request.model,
            "messages": request.body.get("messages", []),
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(url, json=body)

        ollama_body: dict[str, Any] = {}
        try:
            ollama_body = response.json()
        except Exception:
            ollama_body = {}

        usage = self._extract_usage(ollama_body)
        if usage is None:
            messages = request.body.get("messages", [])
            usage = estimate_tokens_tiktoken(messages)
            logger.debug("No Ollama usage counts — falling back to tiktoken estimate")

        openai_body = self._to_openai_response(ollama_body, request.model)
        chat_response = ChatResponse(body=openai_body, status_code=response.status_code)
        return chat_response, usage

    async def chat_complete_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[tuple[str, UsageData | None]]:
        """Forward a streaming chat-completion request to Ollama (NDJSON)."""
        url = f"{self.base_url}/api/chat"
        body: dict[str, Any] = {
            "model": request.model,
            "messages": request.body.get("messages", []),
            "stream": True,
        }

        usage: UsageData | None = None
        messages = request.body.get("messages", [])

        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream("POST", url, json=body) as response:
                async for raw_line in response.aiter_lines():
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue

                    try:
                        chunk = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue

                    # Convert Ollama chunk to an OpenAI-style SSE chunk
                    content = chunk.get("message", {}).get("content", "")
                    openai_chunk = {
                        "object": "chat.completion.chunk",
                        "model": request.model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "content": content},
                                "finish_reason": "stop" if chunk.get("done") else None,
                            }
                        ],
                    }
                    sse_line = f"data: {json.dumps(openai_chunk)}\n\n"

                    if chunk.get("done"):
                        usage = self._extract_usage(chunk)

                    yield sse_line, None

        if usage is None:
            usage = estimate_tokens_tiktoken(messages)
            logger.debug("No Ollama stream usage — falling back to tiktoken estimate")

        yield "", usage
