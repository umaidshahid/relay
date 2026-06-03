"""
proxy/routers/stats.py

Read-only stats endpoints consumed by the dashboard.

All five endpoints defined in contracts/stats-api.md:
  GET /stats/summary
  GET /stats/by-key
  GET /stats/by-model
  GET /stats/timeseries
  GET /stats/requests
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from proxy.db.models import UsageRecord
from proxy.db.session import get_session_dep

from fastapi import Depends

router = APIRouter()


@router.get("/summary")
async def summary(session: AsyncSession = Depends(get_session_dep)):
    result = await session.exec(  # type: ignore[call-overload]
        select(
            func.coalesce(func.sum(UsageRecord.cost), 0.0).label("total_cost"),
            func.count(UsageRecord.id).label("total_requests"),
            func.coalesce(func.sum(UsageRecord.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0).label("total_output_tokens"),
        )
    )
    row = result.one()
    return {
        "total_cost": float(row.total_cost),
        "total_requests": int(row.total_requests),
        "total_input_tokens": int(row.total_input_tokens),
        "total_output_tokens": int(row.total_output_tokens),
    }


@router.get("/by-key")
async def by_key(session: AsyncSession = Depends(get_session_dep)):
    result = await session.exec(  # type: ignore[call-overload]
        select(
            UsageRecord.api_key_label,
            func.coalesce(func.sum(UsageRecord.cost), 0.0).label("total_cost"),
            func.count(UsageRecord.id).label("total_requests"),
            func.coalesce(func.sum(UsageRecord.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0).label("total_output_tokens"),
        )
        .group_by(UsageRecord.api_key_label)
        .order_by(func.sum(UsageRecord.cost).desc())
    )
    rows = result.all()
    return [
        {
            "api_key_label": row.api_key_label,
            "total_cost": float(row.total_cost),
            "total_requests": int(row.total_requests),
            "total_input_tokens": int(row.total_input_tokens),
            "total_output_tokens": int(row.total_output_tokens),
        }
        for row in rows
    ]


@router.get("/by-model")
async def by_model(session: AsyncSession = Depends(get_session_dep)):
    result = await session.exec(  # type: ignore[call-overload]
        select(
            UsageRecord.model,
            UsageRecord.backend,
            func.coalesce(func.sum(UsageRecord.cost), 0.0).label("total_cost"),
            func.count(UsageRecord.id).label("total_requests"),
            func.coalesce(func.sum(UsageRecord.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0).label("total_output_tokens"),
        )
        .group_by(UsageRecord.model, UsageRecord.backend)
        .order_by(func.sum(UsageRecord.cost).desc())
    )
    rows = result.all()
    return [
        {
            "model": row.model,
            "backend": row.backend,
            "total_cost": float(row.total_cost),
            "total_requests": int(row.total_requests),
            "total_input_tokens": int(row.total_input_tokens),
            "total_output_tokens": int(row.total_output_tokens),
        }
        for row in rows
    ]


@router.get("/timeseries")
async def timeseries(
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session_dep),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = await session.exec(  # type: ignore[call-overload]
        select(
            func.strftime("%Y-%m-%d", UsageRecord.timestamp).label("date"),
            func.coalesce(func.sum(UsageRecord.cost), 0.0).label("total_cost"),
            func.count(UsageRecord.id).label("total_requests"),
        )
        .where(UsageRecord.timestamp >= cutoff)
        .group_by(func.strftime("%Y-%m-%d", UsageRecord.timestamp))
        .order_by(func.strftime("%Y-%m-%d", UsageRecord.timestamp))
    )
    rows = result.all()
    return [
        {
            "date": row.date,
            "total_cost": float(row.total_cost),
            "total_requests": int(row.total_requests),
        }
        for row in rows
    ]


@router.get("/requests")
async def requests(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session_dep),
):
    count_result = await session.exec(  # type: ignore[call-overload]
        select(func.count(UsageRecord.id))
    )
    total = int(count_result.one())

    result = await session.exec(  # type: ignore[call-overload]
        select(UsageRecord)
        .order_by(UsageRecord.timestamp.desc())  # type: ignore[attr-defined]
        .offset(offset)
        .limit(limit)
    )
    records = result.all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "api_key_label": r.api_key_label,
                "model": r.model,
                "backend": r.backend,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost": r.cost,
                "token_count_source": r.token_count_source,
                "status_code": r.status_code,
            }
            for r in records
        ],
    }
