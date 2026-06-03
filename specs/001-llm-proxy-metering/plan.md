# Implementation Plan: LLM Proxy with Usage Metering

**Branch**: `001-llm-proxy-metering` | **Date**: 2026-06-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-llm-proxy-metering/spec.md`

## Summary

Build Relay: a self-hosted HTTP proxy that accepts OpenAI-compatible
`/v1/chat/completions` requests, forwards them to a configured LLM backend
(OpenAI-compatible API or Ollama), and records token usage and computed cost per
request. A Vite+React dashboard reads a JSON stats API and displays spend by key
and model. The full stack starts with `docker compose up`.

Build priority: non-streaming proxy + token recording + minimal dashboard
against one backend first (shippable core), then second backend, then streaming.

## Technical Context

**Language/Version**: Python 3.12 (proxy/API), Node 20 (dashboard build)

**Primary Dependencies**:
- `fastapi` + `uvicorn` — ASGI web framework and server
- `httpx` — async HTTP client with streaming support (stdlib `http.client` lacks async)
- `sqlmodel` — SQLite ORM that unifies SQLAlchemy + Pydantic (less boilerplate than raw SQLAlchemy)
- `pyyaml` — YAML config parsing
- `tiktoken` — token estimation fallback (OpenAI tokenizer; stdlib has none)
- `vite` + `react` + `@mantine/core` + `recharts` — client-side dashboard; Mantine for layout/tables/cards, recharts for charting

**Storage**: SQLite via SQLModel (single file, zero-infra, appropriate for single-node)

**Testing**: `pytest` + `pytest-asyncio`; mock httpx transport for backend isolation

**Target Platform**: Linux container (Docker), also runs locally with Python 3.12+

**Project Type**: Web service (proxy) + client-side SPA (dashboard)

**Performance Goals**: Adds <5ms overhead to non-streaming requests; streaming
latency matches backend (no buffering)

**Constraints**: Single-node; no distributed storage; no auth beyond static API keys

**Scale/Scope**: Single developer, weekend project; supports up to 10k stored records
with dashboard remaining responsive

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Single Purpose | No feature outside proxying or metering | ✅ Pass |
| II. Minimal Dependencies | Each dep justified by capability gap | ✅ Pass |
| III. Observability | Exact-first tokens; `estimated` flag required | ✅ Pass |
| IV. Backend-Agnostic Core | Adapter interface; metering never imports backends | ✅ Pass |
| V. Testable Units | Forwarding, token counting, cost calc mockable without LLM | ✅ Pass |
| VI. Runnable in One Command | `docker compose up` documented in README | ✅ Pass |

**Post-design re-check**: Confirmed — see data-model.md and contracts/. Metering
logic in `proxy/metering.py` has zero backend imports; adapters in
`proxy/backends/` implement a single `BackendAdapter` protocol.

## Project Structure

### Documentation (this feature)

```text
specs/001-llm-proxy-metering/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── proxy-api.md
│   └── stats-api.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
proxy/                        # Python package — the FastAPI proxy service
├── __init__.py
├── main.py                   # FastAPI app, lifespan, mounts dashboard static
├── config.py                 # Pydantic settings loaded from config.yml / env
├── auth.py                   # API key validation (static lookup)
├── metering.py               # Token counting + cost calculation (no backend imports)
├── backends/
│   ├── __init__.py
│   ├── base.py               # BackendAdapter protocol / abstract base
│   ├── openai_compat.py      # OpenAI-compatible HTTP adapter
│   └── ollama.py             # Ollama adapter
├── db/
│   ├── __init__.py
│   ├── models.py             # SQLModel table definitions
│   └── session.py            # Engine / session factory
├── routers/
│   ├── __init__.py
│   ├── proxy.py              # POST /v1/chat/completions
│   └── stats.py              # GET /stats/* endpoints
└── tests/
    ├── test_metering.py      # Unit: token counting + cost calc
    ├── test_auth.py          # Unit: key validation
    ├── test_proxy.py         # Unit: forwarding with mock httpx transport
    └── test_stats.py         # Unit: aggregation queries against in-memory SQLite

dashboard/                    # Vite + React + Mantine UI SPA
├── index.html
├── vite.config.ts
├── src/
│   ├── main.tsx              # MantineProvider + RouterProvider setup
│   ├── App.tsx               # AppShell layout (navbar + main content)
│   ├── api.ts                # fetch wrappers for /stats endpoints
│   ├── components/
│   │   ├── SummaryCards.tsx  # Mantine Card + Grid for totals
│   │   ├── CostChart.tsx     # recharts LineChart inside Mantine Card
│   │   ├── BreakdownTable.tsx # Mantine Table for per-key / per-model
│   │   └── RequestLog.tsx    # Mantine Table (scrollable) + pagination
│   └── types.ts
└── dist/                     # Built output (served as static by FastAPI)

config.yml                    # Operator config: backend, api_keys, cost_rates
docker-compose.yml
Dockerfile
README.md
pyproject.toml
```

**Structure Decision**: Web-service layout with proxy and dashboard as sibling
top-level directories. Dashboard is a separate Vite + React + Mantine project
built to `dashboard/dist/` and served as FastAPI static files — no separate
dashboard server needed. Mantine handles layout/tables/cards; recharts handles
the time-series chart.

## Complexity Tracking

> No constitution violations requiring justification.
