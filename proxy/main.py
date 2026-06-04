"""
proxy/main.py

FastAPI application entry point for Relay (multi-user).

Lifespan:
  - Validates required environment variables (RELAY_ENCRYPT_KEY, JWT_SECRET)
  - Loads operator config from config.yml (cost rates)
  - Creates database tables if they don't exist

Mounts:
  /auth          → FastAPI-Users auth routers (register, login, logout, me)
  /api/keys      → proxy key management (JWT-auth)
  /api/credentials → backend credential management (JWT-auth)
  /v1            → proxy router (proxy-key-auth)
  /stats         → stats router (JWT-auth)
  /health        → inline health check
  /dashboard     → static dashboard build (dashboard/dist/)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi_users import schemas

from proxy.auth import auth_backend, fastapi_users
from proxy.config import load_config, validate_required_env
from proxy.db.models import User
from proxy.db.session import create_db_and_tables

logger = logging.getLogger(__name__)

_DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard" / "dist"


# ---------------------------------------------------------------------------
# FastAPI-Users schemas  (inline — simple enough to not need a separate file)
# ---------------------------------------------------------------------------

class UserRead(schemas.BaseUser[__import__("uuid").UUID]):
    pass


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_required_env()
    config = load_config()
    app.state.config = config
    await create_db_and_tables()
    logger.info("Relay started (multi-user mode)")
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Relay",
    description="Self-hosted multi-user LLM proxy with usage metering",
    version="2.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Auth routers (FastAPI-Users)
# ---------------------------------------------------------------------------

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/auth",
    tags=["auth"],
)


# ---------------------------------------------------------------------------
# API routers (JWT-authenticated)
# ---------------------------------------------------------------------------

from proxy.routers import credentials as credentials_router  # noqa: E402
from proxy.routers import keys as keys_router  # noqa: E402

app.include_router(keys_router.router, prefix="/api/keys", tags=["keys"])
app.include_router(
    credentials_router.router, prefix="/api/credentials", tags=["credentials"]
)


# ---------------------------------------------------------------------------
# Proxy + Stats routers
# ---------------------------------------------------------------------------

from proxy.routers import proxy as proxy_router  # noqa: E402
from proxy.routers import stats as stats_router  # noqa: E402

app.include_router(proxy_router.router, prefix="/v1", tags=["proxy"])
app.include_router(stats_router.router, prefix="/stats", tags=["stats"])


# ---------------------------------------------------------------------------
# Health + Dashboard
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


if _DASHBOARD_DIR.exists():
    from fastapi.responses import FileResponse

    # Static assets (JS, CSS, icons) served from /assets/*
    app.mount(
        "/assets",
        StaticFiles(directory=str(_DASHBOARD_DIR / "assets")),
        name="spa-assets",
    )

    # Catch-all: any path not already claimed by an API route serves index.html.
    # API routes (/v1, /auth, /api, /stats, /health) are all registered above
    # and take priority over this catch-all because FastAPI matches in order.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        return FileResponse(str(_DASHBOARD_DIR / "index.html"))

else:
    logger.warning(
        "Dashboard build not found at %s — run 'npm run build' in dashboard/",
        _DASHBOARD_DIR,
    )
