"""
proxy/tests/test_auth.py

Tests for /auth/* endpoints (FastAPI-Users backed).
No live network or LLM required — in-memory SQLite.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_returns_201(client: AsyncClient):
    resp = await client.post(
        "/auth/register",
        json={"email": "new@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "new@example.com"
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_400(client: AsyncClient):
    payload = {"email": "dup@example.com", "password": "password123"}
    await client.post("/auth/register", json=payload)
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login_returns_jwt(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"email": "login@example.com", "password": "password123"},
    )
    resp = await client.post(
        "/auth/jwt/login",
        data={"username": "login@example.com", "password": "password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_400(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"email": "wrong@example.com", "password": "correct123"},
    )
    resp = await client.post(
        "/auth/jwt/login",
        data={"username": "wrong@example.com", "password": "incorrect"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_me_with_valid_jwt(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"email": "me@example.com", "password": "password123"},
    )
    login = await client.post(
        "/auth/jwt/login",
        data={"username": "me@example.com", "password": "password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = login.json()["access_token"]

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_get_me_without_jwt_returns_401(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stats_without_jwt_returns_401(client: AsyncClient):
    resp = await client.get("/stats/summary")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_two_users_get_own_me(two_users):
    user_a, token_a, user_b, token_b = two_users
    async with __import__("httpx").AsyncClient(
        transport=__import__("httpx").ASGITransport(app=__import__("proxy.main", fromlist=["app"]).app),
        base_url="http://test",
    ) as client:
        resp_a = await client.get("/auth/me", headers={"Authorization": f"Bearer {token_a}"})
        resp_b = await client.get("/auth/me", headers={"Authorization": f"Bearer {token_b}"})

    assert resp_a.json()["email"] == "usera@example.com"
    assert resp_b.json()["email"] == "userb@example.com"
    assert resp_a.json()["id"] != resp_b.json()["id"]
