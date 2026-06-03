"""
proxy/db/models.py

SQLModel table definitions for Relay.

The only persisted entity is UsageRecord — one row per completed proxied
request.  No prompt or response content is stored.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, Index, SQLModel


class UsageRecord(SQLModel, table=True):
    """One row per completed proxied request."""

    __tablename__ = "usage_records"

    # Explicit index declarations via __table_args__; SQLModel forwards these
    # to the underlying SQLAlchemy Table object.
    __table_args__ = (
        Index("ix_usage_records_timestamp", "timestamp"),
        Index("ix_usage_records_api_key_label", "api_key_label"),
        Index("ix_usage_records_model", "model"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # UTC time the request completed
    timestamp: datetime = Field(nullable=False)

    # Denormalised from ApiKey.label at write time so history survives key
    # renames / removals.
    api_key_label: str = Field(nullable=False, max_length=255)

    # Backend identifier: "openai_compat" | "ollama"
    backend: str = Field(nullable=False, max_length=64)

    # Model name as reported by or sent to the backend
    model: str = Field(nullable=False, max_length=255)

    # Token counts (≥ 0).  Error requests are stored with 0 tokens.
    input_tokens: int = Field(nullable=False, ge=0)
    output_tokens: int = Field(nullable=False, ge=0)

    # Computed cost in USD (0.0 when no rate configured)
    cost: float = Field(nullable=False, ge=0.0)

    # "exact" = counts from provider response; "estimated" = tiktoken fallback
    token_count_source: str = Field(nullable=False, max_length=16)

    # HTTP status code returned to the client
    status_code: int = Field(nullable=False)
