"""
proxy/routers/stats.py

Read-only stats endpoints (JWT-authenticated, user-scoped).

All queries MUST filter by user_id — Constitution §II invariant.

GET /stats/summary
GET /stats/by-key
GET /stats/by-model
GET /stats/timeseries
GET /stats/requests
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from proxy.db.models import User, UsageRecord
from proxy.deps import get_current_user, get_session_dep

router = APIRouter()


@router.get("/summary")
async def summary(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session_dep),
):
    result = await session.exec(  # type: ignore[call-overload]
        select(
            func.coalesce(func.sum(UsageRecord.cost), 0.0).label("total_cost"),
            func.count(UsageRecord.id).label("total_requests"),
            func.coalesce(func.sum(UsageRecord.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0).label("total_output_tokens"),
            func.avg(UsageRecord.tokens_per_second).label("avg_tokens_per_second"),
        ).where(UsageRecord.user_id == user.id)
    )
    row = result.one()
    avg_tps = row.avg_tokens_per_second
    return {
        "total_cost": float(row.total_cost),
        "total_requests": int(row.total_requests),
        "total_input_tokens": int(row.total_input_tokens),
        "total_output_tokens": int(row.total_output_tokens),
        "avg_tokens_per_second": round(float(avg_tps), 1) if avg_tps is not None else None,
    }


@router.get("/by-key")
async def by_key(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session_dep),
):
    result = await session.exec(  # type: ignore[call-overload]
        select(
            UsageRecord.proxy_key_id,
            UsageRecord.proxy_key_label,
            func.coalesce(func.sum(UsageRecord.cost), 0.0).label("total_cost"),
            func.count(UsageRecord.id).label("total_requests"),
            func.coalesce(func.sum(UsageRecord.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0).label("total_output_tokens"),
        )
        .where(UsageRecord.user_id == user.id)
        .group_by(UsageRecord.proxy_key_id, UsageRecord.proxy_key_label)
        .order_by(func.sum(UsageRecord.cost).desc())
    )
    rows = result.all()
    return [
        {
            "proxy_key_id": str(row.proxy_key_id),
            "proxy_key_label": row.proxy_key_label,
            "total_cost": float(row.total_cost),
            "total_requests": int(row.total_requests),
            "total_input_tokens": int(row.total_input_tokens),
            "total_output_tokens": int(row.total_output_tokens),
        }
        for row in rows
    ]


@router.get("/by-model")
async def by_model(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session_dep),
):
    result = await session.exec(  # type: ignore[call-overload]
        select(
            UsageRecord.model,
            UsageRecord.backend_type,
            func.coalesce(func.sum(UsageRecord.cost), 0.0).label("total_cost"),
            func.count(UsageRecord.id).label("total_requests"),
            func.coalesce(func.sum(UsageRecord.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0).label("total_output_tokens"),
        )
        .where(UsageRecord.user_id == user.id)
        .group_by(UsageRecord.model, UsageRecord.backend_type)
        .order_by(func.sum(UsageRecord.cost).desc())
    )
    rows = result.all()
    return [
        {
            "model": row.model,
            "backend_type": row.backend_type,
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
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session_dep),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await session.exec(  # type: ignore[call-overload]
        select(
            func.strftime("%Y-%m-%d", UsageRecord.timestamp).label("date"),
            func.coalesce(func.sum(UsageRecord.cost), 0.0).label("total_cost"),
            func.count(UsageRecord.id).label("total_requests"),
            func.avg(UsageRecord.tokens_per_second).label("avg_tokens_per_second"),
        )
        .where(UsageRecord.user_id == user.id, UsageRecord.timestamp >= cutoff)
        .group_by(func.strftime("%Y-%m-%d", UsageRecord.timestamp))
        .order_by(func.strftime("%Y-%m-%d", UsageRecord.timestamp))
    )
    rows = result.all()
    return [
        {
            "date": row.date,
            "total_cost": float(row.total_cost),
            "total_requests": int(row.total_requests),
            "avg_tokens_per_second": round(float(row.avg_tokens_per_second), 1) if row.avg_tokens_per_second is not None else None,
        }
        for row in rows
    ]


@router.get("/requests")
async def requests(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session_dep),
):
    from sqlalchemy import text as _text  # noqa: F401 — not used, just guard
    count_result = await session.execute(  # type: ignore[call-overload]
        select(func.count(UsageRecord.id)).where(UsageRecord.user_id == user.id)
    )
    total = int(count_result.scalar_one())

    raw_result = await session.execute(
        select(UsageRecord)
        .where(UsageRecord.user_id == user.id)
        .order_by(UsageRecord.timestamp.desc())  # type: ignore[attr-defined]
        .offset(offset)
        .limit(limit)
    )
    records = raw_result.scalars().all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "proxy_key_label": r.proxy_key_label,
                "model": r.model,
                "backend_type": r.backend_type,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost": r.cost,
                "token_count_source": r.token_count_source,
                "status_code": r.status_code,
                "tokens_per_second": round(r.tokens_per_second, 1) if r.tokens_per_second is not None else None,
            }
            for r in records
        ],
    }
