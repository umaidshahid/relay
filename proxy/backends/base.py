"""
proxy/backends/base.py

Protocol and shared value types for LLM backend adapters.

All concrete backend adapters (openai_compat, ollama) must satisfy the
BackendAdapter Protocol.  The metering layer imports only from this module —
never from any concrete adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, AsyncIterator, Literal, Protocol

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass
class UsageData:
    """Token counts extracted or estimated for a single request."""

    input_tokens: int
    output_tokens: int
    source: Literal["exact", "estimated"]


# ---------------------------------------------------------------------------
# Request / Response wrappers
# ---------------------------------------------------------------------------


@dataclass
class ChatRequest:
    """Thin wrapper around an incoming chat-completion request body."""

    body: dict[str, Any]
    model: str


@dataclass
class ChatResponse:
    """Thin wrapper around a completed (non-streaming) backend response."""

    body: dict[str, Any]
    status_code: int


# ---------------------------------------------------------------------------
# Backend Protocol
# ---------------------------------------------------------------------------


class BackendAdapter(Protocol):
    """Interface every backend adapter must implement.

    Metering code imports only this Protocol — never the concrete adapters.
    Adding a new backend means implementing this Protocol; no metering code
    changes required.
    """

    async def chat_complete(
        self, request: ChatRequest
    ) -> tuple[ChatResponse, UsageData]:
        """Send a non-streaming chat-completion request and return the response
        plus exact-or-estimated token usage."""
        ...

    async def chat_complete_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[tuple[str, UsageData | None]]:
        """Send a streaming chat-completion request.

        Yields (chunk_text, usage_or_none) pairs.  usage_or_none is non-None
        only on the final chunk, once the backend has reported token counts.
        """
        ...
