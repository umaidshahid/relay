"""
proxy/tests/test_stats.py

Tests for /stats/* endpoints — user-scoped aggregations.
Seeds UsageRecords directly via SQLModel and verifies endpoint responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from proxy.backends.base import ChatResponse, UsageData
from proxy.db import session as db_session
from proxy.db.models import UsageRecord
from proxy.main import app


async def _seed_records_for_user(
    session: AsyncSession, user_id: uuid.UUID, proxy_key_id: uuid.UUID
) -> None:
    now = datetime.now(timezone.utc)
    records = [
        UsageRecord(
            user_id=user_id,
            timestamp=now - timedelta(hours=2),
            proxy_key_id=proxy_key_id,
            proxy_key_label="app-a",
            backend_type="openai_compat",
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
            cost=0.04,
            token_count_source="exact",
            status_code=200,
        ),
        UsageRecord(
            user_id=user_id,
            timestamp=now - timedelta(hours=1),
            proxy_key_id=proxy_key_id,
            proxy_key_label="app-a",
            backend_type="ollama",
            model="llama3",
            input_tokens=200,
            output_tokens=80,
            cost=0.0,
            token_count_source="estimated",
            status_code=200,
        ),
    ]
    for r in records:
        session.add(r)
    await session.commit()


async def _create_cred_and_key(token: str, client) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a credential + key and return (user_id, key_id)."""
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_id = uuid.UUID(me.json()["id"])
    cred = (await client.post(
        "/api/credentials",
        json={"name": "Test", "backend_type": "openai_compat", "base_url": "https://example.com/v1"},
        headers={"Authorization": f"Bearer {token}"},
    )).json()
    key_resp = await client.post(
        "/api/keys",
        json={"label": "test", "backend_config_id": cred["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    return user_id, uuid.UUID(key_resp.json()["id"])


@pytest.mark.asyncio
async def test_summary_returns_user_scoped_totals(user_a_client):
    _, token, client = user_a_client
    user_id, key_id = await _create_cred_and_key(token, client)

    # Seed directly
    async with AsyncSession(db_session.engine) as session:
        await _seed_records_for_user(session, user_id, key_id)

    resp = await client.get("/stats/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_requests"] == 2
    assert data["total_input_tokens"] == 300
    assert data["total_output_tokens"] == 130
    assert abs(data["total_cost"] - 0.04) < 1e-9


@pytest.mark.asyncio
async def test_summary_empty_returns_zeros(user_a_client):
    _, token, client = user_a_client
    resp = await client.get("/stats/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_requests"] == 0
    assert data["total_cost"] == 0.0


@pytest.mark.asyncio
async def test_two_users_see_only_own_stats(two_users):
    user_a, token_a, user_b, token_b = two_users

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        cred_a = (await c.post(
            "/api/credentials",
            json={"name": "Backend A", "backend_type": "openai_compat", "base_url": "http://fake/v1", "credential": "sk-fake"},
            headers={"Authorization": f"Bearer {token_a}"},
        )).json()
        key_a = (await c.post(
            "/api/keys",
            json={"label": "a", "backend_config_id": cred_a["id"]},
            headers={"Authorization": f"Bearer {token_a}"},
        )).json()["key"]

        mock_usage = UsageData(input_tokens=10, output_tokens=5, source="exact")
        mock_resp_obj = ChatResponse(
            body={
                "id": "x",
                "object": "chat.completion",
                "model": "gpt-4o-mini",
                "choices": [],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
            status_code=200,
        )
        with patch("proxy.routers.proxy.OpenAICompatAdapter") as mock_cls:
            mock_adapter = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock()
            mock_adapter.chat_complete.return_value = (mock_resp_obj, mock_usage)
            mock_cls.return_value = mock_adapter
            await c.post(
                "/v1/chat/completions",
                json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
                headers={"Authorization": f"Bearer {key_a}"},
            )

        # User A sees 1 record, User B sees 0
        summary_a = await c.get("/stats/summary", headers={"Authorization": f"Bearer {token_a}"})
        summary_b = await c.get("/stats/summary", headers={"Authorization": f"Bearer {token_b}"})

    assert summary_a.json()["total_requests"] == 1
    assert summary_b.json()["total_requests"] == 0


@pytest.mark.asyncio
async def test_by_key_groups_by_proxy_key(user_a_client):
    _, token, client = user_a_client
    user_id, key_id = await _create_cred_and_key(token, client)

    async with AsyncSession(db_session.engine) as session:
        await _seed_records_for_user(session, user_id, key_id)

    resp = await client.get("/stats/by-key", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["proxy_key_label"] == "app-a"
    assert data[0]["total_requests"] == 2


@pytest.mark.asyncio
async def test_by_model_groups_by_model(user_a_client):
    _, token, client = user_a_client
    user_id, key_id = await _create_cred_and_key(token, client)

    async with AsyncSession(db_session.engine) as session:
        await _seed_records_for_user(session, user_id, key_id)

    resp = await client.get("/stats/by-model", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    models = {r["model"] for r in data}
    assert "gpt-4o-mini" in models
    assert "llama3" in models


@pytest.mark.asyncio
async def test_requests_pagination(user_a_client):
    _, token, client = user_a_client
    user_id, key_id = await _create_cred_and_key(token, client)

    async with AsyncSession(db_session.engine) as session:
        await _seed_records_for_user(session, user_id, key_id)

    resp = await client.get(
        "/stats/requests?limit=1&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_estimated_tokens_labelled(user_a_client):
    _, token, client = user_a_client
    user_id, key_id = await _create_cred_and_key(token, client)

    async with AsyncSession(db_session.engine) as session:
        await _seed_records_for_user(session, user_id, key_id)

    resp = await client.get("/stats/requests", headers={"Authorization": f"Bearer {token}"})
    sources = {item["token_count_source"] for item in resp.json()["items"]}
    assert "estimated" in sources
