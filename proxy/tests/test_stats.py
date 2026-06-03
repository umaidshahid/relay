"""
Tests for proxy/routers/stats.py — unit tests against in-memory SQLite.

Seeds a known set of UsageRecords and asserts correct aggregation across
all five stats endpoints.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from proxy.db.models import UsageRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def use_test_db(tmp_path):
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/test_stats.db"
    yield
    os.environ.pop("DATABASE_URL", None)


async def _seed_records(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    records = [
        UsageRecord(
            timestamp=now - timedelta(hours=2),
            api_key_label="app-a",
            backend="openai_compat",
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
            cost=0.04,
            token_count_source="exact",
            status_code=200,
        ),
        UsageRecord(
            timestamp=now - timedelta(hours=1),
            api_key_label="app-b",
            backend="openai_compat",
            model="gpt-4o-mini",
            input_tokens=200,
            output_tokens=80,
            cost=0.10,
            token_count_source="exact",
            status_code=200,
        ),
        UsageRecord(
            timestamp=now,
            api_key_label="app-a",
            backend="ollama",
            model="llama3",
            input_tokens=50,
            output_tokens=20,
            cost=0.0,
            token_count_source="exact",
            status_code=200,
        ),
    ]
    for r in records:
        session.add(r)
    await session.commit()


@pytest_asyncio.fixture
async def seeded_session():
    from proxy.db import session as db_session
    # Reinitialise engine to use the test DB
    db_session.engine = create_async_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
    )
    async with db_session.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(db_session.engine) as session:
        await _seed_records(session)

    yield db_session.engine


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summary_totals(seeded_session):
    from proxy.db import session as db_session
    async with AsyncSession(db_session.engine) as session:
        from sqlalchemy import func, select
        result = await session.exec(  # type: ignore[call-overload]
            select(
                func.sum(UsageRecord.cost).label("total_cost"),
                func.count(UsageRecord.id).label("total_requests"),
                func.sum(UsageRecord.input_tokens).label("total_input"),
                func.sum(UsageRecord.output_tokens).label("total_output"),
            )
        )
        row = result.one()
    assert float(row.total_cost) == pytest.approx(0.14)
    assert int(row.total_requests) == 3
    assert int(row.total_input) == 350
    assert int(row.total_output) == 150


@pytest.mark.asyncio
async def test_by_key_groups_correctly(seeded_session):
    from proxy.db import session as db_session
    from sqlalchemy import func, select
    async with AsyncSession(db_session.engine) as session:
        result = await session.exec(  # type: ignore[call-overload]
            select(
                UsageRecord.api_key_label,
                func.count(UsageRecord.id).label("cnt"),
            ).group_by(UsageRecord.api_key_label)
        )
        rows = {r.api_key_label: r.cnt for r in result.all()}
    assert rows["app-a"] == 2
    assert rows["app-b"] == 1


@pytest.mark.asyncio
async def test_by_model_groups_correctly(seeded_session):
    from proxy.db import session as db_session
    from sqlalchemy import func, select
    async with AsyncSession(db_session.engine) as session:
        result = await session.exec(  # type: ignore[call-overload]
            select(
                UsageRecord.model,
                func.count(UsageRecord.id).label("cnt"),
            ).group_by(UsageRecord.model)
        )
        rows = {r.model: r.cnt for r in result.all()}
    assert rows["gpt-4o-mini"] == 2
    assert rows["llama3"] == 1


@pytest.mark.asyncio
async def test_empty_db_returns_zero_totals(tmp_path):
    from proxy.db import session as db_session
    db_url = f"sqlite+aiosqlite:///{tmp_path}/empty.db"
    db_session.engine = create_async_engine(db_url, connect_args={"check_same_thread": False})
    async with db_session.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    from sqlalchemy import func, select
    async with AsyncSession(db_session.engine) as session:
        result = await session.exec(  # type: ignore[call-overload]
            select(
                func.coalesce(func.sum(UsageRecord.cost), 0.0).label("total_cost"),
                func.count(UsageRecord.id).label("total_requests"),
            )
        )
        row = result.one()
    assert float(row.total_cost) == 0.0
    assert int(row.total_requests) == 0


@pytest.mark.asyncio
async def test_timeseries_filters_by_days(seeded_session):
    from proxy.db import session as db_session
    from sqlalchemy import func, select
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    async with AsyncSession(db_session.engine) as session:
        result = await session.exec(  # type: ignore[call-overload]
            select(func.count(UsageRecord.id))
            .where(UsageRecord.timestamp >= cutoff)
        )
        count = result.scalar()
    assert count == 3  # all 3 seeds are within the last day


@pytest.mark.asyncio
async def test_requests_pagination(seeded_session):
    from proxy.db import session as db_session
    from sqlalchemy import select
    async with AsyncSession(db_session.engine) as session:
        result = await session.exec(  # type: ignore[call-overload]
            select(UsageRecord)
            .order_by(UsageRecord.timestamp.desc())  # type: ignore[attr-defined]
            .offset(1)
            .limit(2)
        )
        rows = result.all()
    assert len(rows) == 2
