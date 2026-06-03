"""
proxy/metering.py

Token counting and cost calculation for Relay.

This module has NO imports from proxy.backends — it only operates on
UsageData (from proxy.backends.base) and plain Python types.

Two entry points:
  compute_cost()             — given usage + rates, return cost in USD
  estimate_tokens_tiktoken() — tiktoken-based fallback when the backend
                               provides no usage data
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from proxy.backends.base import UsageData
    from proxy.config import CostRate


def compute_cost(
    model: str,
    usage: "UsageData",
    rates: dict[str, "CostRate"],
) -> float:
    """Compute USD cost for a completed request.

    Returns 0.0 if no rate is configured for the model.  The caller is
    responsible for recording this as a zero-cost record (not silently
    omitting it).
    """
    rate = rates.get(model)
    if rate is None:
        return 0.0
    return (usage.input_tokens * rate.input_per_token) + (
        usage.output_tokens * rate.output_per_token
    )


def estimate_tokens_tiktoken(messages: list[dict[str, Any]]) -> "UsageData":
    """Estimate token counts using tiktoken when the backend returns no usage.

    Uses the cl100k_base encoding (GPT-3.5/GPT-4 family) as a safe default.
    Always returns source="estimated" — the caller MUST surface this label
    everywhere the counts are displayed.

    Counting heuristic (matches OpenAI's documented approach):
      - 4 tokens overhead per message (role + framing)
      - 2 tokens overhead for the reply primer (assistant turn start)
    """
    import tiktoken  # lazy import — only used on the fallback path

    from proxy.backends.base import UsageData

    encoding = tiktoken.get_encoding("cl100k_base")

    token_count = 0
    for message in messages:
        token_count += 4  # per-message overhead
        for value in message.values():
            if isinstance(value, str):
                token_count += len(encoding.encode(value))
    token_count += 2  # reply primer

    return UsageData(
        input_tokens=token_count,
        output_tokens=0,
        source="estimated",
    )
