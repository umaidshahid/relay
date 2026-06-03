"""
proxy/main.py

FastAPI application entry point for Relay.

Lifespan:
  - Loads configuration from config.yml
  - Creates database tables if they don't exist
  - Stores config on app.state so routers can access it

Mounts:
  - /v1        → proxy router  (POST /v1/chat/completions)
  - /stats     → stats router  (GET  /stats/*)
  - /health    → inline health check
  - /dashboard → static dashboard build (dashboard/dist/)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from proxy.config import load_config
from proxy.db.session import create_db_and_tables

logger = logging.getLogger(__name__)

_DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    config = load_config()
    app.state.config = config
    await create_db_and_tables()
    logger.info(
        "Relay started — backend=%s base_url=%s",
        config.backend.type,
        config.backend.base_url,
    )
    yield
    # Shutdown (nothing to clean up)


app = FastAPI(
    title="Relay",
    description="Self-hosted LLM proxy with usage metering",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Import and include routers after app is defined to avoid circular imports
from proxy.routers import proxy as proxy_router  # noqa: E402
from proxy.routers import stats as stats_router  # noqa: E402

app.include_router(proxy_router.router, prefix="/v1")
app.include_router(stats_router.router, prefix="/stats")

# Serve the compiled dashboard at /dashboard/
# html=True means index.html is served for unknown paths (SPA routing)
if _DASHBOARD_DIR.exists():
    app.mount(
        "/dashboard",
        StaticFiles(directory=str(_DASHBOARD_DIR), html=True),
        name="dashboard",
    )
else:
    logger.warning(
        "Dashboard build not found at %s — run 'npm run build' in dashboard/",
        _DASHBOARD_DIR,
    )
