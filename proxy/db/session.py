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
    """Run migrations then create all SQLModel tables if they do not already exist."""
    async with engine.begin() as conn:
        from proxy.db.migrate import run_migrations
        from proxy.db.models import BackendConfig, ProxyKey, UsageRecord, User  # noqa: F401

        await run_migrations(conn)
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
    # expire_on_commit=False: required for async sessions so attributes (e.g.
    # the OAuth user's relationships, read after commit when building the
    # session token) aren't expired and lazily re-loaded outside the async
    # greenlet — which raises MissingGreenlet.
    async with AsyncSession(engine, expire_on_commit=False) as session:
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
    # expire_on_commit=False: required for async sessions so attributes (e.g.
    # the OAuth user's relationships, read after commit when building the
    # session token) aren't expired and lazily re-loaded outside the async
    # greenlet — which raises MissingGreenlet.
    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
