# Implementation Plan: Multi-User LLM Proxy

**Branch**: `002-multi-user-proxy` | **Date**: 2026-06-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-multi-user-proxy/spec.md`

## Summary

Evolve Relay from a single-operator proxy into a multi-user self-service
platform. Each user signs up, configures their own LLM backend credential
(encrypted at rest), creates proxy API keys, and sends requests through those
keys. The proxy identifies the key owner, decrypts their credential transiently,
forwards the request to their backend, and records usage against them. A
Vite+React+Mantine dashboard shows each user only their own usage. Deployed on
GCP e2-micro with Docker + Caddy for automatic HTTPS.

Build order is security-first: auth → user_id scoping → migration of existing
endpoints → credential encryption → proxy key ownership + forwarding → UIs →
OAuth → deploy.

## Technical Context

**Language/Version**: Python 3.12 (proxy/API), Node 20 (dashboard build)

**Primary Dependencies** (Python):
- `fastapi` + `uvicorn[standard]` — ASGI framework (existing)
- `fastapi-users[sqlalchemy]` — self-hosted auth: signup, login, JWT/cookie sessions, password hashing
- `httpx` — async HTTP client for backend forwarding (existing)
- `sqlmodel` — SQLite ORM unifying SQLAlchemy + Pydantic (existing)
- `pyyaml` — YAML config (existing, used for cost rates)
- `tiktoken` — token estimation fallback (existing)
- `cryptography` — Fernet authenticated symmetric encryption for provider credentials
- `aiosqlite` — async SQLite driver (existing)
- `python-multipart` — form data for FastAPI-Users (existing)

**Primary Dependencies** (Node / dashboard):
- `vite` + `react` + `@mantine/core` + `@mantine/hooks` + `recharts` (existing)
- `@mantine/form` — form state management for login/signup/settings forms
- `react-router-dom` — client-side routing for auth-gated pages

**Optional / later**:
- `httpx-oauth` — OAuth 2.0 providers (GitHub, Google) — Phase 7 only

**Storage**: SQLite via SQLModel + aiosqlite (persistent on VM disk). Scale-up
path: PostgreSQL / Cloud SQL with no application code changes (SQLAlchemy dialect
swap).

**Testing**: `pytest` + `pytest-asyncio`; `httpx.AsyncClient` against the FastAPI
app; in-memory SQLite for unit and integration tests.

**Target Platform**: GCP e2-micro (US region, always-free tier), Linux container,
Docker + Caddy (automatic HTTPS via Let's Encrypt on a subdomain).

**Project Type**: Web service (multi-user proxy + REST API) + client-side SPA
(dashboard with auth screens)

**Performance Goals**: Adds <5 ms overhead to non-streaming requests; streaming
latency matches backend (no buffering); dashboard responsive for ≤ 10k records
per user.

**Constraints**:
- Encryption key supplied via environment variable / systemd secret — never
  stored in DB or committed to repo.
- SQLite file and encryption key reside on VM persistent disk.
- Provider credentials NEVER appear in logs, error bodies, or API responses
  beyond masked form (last 4 chars).
- Every non-user DB table has a `user_id` FK; every query filters by
  authenticated `user_id`.

**Scale/Scope**: Multi-user self-service; v1 single-node; weekend-to-weeks
project scope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Single Purpose | Features serve proxying, user identity, usage metering, or user-scoped reporting | ✅ Pass |
| II. Multi-Tenant Isolation & Credential Security | user_id FK on every table; shared scoping dependency; Fernet encrypt-at-rest; masked display; transient decrypt at forward time; cross-user tests | ✅ Pass |
| III. Minimal Dependencies | Each new dep justified: fastapi-users (auth correctness), cryptography (encryption correctness), react-router-dom (SPA routing), @mantine/form (form UX) | ✅ Pass |
| IV. Observability | estimated flag kept; all stats queries filter by user_id | ✅ Pass |
| V. Backend-Agnostic Core | BackendAdapter protocol unchanged; per-user config injected at call site, not inside adapters | ✅ Pass |
| VI. Testable Units | forwarding, token counting, cost calc, isolation enforcement, credential encrypt/decrypt + masking — all unit-testable without live LLM | ✅ Pass |
| VII. Runnable in One Command | `docker compose up` (Caddy + proxy); documented in README | ✅ Pass |

**Post-design re-check**: Confirmed — see data-model.md and contracts/. The
`current_user` FastAPI dependency injects `user_id`; every data-access function
accepts it as a required argument so omission is a type error, not a runtime
surprise.

## Project Structure

### Documentation (this feature)

```text
specs/002-multi-user-proxy/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── auth-api.md
│   ├── proxy-api.md
│   ├── settings-api.md
│   └── stats-api.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
proxy/
├── __init__.py
├── main.py               # FastAPI app, lifespan, router mounts, Caddy trust
├── config.py             # Settings: load config.yml + env vars (RELAY_ENCRYPT_KEY etc.)
├── auth.py               # FastAPI-Users setup: User model, UserManager, JWT backend
├── crypto.py             # Fernet encrypt/decrypt; mask_credential(); never logs keys
├── deps.py               # Shared FastAPI dependencies: get_current_user, scoped_session
├── backends/
│   ├── __init__.py
│   ├── base.py           # BackendAdapter protocol, UsageData (unchanged from v1)
│   ├── openai_compat.py  # OpenAI-compatible adapter (base_url + api_key injected per-request)
│   └── ollama.py         # Ollama adapter (base_url injected per-request)
├── db/
│   ├── __init__.py
│   ├── models.py         # All SQLModel tables: User (FastAPI-Users), ProxyKey,
│   │                     #   BackendConfig, UsageRecord, CostRate
│   │                     #   — user_id FK on all non-User tables
│   └── session.py        # Async engine, session factory (unchanged)
├── metering.py           # compute_cost(), estimate_tokens_tiktoken() (unchanged)
├── routers/
│   ├── __init__.py
│   ├── proxy.py          # /v1/* — auth by proxy key, per-user backend lookup + decrypt
│   ├── stats.py          # /stats/* — auth by JWT session, user-scoped queries
│   ├── keys.py           # /api/keys — CRUD for user's own proxy keys
│   └── credentials.py    # /api/credentials — store/update/display masked backend config
└── tests/
    ├── conftest.py        # Fixtures: test app, two test users, in-memory SQLite, seeded data
    ├── test_auth.py       # Signup, login, token validation
    ├── test_isolation.py  # Cross-user access attempts — all MUST return 403/404
    ├── test_credentials.py# Encrypt/decrypt round-trip; masking; key never in any response
    ├── test_proxy.py      # Proxy path: key lookup, backend dispatch, usage recording
    ├── test_metering.py   # compute_cost, tiktoken estimation (unchanged)
    └── test_stats.py      # User-scoped aggregations

dashboard/
├── index.html
├── vite.config.ts
├── src/
│   ├── main.tsx          # MantineProvider + RouterProvider
│   ├── App.tsx           # Route layout; redirects unauthenticated users to /login
│   ├── api.ts            # fetch wrappers: auth, stats, keys, credentials
│   ├── auth.tsx          # AuthContext: current user, login/logout helpers
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── SignupPage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── KeysPage.tsx
│   │   └── CredentialsPage.tsx
│   ├── components/
│   │   ├── SummaryCards.tsx
│   │   ├── CostChart.tsx
│   │   ├── BreakdownTable.tsx
│   │   ├── RequestLog.tsx
│   │   ├── ProxyKeyList.tsx
│   │   └── BackendCredentialForm.tsx
│   └── types.ts
└── dist/

Caddyfile                 # Caddy reverse-proxy: HTTPS + forward to proxy:8000
docker-compose.yml        # proxy + Caddy; RELAY_ENCRYPT_KEY via environment
Dockerfile                # Multi-stage: Node build + Python runtime (unchanged structure)
config.yml.example        # Operator cost rates only (no user credentials)
README.md
pyproject.toml
```

**Structure Decision**: Extended v1 layout. Two new isolated modules:
`proxy/crypto.py` (encrypt/decrypt/mask — never imported near logging paths) and
`proxy/deps.py` (shared user_id injection — makes omitting the filter a type
error). Dashboard gains `auth.tsx` context and `pages/` for auth-gated routing.

## Complexity Tracking

> Justified additions beyond the v1 structure:

| Addition | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|--------------------------------------|
| `proxy/deps.py` | Centralises `get_current_user` so user_id injection is a required dep, not optional | Inline auth per route — easy to accidentally omit the user_id filter |
| `proxy/crypto.py` | Isolates encrypt/decrypt/mask from all logging and response-serialisation code | Inline Fernet in routers — accidental key exposure in error handlers becomes easy |
| `proxy/auth.py` | FastAPI-Users wiring is non-trivial; isolating it keeps main.py clean | Single-file auth — harder to test and harder to extend for OAuth later |
