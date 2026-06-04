"""
proxy/tests/test_proxy.py

Tests for /v1/* endpoints — proxy-key authentication, per-user backend
dispatch, and usage recording.

All tests use in-memory SQLite and mock httpx transport; no live LLM required.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from proxy.backends.base import ChatResponse, UsageData
from proxy.main import app

VALID_REQUEST = {
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hi"}],
}

VALID_RESPONSE_BODY = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "model": "gpt-4o-mini",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hello!"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
}


async def _setup_user_with_key(token: str, client: AsyncClient) -> str:
    """Configure a backend credential and create a proxy key; return proxy key plaintext."""
    cred = (await client.post(
        "/api/credentials",
        json={"name": "Test Backend", "backend_type": "openai_compat", "base_url": "http://fake-backend/v1", "credential": "sk-fake-provider-key"},
        headers={"Authorization": f"Bearer {token}"},
    )).json()
    key_resp = await client.post(
        "/api/keys",
        json={"label": "test-app", "backend_config_id": cred["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert key_resp.status_code == 201
    return key_resp.json()["key"]


@pytest.mark.asyncio
async def test_valid_proxy_key_returns_200(user_a_client):
    _, token, client = user_a_client
    proxy_key = await _setup_user_with_key(token, client)

    mock_usage = UsageData(input_tokens=10, output_tokens=5, source="exact")
    mock_response = ChatResponse(body=VALID_RESPONSE_BODY, status_code=200)

    with patch("proxy.routers.proxy.OpenAICompatAdapter") as mock_cls:
        mock_adapter = AsyncMock()
        mock_adapter.chat_complete.return_value = (mock_response, mock_usage)
        mock_cls.return_value = mock_adapter

        resp = await client.post(
            "/v1/chat/completions",
            json=VALID_REQUEST,
            headers={"Authorization": f"Bearer {proxy_key}"},
        )

    assert resp.status_code == 200
    assert resp.json()["id"] == "chatcmpl-test"


@pytest.mark.asyncio
async def test_invalid_proxy_key_returns_401(user_a_client):
    _, token, client = user_a_client
    await _setup_user_with_key(token, client)

    resp = await client.post(
        "/v1/chat/completions",
        json=VALID_REQUEST,
        headers={"Authorization": "Bearer sk-totally-wrong-key"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_missing_auth_returns_401(user_a_client):
    _, _, client = user_a_client
    resp = await client.post("/v1/chat/completions", json=VALID_REQUEST)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_no_backend_configured_returns_400(user_a_client):
    """Key with backend_config_id pointing to a non-existent backend returns 400."""
    _, token, client = user_a_client
    # Create a credential and key, then null out the backend_config_id directly
    cred = (await client.post(
        "/api/credentials",
        json={"name": "Temp", "backend_type": "openai_compat", "base_url": "http://fake/v1"},
        headers={"Authorization": f"Bearer {token}"},
    )).json()
    key_resp = await client.post(
        "/api/keys",
        json={"label": "no-backend-app", "backend_config_id": cred["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    proxy_key = key_resp.json()["key"]
    key_id = key_resp.json()["id"]

    # Null out backend_config_id directly in DB
    from proxy.db import session as db_session
    from proxy.db.models import ProxyKey as PK
    from sqlmodel.ext.asyncio.session import AsyncSession
    from sqlmodel import select
    import uuid as _uuid
    async with AsyncSession(db_session.engine) as s:
        result = await s.exec(select(PK).where(PK.id == _uuid.UUID(key_id)))
        pk = result.first()
        pk.backend_config_id = None
        s.add(pk)
        await s.commit()

    resp = await client.post(
        "/v1/chat/completions",
        json=VALID_REQUEST,
        headers={"Authorization": f"Bearer {proxy_key}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_usage_record_created(user_a_client):
    """After a successful proxy request, a UsageRecord exists for user A."""
    _, token, client = user_a_client
    proxy_key = await _setup_user_with_key(token, client)

    mock_usage = UsageData(input_tokens=10, output_tokens=5, source="exact")
    mock_response = ChatResponse(body=VALID_RESPONSE_BODY, status_code=200)

    with patch("proxy.routers.proxy.OpenAICompatAdapter") as mock_cls:
        mock_adapter = AsyncMock()
        mock_adapter.chat_complete.return_value = (mock_response, mock_usage)
        mock_cls.return_value = mock_adapter

        await client.post(
            "/v1/chat/completions",
            json=VALID_REQUEST,
            headers={"Authorization": f"Bearer {proxy_key}"},
        )

    # Check usage appeared in stats
    stats = await client.get("/stats/summary", headers={"Authorization": f"Bearer {token}"})
    assert stats.json()["total_requests"] == 1


@pytest.mark.asyncio
async def test_revoked_key_returns_401(user_a_client):
    _, token, client = user_a_client
    proxy_key = await _setup_user_with_key(token, client)

    # Get key id
    keys = await client.get("/api/keys", headers={"Authorization": f"Bearer {token}"})
    key_id = keys.json()[0]["id"]

    # Revoke
    await client.delete(
        f"/api/keys/{key_id}", headers={"Authorization": f"Bearer {token}"}
    )

    resp = await client.post(
        "/v1/chat/completions",
        json=VALID_REQUEST,
        headers={"Authorization": f"Bearer {proxy_key}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_two_users_use_own_backends(two_users):
    """User A and B each have different backends; each request goes to the correct one."""
    user_a, token_a, user_b, token_b = two_users

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Setup user A
        cred_a = (await c.post(
            "/api/credentials",
            json={"name": "Backend A", "backend_type": "openai_compat", "base_url": "http://backend-a/v1", "credential": "sk-key-for-a"},
            headers={"Authorization": f"Bearer {token_a}"},
        )).json()
        key_a = (await c.post(
            "/api/keys",
            json={"label": "a", "backend_config_id": cred_a["id"]},
            headers={"Authorization": f"Bearer {token_a}"},
        )).json()["key"]

        # Setup user B
        cred_b = (await c.post(
            "/api/credentials",
            json={"name": "Backend B", "backend_type": "openai_compat", "base_url": "http://backend-b/v1", "credential": "sk-key-for-b"},
            headers={"Authorization": f"Bearer {token_b}"},
        )).json()
        key_b = (await c.post(
            "/api/keys",
            json={"label": "b", "backend_config_id": cred_b["id"]},
            headers={"Authorization": f"Bearer {token_b}"},
        )).json()["key"]

        captured_urls: list[str] = []

        mock_usage = UsageData(input_tokens=5, output_tokens=3, source="exact")
        mock_resp = ChatResponse(body=VALID_RESPONSE_BODY, status_code=200)

        original_init = __import__(
            "proxy.backends.openai_compat", fromlist=["OpenAICompatAdapter"]
        ).OpenAICompatAdapter.__init__

        def tracking_init(self, base_url, api_key=None):
            captured_urls.append(base_url)
            original_init(self, base_url=base_url, api_key=api_key)

        with patch("proxy.routers.proxy.OpenAICompatAdapter") as mock_cls:
            instances = []

            def make_instance(base_url, api_key=None):
                captured_urls.append(base_url)
                inst = AsyncMock()
                inst.chat_complete.return_value = (mock_resp, mock_usage)
                instances.append(inst)
                return inst

            mock_cls.side_effect = make_instance

            await c.post(
                "/v1/chat/completions",
                json=VALID_REQUEST,
                headers={"Authorization": f"Bearer {key_a}"},
            )
            await c.post(
                "/v1/chat/completions",
                json=VALID_REQUEST,
                headers={"Authorization": f"Bearer {key_b}"},
            )

        assert "http://backend-a/v1" in captured_urls
        assert "http://backend-b/v1" in captured_urls
