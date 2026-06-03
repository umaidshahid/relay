"""
proxy/db/session.py

Async SQLite engine and session factory for Relay.

Usage (inside a FastAPI route or lifespan):
    async with get_session() as session:
        session.add(record)
        await session.commit()

Call create_db_and_tables() once at application startup (inside the lifespan
context manager) to ensure all tables exist.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


def _db_url() -> str:
    """
    Build the SQLite database URL.

    Resolution order:
    1. ``DATABASE_URL`` environment variable (must be an ``sqlite+aiosqlite://`` URL)
    2. ``relay.db`` in the current working directory
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    db_path = os.environ.get("RELAY_DB_PATH", "relay.db")
    return f"sqlite+aiosqlite:///{db_path}"


# Module-level engine — created once, shared across all requests.
# connect_args: check_same_thread=False is required for SQLite when using
# async (multiple coroutines share the same connection).
engine = create_async_engine(
    _db_url(),
    echo=False,
    connect_args={"check_same_thread": False},
)


async def create_db_and_tables() -> None:
    """Create all SQLModel tables if they do not already exist.

    Called once during application startup via the FastAPI lifespan handler.
    Safe to call on an already-initialised database (uses CREATE TABLE IF NOT
    EXISTS semantics via SQLAlchemy).
    """
    async with engine.begin() as conn:
        # Import models here to ensure they are registered on SQLModel.metadata
        # before create_all is called.
        from proxy.db.models import UsageRecord  # noqa: F401

        await conn.run_sync(SQLModel.metadata.create_all)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that yields a database session.

    The session is committed automatically if no exception is raised;
    otherwise it is rolled back and the exception re-raised.

    Example::

        async with get_session() as session:
            session.add(record)
            # commit happens automatically on __aexit__
    """
    async with AsyncSession(engine) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session_dep() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession.

    Use with ``Depends(get_session_dep)`` in route signatures.
    The caller is responsible for committing; rollback occurs on exception.
    """
    async with AsyncSession(engine) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
