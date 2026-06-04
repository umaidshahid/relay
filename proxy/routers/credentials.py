"""
proxy/routers/credentials.py

Backend credential management (JWT-authenticated, user-scoped).

Users can have multiple named backend configs.

GET    /api/credentials              — list all user's backends (masked)
POST   /api/credentials              — add a new backend
PATCH  /api/credentials/{id}         — update name/url/credential
DELETE /api/credentials/{id}         — remove a backend
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from proxy.crypto import encrypt_credential
from proxy.db.models import BackendConfig, ProxyKey, User
from proxy.deps import get_current_user, get_encrypt_key, get_session_dep

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreateCredentialRequest(BaseModel):
    name: str
    backend_type: str          # "openai_compat" | "ollama"
    base_url: str
    credential: Optional[str] = None


class UpdateCredentialRequest(BaseModel):
    name: Optional[str] = None
    backend_type: Optional[str] = None
    base_url: Optional[str] = None
    credential: Optional[str] = None  # None = keep existing


class CredentialResponse(BaseModel):
    id: uuid.UUID
    name: str
    backend_type: str
    base_url: str
    credential_masked: Optional[str]
    updated_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _masked(suffix: Optional[str]) -> Optional[str]:
    return f"****{suffix}" if suffix else None


def _validate_type(t: str) -> None:
    if t not in ("openai_compat", "ollama"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="backend_type must be 'openai_compat' or 'ollama'",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[CredentialResponse])
async def list_credentials(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session_dep),
) -> list[CredentialResponse]:
    result = await session.exec(
        select(BackendConfig)
        .where(BackendConfig.user_id == user.id)
        .order_by(BackendConfig.updated_at.desc())  # type: ignore[attr-defined]
    )
    configs = result.all()
    return [
        CredentialResponse(
            id=c.id,
            name=c.name,
            backend_type=c.backend_type,
            base_url=c.base_url,
            credential_masked=_masked(c.credential_suffix),
            updated_at=c.updated_at,
        )
        for c in configs
    ]


@router.post("", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    body: CreateCredentialRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session_dep),
    encrypt_key: bytes = Depends(get_encrypt_key),
) -> CredentialResponse:
    _validate_type(body.backend_type)

    ciphertext: Optional[str] = None
    suffix: Optional[str] = None
    if body.credential:
        ciphertext = encrypt_credential(body.credential, encrypt_key)
        suffix = body.credential[-4:] if len(body.credential) >= 4 else body.credential

    now = datetime.now(timezone.utc)
    config = BackendConfig(
        user_id=user.id,
        name=body.name,
        backend_type=body.backend_type,
        base_url=body.base_url,
        credential_ciphertext=ciphertext,
        credential_suffix=suffix,
        updated_at=now,
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)

    return CredentialResponse(
        id=config.id,
        name=config.name,
        backend_type=config.backend_type,
        base_url=config.base_url,
        credential_masked=_masked(suffix),
        updated_at=config.updated_at,
    )


@router.patch("/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: uuid.UUID,
    body: UpdateCredentialRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session_dep),
    encrypt_key: bytes = Depends(get_encrypt_key),
) -> CredentialResponse:
    result = await session.exec(
        select(BackendConfig).where(
            BackendConfig.id == credential_id,
            BackendConfig.user_id == user.id,
        )
    )
    config = result.first()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    if body.backend_type is not None:
        _validate_type(body.backend_type)
        config.backend_type = body.backend_type
    if body.name is not None:
        config.name = body.name
    if body.base_url is not None:
        config.base_url = body.base_url
    if body.credential is not None:
        config.credential_ciphertext = encrypt_credential(body.credential, encrypt_key)
        config.credential_suffix = body.credential[-4:] if len(body.credential) >= 4 else body.credential

    config.updated_at = datetime.now(timezone.utc)
    session.add(config)
    await session.commit()
    await session.refresh(config)

    return CredentialResponse(
        id=config.id,
        name=config.name,
        backend_type=config.backend_type,
        base_url=config.base_url,
        credential_masked=_masked(config.credential_suffix),
        updated_at=config.updated_at,
    )


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session_dep),
) -> None:
    result = await session.exec(
        select(BackendConfig).where(
            BackendConfig.id == credential_id,
            BackendConfig.user_id == user.id,
        )
    )
    config = result.first()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    # Check no active keys are using this backend
    keys_result = await session.exec(
        select(ProxyKey).where(
            ProxyKey.backend_config_id == credential_id,
            ProxyKey.is_active == True,  # noqa: E712
        )
    )
    if keys_result.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete: active proxy keys are using this backend. Revoke them first.",
        )

    await session.delete(config)
    await session.commit()
