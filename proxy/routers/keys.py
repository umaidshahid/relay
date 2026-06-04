"""
proxy/routers/keys.py

Proxy key management (JWT-authenticated, user-scoped).

GET    /api/keys          — list user's proxy keys
POST   /api/keys          — create a key (full value shown once)
PATCH  /api/keys/{id}     — update label, backend, or rate limit
DELETE /api/keys/{id}     — revoke
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from proxy.db.models import BackendConfig, ProxyKey, User
from proxy.deps import get_current_user, get_session_dep

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreateKeyRequest(BaseModel):
    label: Optional[str] = None
    backend_config_id: uuid.UUID
    requests_per_minute: Optional[int] = None


class UpdateKeyRequest(BaseModel):
    label: Optional[str] = None
    backend_config_id: Optional[uuid.UUID] = None
    requests_per_minute: Optional[int] = None


class KeyResponse(BaseModel):
    id: uuid.UUID
    label: Optional[str]
    display: str
    is_active: bool
    created_at: datetime
    backend_config_id: Optional[uuid.UUID]
    backend_name: Optional[str]
    requests_per_minute: Optional[int]


class CreateKeyResponse(KeyResponse):
    key: str  # full plaintext — shown exactly once


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def _display(prefix: str, suffix: str) -> str:
    return f"{prefix}...{suffix}"


async def _get_backend(
    session: AsyncSession, backend_config_id: uuid.UUID, user_id: uuid.UUID
) -> BackendConfig:
    result = await session.exec(
        select(BackendConfig).where(
            BackendConfig.id == backend_config_id,
            BackendConfig.user_id == user_id,
        )
    )
    bc = result.first()
    if bc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backend not found or does not belong to you",
        )
    return bc


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[KeyResponse])
async def list_keys(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session_dep),
) -> list[KeyResponse]:
    result = await session.exec(
        select(ProxyKey)
        .where(ProxyKey.user_id == user.id, ProxyKey.is_active == True)  # noqa: E712
        .order_by(ProxyKey.created_at.desc())  # type: ignore[attr-defined]
    )
    keys = result.all()

    # Fetch backend names in one query
    bc_ids = {k.backend_config_id for k in keys if k.backend_config_id}
    bc_map: dict[uuid.UUID, str] = {}
    if bc_ids:
        bc_result = await session.exec(
            select(BackendConfig).where(BackendConfig.id.in_(bc_ids))  # type: ignore[attr-defined]
        )
        bc_map = {bc.id: bc.name for bc in bc_result.all()}

    return [
        KeyResponse(
            id=k.id,
            label=k.label,
            display=_display(k.key_prefix, k.key_suffix),
            is_active=k.is_active,
            created_at=k.created_at,
            backend_config_id=k.backend_config_id,
            backend_name=bc_map.get(k.backend_config_id) if k.backend_config_id else None,
            requests_per_minute=k.requests_per_minute,
        )
        for k in keys
    ]


@router.post("", response_model=CreateKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    body: CreateKeyRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session_dep),
) -> CreateKeyResponse:
    bc = await _get_backend(session, body.backend_config_id, user.id)

    plaintext = "sk-relay-" + secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    proxy_key = ProxyKey(
        user_id=user.id,
        backend_config_id=bc.id,
        key_hash=_hash_key(plaintext),
        key_prefix=plaintext[:8],
        key_suffix=plaintext[-4:],
        label=body.label,
        is_active=True,
        created_at=now,
        requests_per_minute=body.requests_per_minute,
    )
    # Capture all fields before commit (avoids lazy-load after session expires)
    bc_id = bc.id
    bc_name = bc.name
    key_id = proxy_key.id
    key_label = proxy_key.label
    key_prefix = proxy_key.key_prefix
    key_suffix = proxy_key.key_suffix
    key_rpm = proxy_key.requests_per_minute

    session.add(proxy_key)
    await session.commit()

    return CreateKeyResponse(
        id=key_id,
        label=key_label,
        key=plaintext,
        display=_display(key_prefix, key_suffix),
        is_active=True,
        created_at=now,
        backend_config_id=bc_id,
        backend_name=bc_name,
        requests_per_minute=key_rpm,
    )


@router.patch("/{key_id}", response_model=KeyResponse)
async def update_key(
    key_id: uuid.UUID,
    body: UpdateKeyRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session_dep),
) -> KeyResponse:
    result = await session.exec(
        select(ProxyKey).where(
            ProxyKey.id == key_id,
            ProxyKey.user_id == user.id,
            ProxyKey.is_active == True,  # noqa: E712
        )
    )
    proxy_key = result.first()
    if proxy_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")

    backend_name: Optional[str] = None
    if body.backend_config_id is not None:
        bc = await _get_backend(session, body.backend_config_id, user.id)
        proxy_key.backend_config_id = bc.id
        backend_name = bc.name
    else:
        if proxy_key.backend_config_id:
            bc_result = await session.exec(
                select(BackendConfig).where(BackendConfig.id == proxy_key.backend_config_id)
            )
            bc_obj = bc_result.first()
            backend_name = bc_obj.name if bc_obj else None

    if body.label is not None:
        proxy_key.label = body.label
    if body.requests_per_minute is not None:
        proxy_key.requests_per_minute = body.requests_per_minute

    session.add(proxy_key)
    await session.commit()
    await session.refresh(proxy_key)

    return KeyResponse(
        id=proxy_key.id,
        label=proxy_key.label,
        display=_display(proxy_key.key_prefix, proxy_key.key_suffix),
        is_active=proxy_key.is_active,
        created_at=proxy_key.created_at,
        backend_config_id=proxy_key.backend_config_id,
        backend_name=backend_name,
        requests_per_minute=proxy_key.requests_per_minute,
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(
    key_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session_dep),
) -> None:
    result = await session.exec(
        select(ProxyKey).where(
            ProxyKey.id == key_id,
            ProxyKey.user_id == user.id,
            ProxyKey.is_active == True,  # noqa: E712
        )
    )
    proxy_key = result.first()
    if proxy_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")

    proxy_key.is_active = False
    proxy_key.revoked_at = datetime.now(timezone.utc)
    session.add(proxy_key)
    await session.commit()
