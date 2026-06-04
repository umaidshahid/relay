"""
proxy/db/migrate.py

Incremental SQLite migrations for Relay.

Called once at startup (before create_all) to add columns/tables that
exist in the model but not yet in the on-disk schema.  Safe to run on
an already-migrated database — each step is guarded by a column existence
check.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger(__name__)


async def _columns(conn: AsyncConnection, table: str) -> set[str]:
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    return {row[1] for row in result.fetchall()}


async def run_migrations(conn: AsyncConnection) -> None:
    """Apply all pending migrations in order."""
    await _m001_usage_records_tokens_per_second(conn)
    await _m002_backend_configs_name(conn)
    await _m003_proxy_keys_backend_config_id(conn)
    await _m004_proxy_keys_requests_per_minute(conn)
    await _m005_backend_configs_drop_unique(conn)


async def _m001_usage_records_tokens_per_second(conn: AsyncConnection) -> None:
    cols = await _columns(conn, "usage_records")
    if "tokens_per_second" not in cols:
        await conn.execute(text(
            "ALTER TABLE usage_records ADD COLUMN tokens_per_second REAL"
        ))
        logger.info("Migration: added usage_records.tokens_per_second")


async def _m002_backend_configs_name(conn: AsyncConnection) -> None:
    if "backend_configs" not in (await _tables(conn)):
        return  # table doesn't exist yet; create_all will make it correctly
    cols = await _columns(conn, "backend_configs")
    if "name" not in cols:
        await conn.execute(text(
            "ALTER TABLE backend_configs ADD COLUMN name VARCHAR(100) NOT NULL DEFAULT ''"
        ))
        # Backfill: set name = backend_type for existing rows
        await conn.execute(text(
            "UPDATE backend_configs SET name = backend_type WHERE name = ''"
        ))
        logger.info("Migration: added backend_configs.name")


async def _m003_proxy_keys_backend_config_id(conn: AsyncConnection) -> None:
    if "proxy_keys" not in (await _tables(conn)):
        return
    cols = await _columns(conn, "proxy_keys")
    if "backend_config_id" not in cols:
        await conn.execute(text(
            "ALTER TABLE proxy_keys ADD COLUMN backend_config_id VARCHAR(36)"
        ))
        # Backfill: point existing keys at the user's single existing backend config
        await conn.execute(text("""
            UPDATE proxy_keys
            SET backend_config_id = (
                SELECT id FROM backend_configs
                WHERE backend_configs.user_id = proxy_keys.user_id
                LIMIT 1
            )
            WHERE backend_config_id IS NULL
        """))
        logger.info("Migration: added proxy_keys.backend_config_id (backfilled)")


async def _m004_proxy_keys_requests_per_minute(conn: AsyncConnection) -> None:
    if "proxy_keys" not in (await _tables(conn)):
        return
    cols = await _columns(conn, "proxy_keys")
    if "requests_per_minute" not in cols:
        await conn.execute(text(
            "ALTER TABLE proxy_keys ADD COLUMN requests_per_minute INTEGER"
        ))
        logger.info("Migration: added proxy_keys.requests_per_minute")


async def _m005_backend_configs_drop_unique(conn: AsyncConnection) -> None:
    """SQLite can't DROP UNIQUE constraints directly.

    The unique index on backend_configs.user_id was created by the original
    schema.  We recreate the table without it.  This is a no-op if the index
    doesn't exist.
    """
    result = await conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='backend_configs' AND name='ix_backend_configs_user_id_unique'"
    ))
    if result.fetchone():
        # SQLite requires recreating the table to drop a unique constraint.
        # Simpler: just drop the unique index directly if it was created standalone.
        await conn.execute(text("DROP INDEX IF EXISTS ix_backend_configs_user_id_unique"))
        logger.info("Migration: dropped unique index on backend_configs.user_id")

    # Also drop the implicit unique index SQLModel creates for unique=True fields
    result2 = await conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='backend_configs'"
    ))
    for row in result2.fetchall():
        idx_name = row[0]
        if "user_id" in idx_name and idx_name.startswith("uq_"):
            await conn.execute(text(f"DROP INDEX IF EXISTS {idx_name}"))
            logger.info("Migration: dropped unique index %s", idx_name)


async def _tables(conn: AsyncConnection) -> set[str]:
    result = await conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ))
    return {row[0] for row in result.fetchall()}
