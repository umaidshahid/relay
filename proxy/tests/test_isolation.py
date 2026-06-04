"""
proxy/tests/test_isolation.py

Cross-user access tests — every data endpoint MUST return 403 or 404
when user B supplies user A's resource IDs.

Constitution §II: isolation is enforced at the data layer.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from proxy.main import app


async def _make_cred_and_key(c: AsyncClient, token: str, label: str) -> tuple[str, str]:
    cred = (await c.post(
        "/api/credentials",
        json={"name": label, "backend_type": "openai_compat", "base_url": "https://example.com/v1"},
        headers={"Authorization": f"Bearer {token}"},
    )).json()
    key = (await c.post(
        "/api/keys",
        json={"label": label, "backend_config_id": cred["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )).json()
    return cred["id"], key["id"]


@pytest.mark.asyncio
async def test_user_b_cannot_see_user_a_keys(two_users):
    """User B lists proxy keys — should see 0, not user A's keys."""
    user_a, token_a, user_b, token_b = two_users

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        _, key_id_a = await _make_cred_and_key(c, token_a, "app-a")

        list_b = await c.get("/api/keys", headers={"Authorization": f"Bearer {token_b}"})
        assert list_b.status_code == 200
        ids_b = [k["id"] for k in list_b.json()]
        assert key_id_a not in ids_b
        assert len(ids_b) == 0


@pytest.mark.asyncio
async def test_user_b_cannot_revoke_user_a_key(two_users):
    """User B DELETE on user A's key ID → 404."""
    user_a, token_a, user_b, token_b = two_users

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        _, key_id_a = await _make_cred_and_key(c, token_a, "app-a")

        resp = await c.delete(
            f"/api/keys/{key_id_a}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_user_b_cannot_see_user_a_credentials(two_users):
    """User B GET /api/credentials → empty list (not user A's configs)."""
    user_a, token_a, user_b, token_b = two_users

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # User A creates a credential
        await c.post(
            "/api/credentials",
            json={"name": "OpenAI", "backend_type": "openai_compat", "base_url": "https://api.openai.com/v1", "credential": "sk-usera-secret-key"},
            headers={"Authorization": f"Bearer {token_a}"},
        )

        # User B sees their own (empty)
        resp_b = await c.get("/api/credentials", headers={"Authorization": f"Bearer {token_b}"})
        assert resp_b.status_code == 200
        assert resp_b.json() == []


@pytest.mark.asyncio
async def test_user_b_cannot_see_user_a_stats(two_users):
    """Stats endpoints return user-scoped data only."""
    user_a, token_a, user_b, token_b = two_users

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # User B has zero records
        summary_b = await c.get(
            "/stats/summary", headers={"Authorization": f"Bearer {token_b}"}
        )
        assert summary_b.status_code == 200
        assert summary_b.json()["total_requests"] == 0

        by_key_b = await c.get(
            "/stats/by-key", headers={"Authorization": f"Bearer {token_b}"}
        )
        assert by_key_b.json() == []

        requests_b = await c.get(
            "/stats/requests", headers={"Authorization": f"Bearer {token_b}"}
        )
        assert requests_b.json()["total"] == 0
        assert requests_b.json()["items"] == []
