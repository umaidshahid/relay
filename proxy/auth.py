"""
proxy/auth.py

FastAPI-Users wiring for Relay.

Exposes:
  fastapi_users  — FastAPIUsers instance for router inclusion
  current_active_user  — dependency yielding the authenticated User
  get_user_db    — dependency yielding the SQLAlchemy user DB adapter
  get_user_manager — dependency yielding the UserManager

Auth routers to include in main.py:
  fastapi_users.get_auth_router(auth_backend)   → /auth/jwt/login, /auth/jwt/logout
  fastapi_users.get_register_router(...)        → /auth/register
  fastapi_users.get_users_router(...)           → /auth/me (GET/PATCH)
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from typing import Optional

from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlmodel.ext.asyncio.session import AsyncSession

from proxy.db.models import User
from proxy.db.session import get_session_dep


# ---------------------------------------------------------------------------
# UserDatabase dependency
# ---------------------------------------------------------------------------

async def get_user_db(
    session: AsyncSession = Depends(get_session_dep),
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User)


# ---------------------------------------------------------------------------
# UserManager
# ---------------------------------------------------------------------------

SECRET = os.environ.get("JWT_SECRET", "CHANGE_ME_IN_PRODUCTION")


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)


# ---------------------------------------------------------------------------
# JWT Authentication Backend
# ---------------------------------------------------------------------------

bearer_transport = BearerTransport(tokenUrl="/auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# ---------------------------------------------------------------------------
# FastAPIUsers instance
# ---------------------------------------------------------------------------

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
