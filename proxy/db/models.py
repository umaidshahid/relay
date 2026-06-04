"""
proxy/db/models.py

SQLModel table definitions for Relay (multi-user).

Tables:
  User          — FastAPI-Users managed; all other tables FK here
  ProxyKey      — per-user proxy API keys (stored hashed)
  BackendConfig — per-user LLM provider config (credential stored encrypted)
  UsageRecord   — one row per completed proxied request (user-scoped)

Constitution §II invariant: every query against ProxyKey, BackendConfig, and
UsageRecord MUST filter by user_id.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import Index, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlmodel import Field, SQLModel


# ---------------------------------------------------------------------------
# Shared metadata: we attach all tables to SQLModel.metadata so that a
# single create_all call creates everything.
# ---------------------------------------------------------------------------

# User must use SQLAlchemy's DeclarativeBase because FastAPI-Users'
# base class uses SQLAlchemy Mapped[] annotations that are incompatible
# with SQLModel's metaclass.  We configure User to register its Table on
# SQLModel.metadata so ProxyKey / BackendConfig / UsageRecord FKs resolve.

class _Base(DeclarativeBase):
    # Share SQLModel's metadata so all tables live in one registry
    metadata = SQLModel.metadata  # type: ignore[assignment]


class User(_Base, SQLAlchemyBaseUserTableUUID):
    __tablename__ = "users"

    display_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, default=None
    )


# ---------------------------------------------------------------------------
# ProxyKey
# ---------------------------------------------------------------------------

class ProxyKey(SQLModel, table=True):
    __tablename__ = "proxy_keys"
    __table_args__ = (
        Index("ix_proxy_keys_user_id", "user_id"),
        Index("ix_proxy_keys_key_hash", "key_hash"),
    )

    id: Optional[uuid.UUID] = Field(
        default_factory=uuid.uuid4, primary_key=True
    )
    user_id: uuid.UUID = Field(nullable=False, foreign_key="users.id")
    backend_config_id: Optional[uuid.UUID] = Field(default=None, foreign_key="backend_configs.id")
    key_hash: str = Field(nullable=False, unique=True, max_length=64)
    key_prefix: str = Field(nullable=False, max_length=8)
    key_suffix: str = Field(nullable=False, max_length=4)
    label: Optional[str] = Field(default=None, max_length=100)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(nullable=False)
    revoked_at: Optional[datetime] = Field(default=None)
    requests_per_minute: Optional[int] = Field(default=None, ge=1)


# ---------------------------------------------------------------------------
# BackendConfig
# ---------------------------------------------------------------------------

class BackendConfig(SQLModel, table=True):
    __tablename__ = "backend_configs"

    id: Optional[uuid.UUID] = Field(
        default_factory=uuid.uuid4, primary_key=True
    )
    user_id: uuid.UUID = Field(nullable=False, foreign_key="users.id")
    name: str = Field(nullable=False, max_length=100)  # user-facing label
    backend_type: str = Field(nullable=False, max_length=32)
    base_url: str = Field(nullable=False)
    credential_ciphertext: Optional[str] = Field(default=None)
    credential_suffix: Optional[str] = Field(default=None, max_length=4)
    updated_at: datetime = Field(nullable=False)


# ---------------------------------------------------------------------------
# UsageRecord
# ---------------------------------------------------------------------------

class UsageRecord(SQLModel, table=True):
    __tablename__ = "usage_records"
    __table_args__ = (
        Index("ix_usage_records_user_id", "user_id"),
        Index("ix_usage_records_timestamp", "timestamp"),
        Index("ix_usage_records_model", "model"),
        Index("ix_usage_records_user_timestamp", "user_id", "timestamp"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: uuid.UUID = Field(nullable=False, foreign_key="users.id")
    timestamp: datetime = Field(nullable=False)
    proxy_key_id: uuid.UUID = Field(nullable=False, foreign_key="proxy_keys.id")
    proxy_key_label: str = Field(nullable=False, max_length=255)
    backend_type: str = Field(nullable=False, max_length=64)
    model: str = Field(nullable=False, max_length=255)
    input_tokens: int = Field(nullable=False, ge=0)
    output_tokens: int = Field(nullable=False, ge=0)
    cost: float = Field(nullable=False, ge=0.0)
    token_count_source: str = Field(nullable=False, max_length=16)
    status_code: int = Field(nullable=False)
    tokens_per_second: Optional[float] = Field(default=None)
