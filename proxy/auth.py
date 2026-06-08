"""
proxy/auth.py

FastAPI-Users wiring for Relay.

Exposes:
  fastapi_users  — FastAPIUsers instance for router inclusion
  current_active_user  — dependency yielding the authenticated User
  get_user_db    — dependency yielding the SQLAlchemy user DB adapter
  get_user_manager — dependency yielding the UserManager

Auth backends (a user may authenticate via either):
  auth_backend     — JWT bearer (Authorization: Bearer …), used by password
                     login and programmatic API clients.
  cookie_backend   — httpOnly session cookie, used by the OAuth sign-in flow
                     (the provider callback can't hand a bearer token to the
                     SPA, so it sets a cookie the browser sends automatically).

OAuth clients (None when the provider's env vars are unset, so the routers
are only mounted when real credentials are configured):
  google_oauth_client
  github_oauth_client

Auth routers to include in main.py:
  fastapi_users.get_auth_router(auth_backend)   → /auth/jwt/login, /auth/jwt/logout
  fastapi_users.get_register_router(...)        → /auth/register
  fastapi_users.get_users_router(...)           → /auth/me (GET/PATCH)
  fastapi_users.get_oauth_router(...)           → /auth/{provider}/authorize, /callback
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
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlmodel.ext.asyncio.session import AsyncSession

from proxy.db.models import OAuthAccount, User
from proxy.db.session import get_session_dep


# ---------------------------------------------------------------------------
# UserDatabase dependency
# ---------------------------------------------------------------------------

async def get_user_db(
    session: AsyncSession = Depends(get_session_dep),
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    # Passing OAuthAccount enables FastAPI-Users' OAuth association logic.
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


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
# Shared JWT strategy
# ---------------------------------------------------------------------------

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


# ---------------------------------------------------------------------------
# JWT Bearer backend (password login, programmatic clients)
# ---------------------------------------------------------------------------

bearer_transport = BearerTransport(tokenUrl="/auth/jwt/login")

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)


# ---------------------------------------------------------------------------
# Cookie backend (OAuth sign-in flow)
# ---------------------------------------------------------------------------

# cookie_secure is False in dev (http://localhost) and True in prod (https).
# RELAY_COOKIE_SECURE lets the deployment force it on; otherwise we infer from
# whether the public base looks like https.
_COOKIE_SECURE = os.environ.get("RELAY_COOKIE_SECURE", "").lower() in {"1", "true", "yes"}

cookie_transport = CookieTransport(
    cookie_name="relay_session",
    cookie_max_age=3600,
    cookie_secure=_COOKIE_SECURE,
    cookie_httponly=True,
    cookie_samesite="lax",
)

cookie_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)


# ---------------------------------------------------------------------------
# OAuth cookie backend
#
# The OAuth callback is hit by a full browser navigation, so its success
# response must *redirect* the browser back into the SPA — a 204 (the default
# CookieTransport response, fine for the XHR-based password login) leaves the
# browser stranded on the provider callback URL. This transport sets the same
# session cookie but returns a 302 to the dashboard. We use a separate backend
# so the password-login cookie route keeps returning 204.
# ---------------------------------------------------------------------------

OAUTH_SUCCESS_REDIRECT = os.environ.get("RELAY_OAUTH_REDIRECT", "/app")


class RedirectCookieTransport(CookieTransport):
    async def get_login_response(self, token: str):
        from fastapi.responses import RedirectResponse

        # 303 so the browser issues a GET to the SPA route after the callback.
        response = RedirectResponse(url=OAUTH_SUCCESS_REDIRECT, status_code=303)
        return self._set_login_cookie(response, token)


oauth_cookie_transport = RedirectCookieTransport(
    cookie_name="relay_session",
    cookie_max_age=3600,
    cookie_secure=_COOKIE_SECURE,
    cookie_httponly=True,
    cookie_samesite="lax",
)

oauth_cookie_backend = AuthenticationBackend(
    name="cookie",
    transport=oauth_cookie_transport,
    get_strategy=get_jwt_strategy,
)


# ---------------------------------------------------------------------------
# OAuth clients — only constructed when credentials are present
# ---------------------------------------------------------------------------

def _build_oauth_clients():
    """Return (google_client, github_client); each is None when unconfigured."""
    google = None
    github = None

    g_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    g_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if g_id and g_secret:
        from httpx_oauth.clients.google import GoogleOAuth2

        google = GoogleOAuth2(g_id, g_secret)

    gh_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID")
    gh_secret = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET")
    if gh_id and gh_secret:
        from httpx_oauth.clients.github import GitHubOAuth2

        github = GitHubOAuth2(gh_id, gh_secret)

    return google, github


google_oauth_client, github_oauth_client = _build_oauth_clients()

# State secret protects the OAuth `state` parameter against CSRF; reusing the
# JWT secret is fine since both are server-side signing secrets.
OAUTH_STATE_SECRET = SECRET


# ---------------------------------------------------------------------------
# FastAPIUsers instance — accepts EITHER backend for current_user
# ---------------------------------------------------------------------------

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager, [auth_backend, cookie_backend]
)

current_active_user = fastapi_users.current_user(active=True)
