"""
proxy/tests/conftest.py

Shared fixtures for all proxy tests.

Provides:
  test_app          — FastAPI app with in-memory SQLite and test env vars
  async_client_a    — httpx.AsyncClient logged in as user_a
  async_client_b    — httpx.AsyncClient logged in as user_b
  user_a / user_b   — User objects for the two test users
  encrypt_key       — test Fernet key (bytes)
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

# Set env vars BEFORE importing the app to avoid fast-fail
TEST_ENCRYPT_KEY = Fernet.generate_key().decode()
os.environ.setdefault("RELAY_ENCRYPT_KEY", TEST_ENCRYPT_KEY)
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-tests-only-minimum-32chars")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from proxy.main import app  # noqa: E402
from proxy.db import session as db_session  # noqa: E402


@pytest.fixture(autouse=True)
def _set_test_env(tmp_path):
    """Each test gets its own isolated SQLite database."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    os.environ["DATABASE_URL"] = db_url
    # Reinitialise module-level engine
    db_session.engine = create_async_engine(
        db_url, connect_args={"check_same_thread": False}
    )
    yield
    os.environ.pop("DATABASE_URL", None)


@pytest_asyncio.fixture
async def db_tables():
    """Create all tables in the test database."""
    async with db_session.engine.begin() as conn:
        from proxy.db.models import BackendConfig, ProxyKey, UsageRecord, User  # noqa: F401
        await conn.run_sync(SQLModel.metadata.create_all)


@pytest.fixture
def encrypt_key() -> bytes:
    return os.environ["RELAY_ENCRYPT_KEY"].encode()


@pytest_asyncio.fixture
async def client(db_tables) -> AsyncGenerator[AsyncClient, None]:
    """Unauthenticated test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _register_and_login(
    client: AsyncClient, email: str, password: str
) -> tuple[dict, str]:
    """Register a user and return (user_dict, jwt_token)."""
    reg = await client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert reg.status_code == 201, reg.text
    user = reg.json()

    login = await client.post(
        "/auth/jwt/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return user, token


@pytest_asyncio.fixture
async def user_a_client(client) -> AsyncGenerator[tuple[dict, str, AsyncClient], None]:
    """(user_a dict, token_a, AsyncClient with auth header for user_a)."""
    user, token = await _register_and_login(
        client, "usera@example.com", "passwordA123"
    )
    client.headers.update({"Authorization": f"Bearer {token}"})
    yield user, token, client


@pytest_asyncio.fixture
async def two_users(db_tables) -> AsyncGenerator[tuple[dict, str, dict, str], None]:
    """Two separate async clients; returns (user_a, token_a, user_b, token_b)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ca:
        user_a, token_a = await _register_and_login(
            ca, "usera@example.com", "passwordA123"
        )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as cb:
        user_b, token_b = await _register_and_login(
            cb, "userb@example.com", "passwordB123"
        )
    yield user_a, token_a, user_b, token_b
