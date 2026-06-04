"""
proxy/deps.py

Shared FastAPI dependencies for Relay.

Making user_id a required argument to all data-access functions means the
type checker catches omissions at development time — omitting the filter is a
type error, not a silent runtime bug.
"""

from __future__ import annotations

import os

from fastapi import Depends, HTTPException, status

from proxy.auth import current_active_user
from proxy.db.models import User
from proxy.db.session import get_session_dep  # re-exported for convenience

__all__ = ["get_current_user", "get_session_dep", "get_encrypt_key"]


async def get_current_user(user: User = Depends(current_active_user)) -> User:
    """Yield the authenticated User; raises 401 if not authenticated."""
    return user


def get_encrypt_key() -> bytes:
    """Return the Fernet encryption key from the environment.

    Raises 500 at request time if the env var is missing — this prevents
    silently operating without encryption.
    """
    key = os.environ.get("RELAY_ENCRYPT_KEY")
    if not key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Encryption key not configured",
        )
    return key.encode()
