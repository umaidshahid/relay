"""
proxy/tests/test_credentials.py

Tests for credential encryption, masking, and the /api/credentials endpoint.
"""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient

from proxy.crypto import decrypt_credential, encrypt_credential, mask_credential
from proxy.main import app


# ---------------------------------------------------------------------------
# Unit tests for crypto.py
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_roundtrip():
    key = Fernet.generate_key()
    plaintext = "sk-openai-supersecret"
    assert decrypt_credential(encrypt_credential(plaintext, key), key) == plaintext


def test_mask_credential_last_four():
    assert mask_credential("sk-openai-1234abcd") == "****abcd"


def test_mask_credential_short():
    assert mask_credential("abc") == "****abc"


def test_mask_credential_empty():
    assert mask_credential("") == "****"


def test_encrypt_does_not_store_plaintext():
    key = Fernet.generate_key()
    plaintext = "sk-secret-value"
    ciphertext = encrypt_credential(plaintext, key)
    assert plaintext not in ciphertext


# ---------------------------------------------------------------------------
# Integration tests for /api/credentials (list-based API)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_credentials_empty(user_a_client):
    _, token, client = user_a_client
    resp = await client.get("/api/credentials", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_credential_returns_masked(user_a_client):
    _, token, client = user_a_client
    resp = await client.post(
        "/api/credentials",
        json={
            "name": "My OpenAI",
            "backend_type": "openai_compat",
            "base_url": "https://api.openai.com/v1",
            "credential": "sk-abc1234567890",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "credential" not in data
    assert data["credential_masked"].endswith("7890")
    assert data["name"] == "My OpenAI"


@pytest.mark.asyncio
async def test_create_multiple_credentials(user_a_client):
    _, token, client = user_a_client
    for name in ["OpenAI", "Ollama"]:
        await client.post(
            "/api/credentials",
            json={"name": name, "backend_type": "openai_compat", "base_url": "https://example.com/v1"},
            headers={"Authorization": f"Bearer {token}"},
        )
    resp = await client.get("/api/credentials", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_delete_credential(user_a_client):
    _, token, client = user_a_client
    create = await client.post(
        "/api/credentials",
        json={"name": "Temp", "backend_type": "openai_compat", "base_url": "https://example.com/v1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cred_id = create.json()["id"]
    del_resp = await client.delete(f"/api/credentials/{cred_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_resp.status_code == 204
    list_resp = await client.get("/api/credentials", headers={"Authorization": f"Bearer {token}"})
    assert all(c["id"] != cred_id for c in list_resp.json())


@pytest.mark.asyncio
async def test_delete_credential_with_active_key_returns_409(user_a_client):
    _, token, client = user_a_client
    cred = (await client.post(
        "/api/credentials",
        json={"name": "Backend", "backend_type": "openai_compat", "base_url": "https://example.com/v1"},
        headers={"Authorization": f"Bearer {token}"},
    )).json()

    await client.post(
        "/api/keys",
        json={"label": "test", "backend_config_id": cred["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.delete(f"/api/credentials/{cred['id']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_credentials_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/credentials")
    assert resp.status_code == 401
