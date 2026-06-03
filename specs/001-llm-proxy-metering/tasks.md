---
description: "Task list for LLM Proxy with Usage Metering"
---

# Tasks: LLM Proxy with Usage Metering

**Input**: Design documents from `specs/001-llm-proxy-metering/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Build order** (per plan): Non-streaming core + dashboard (US1+US2) → Ollama backend (US3 part) → Streaming (US1 extension) → Cost config (US3)

---

## Phase 1: Setup

**Purpose**: Project scaffolding and shared tooling

- [x] T001 Create top-level directory structure: `proxy/`, `proxy/backends/`, `proxy/db/`, `proxy/routers/`, `proxy/tests/`, `dashboard/src/components/`
- [x] T002 Create `pyproject.toml` with dependencies: `fastapi`, `uvicorn[standard]`, `httpx`, `sqlmodel`, `pyyaml`, `tiktoken`, and dev deps `pytest`, `pytest-asyncio`, `httpx` (test transport)
- [x] T003 [P] Create `dashboard/package.json` with dependencies: `react`, `react-dom`, `@mantine/core`, `@mantine/hooks`, `@mantine/dates`, `recharts`, dev: `vite`, `@vitejs/plugin-react`, `typescript`
- [x] T004 [P] Create `dashboard/vite.config.ts` configuring React plugin and proxy for `/stats` → `http://localhost:8000` in dev mode
- [x] T005 [P] Create `dashboard/tsconfig.json` with strict TypeScript settings
- [x] T006 [P] Create `config.yml.example` with backend, api_keys, and cost_rates sections (per research.md §6 structure)
- [x] T007 [P] Create `.gitignore` covering `__pycache__`, `*.pyc`, `.venv`, `node_modules`, `dashboard/dist`, `*.db`, `.env`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure required before any user story can be implemented

**⚠️ CRITICAL**: No user story work begins until this phase is complete

- [x] T008 Create `proxy/config.py` — Pydantic `BaseSettings` class loading `config.yml`; exposes `BackendConfig`, list of `ApiKey`, dict of `CostRate`; supports `BACKEND_API_KEY` env override
- [x] T009 Create `proxy/db/models.py` — `UsageRecord` SQLModel table with all fields from data-model.md: `id`, `timestamp`, `api_key_label`, `backend`, `model`, `input_tokens`, `output_tokens`, `cost`, `token_count_source`, `status_code`; indexes on `timestamp`, `api_key_label`, `model`
- [x] T010 Create `proxy/db/session.py` — async SQLite engine, `AsyncSession` factory, `create_db_and_tables()` startup function
- [x] T011 Create `proxy/backends/base.py` — `BackendAdapter` Protocol with `chat_complete()` and `chat_complete_stream()` async methods; `UsageData` dataclass (`input_tokens`, `output_tokens`, `source: Literal["exact","estimated"]`)
- [x] T012 Create `proxy/metering.py` — `compute_cost(model, usage_data, rates) -> float`; `estimate_tokens_tiktoken(messages) -> UsageData` (cl100k_base fallback, source="estimated"); NO imports from `proxy/backends/`
- [x] T013 Create `proxy/auth.py` — `authenticate_key(authorization_header, api_keys) -> ApiKey | None`; pure function, no DB access
- [x] T014 Create `proxy/main.py` — FastAPI app with lifespan (DB init, config load); mount `dashboard/dist` as StaticFiles at `/dashboard`; include routers; `/health` endpoint

**Checkpoint**: Foundation ready — all three user story phases can now proceed

---

## Phase 3: User Story 1 — Transparent Proxy Pass-Through (Priority: P1) 🎯 MVP

**Goal**: Non-streaming chat-completion requests are forwarded to the OpenAI-compat
backend and the response is returned unchanged. Every completed request produces a
usage record in SQLite.

**Independent Test**: `curl` a non-streaming request to `POST /v1/chat/completions`
with a valid API key → receive a valid OpenAI-format response AND verify a row
appears in the SQLite DB with correct token counts and cost.

### Implementation for User Story 1

- [x] T015 [P] [US1] Create `proxy/backends/openai_compat.py` — `OpenAICompatAdapter` implementing `BackendAdapter`; non-streaming `chat_complete()`: POST to `{base_url}/chat/completions` via httpx, extract `usage.prompt_tokens` / `usage.completion_tokens` → `UsageData(source="exact")`; fall back to tiktoken if usage absent
- [x] T016 [US1] Create `proxy/routers/proxy.py` — `POST /v1/chat/completions` route: authenticate key (401 if missing/bad), select adapter from config, call `chat_complete()`, write `UsageRecord` to DB, return backend response unchanged
- [x] T017 [US1] Add `proxy/config.py` adapter-factory: given `BackendConfig.type`, return the correct `BackendAdapter` instance (only `openai_compat` needed at this phase)
- [x] T018 [P] [US1] Create `proxy/tests/test_metering.py` — unit tests: `compute_cost` with known rates, zero cost for unknown model, `estimate_tokens_tiktoken` returns source="estimated"
- [x] T019 [P] [US1] Create `proxy/tests/test_auth.py` — unit tests: valid key returns `ApiKey`, unknown key returns None, missing header returns None
- [x] T020 [US1] Create `proxy/tests/test_proxy.py` — unit tests using `httpx.MockTransport`: valid request → 200 + usage record written; invalid key → 401 + no record written; backend 500 → forwarded 502 + error record written with zero tokens

**Checkpoint**: US1 complete — non-streaming proxy works end-to-end, usage recorded

---

## Phase 4: User Story 2 — Usage & Cost Dashboard (Priority: P2)

**Goal**: Operator opens `http://localhost:8000/dashboard/` and sees total spend,
per-key breakdown, per-model breakdown, a time-series chart, and a request log.

**Independent Test**: With seed data in SQLite, `GET /stats/summary`, `/stats/by-key`,
`/stats/by-model`, `/stats/timeseries`, `/stats/requests` all return correct JSON.
Loading the dashboard URL renders without errors and displays the data.

### Implementation for User Story 2

- [x] T021 [US2] Create `proxy/routers/stats.py` — implement all five stats endpoints from contracts/stats-api.md: `GET /stats/summary`, `/stats/by-key`, `/stats/by-model`, `/stats/timeseries?days=N`, `/stats/requests?limit=N&offset=N`; all read from `UsageRecord` table via async queries
- [x] T022 [US2] Create `proxy/tests/test_stats.py` — unit tests against in-memory SQLite: seed 3 records across 2 keys and 2 models; assert summary totals, per-key/model breakdowns, timeseries buckets, and paginated request log
- [x] T023 [P] [US2] Create `dashboard/src/types.ts` — TypeScript interfaces matching all stats API response shapes from contracts/stats-api.md
- [x] T024 [P] [US2] Create `dashboard/src/api.ts` — typed `fetch` wrappers: `getSummary()`, `getByKey()`, `getByModel()`, `getTimeseries(days)`, `getRequests(limit, offset)`
- [x] T025 [P] [US2] Create `dashboard/src/components/SummaryCards.tsx` — Mantine `Grid` + `Card` displaying total cost, total requests, total input tokens, total output tokens from `/stats/summary`
- [x] T026 [P] [US2] Create `dashboard/src/components/CostChart.tsx` — recharts `LineChart` inside Mantine `Card` displaying daily cost from `/stats/timeseries`; defaults to last 30 days
- [x] T027 [P] [US2] Create `dashboard/src/components/BreakdownTable.tsx` — Mantine `Table` showing per-key and per-model breakdowns; two tabs or two sections on one page
- [x] T028 [P] [US2] Create `dashboard/src/components/RequestLog.tsx` — Mantine `Table` (scrollable) with pagination controls; marks `token_count_source="estimated"` rows with a visible indicator (e.g. `~` prefix on token counts)
- [x] T029 [US2] Create `dashboard/src/App.tsx` — Mantine `AppShell` layout wiring all components; loads data on mount via `api.ts`; empty-state handling when no records
- [x] T030 [US2] Create `dashboard/index.html` and `dashboard/src/main.tsx` with `MantineProvider` wrapping `App`
- [x] T031 [US2] Verify dashboard build: `npm run build` inside `dashboard/` produces `dist/` that FastAPI serves correctly at `/dashboard/`

**Checkpoint**: US2 complete — dashboard shows live data from the proxy's SQLite

---

## Phase 5: User Story 3a — Ollama Backend (Priority: P3, part 1)

**Goal**: Operator switches `config.yml` to `type: ollama` and requests are
forwarded to Ollama; token counts come from `prompt_eval_count` / `eval_count`.

**Independent Test**: Using `httpx.MockTransport` returning an Ollama-format JSON
response, verify `OllamaAdapter.chat_complete()` returns `UsageData` with
`source="exact"` and correct token counts.

### Implementation for User Story 3a

- [x] T032 [US3] Create `proxy/backends/ollama.py` — `OllamaAdapter` implementing `BackendAdapter`; non-streaming `chat_complete()`: POST to `{base_url}/api/chat`, map Ollama response to OpenAI-compat shape, extract `prompt_eval_count` → input tokens and `eval_count` → output tokens → `UsageData(source="exact")`; fall back to tiktoken if fields absent
- [x] T033 [US3] Update `proxy/config.py` adapter factory to return `OllamaAdapter` when `backend.type == "ollama"`
- [x] T034 [US3] Add Ollama adapter unit tests to `proxy/tests/test_proxy.py` — mock Ollama response shape, assert correct `UsageData` extraction and `UsageRecord` written

**Checkpoint**: US3a complete — Ollama backend usable with exact token counting

---

## Phase 6: User Story 3b — Configurable Per-Model Cost Rates (Priority: P3, part 2)

**Goal**: Operator adds/updates a model rate in `config.yml`, restarts the service,
and new requests are costed at the new rate. Requests for models with no rate get
`cost=0.0` and are clearly marked.

**Independent Test**: Change a rate in config, send a request, verify the recorded
cost in `/stats/requests` matches `input_tokens × new_input_rate + output_tokens × new_output_rate`.

### Implementation for User Story 3b

- [x] T035 [US3] Verify `proxy/metering.py` `compute_cost()` returns `0.0` when model has no configured rate (already required by data-model.md — confirm behavior is tested)
- [x] T036 [US3] Add test to `proxy/tests/test_metering.py` — request for unconfigured model: `cost=0.0`, record written, `token_count_source` still set correctly
- [x] T037 [US3] Add test to `proxy/tests/test_metering.py` — rate change scenario: assert that `compute_cost` uses the rate passed in (rates are read fresh from config at request time, not cached at startup)

**Checkpoint**: US3b complete — all three user stories independently functional

---

## Phase 7: User Story 1 Extension — Streaming Pass-Through

**Goal**: Requests with `"stream": true` are forwarded as SSE; tokens arrive at the
client in real time; usage is recorded from the final chunk's `usage` object.

**Independent Test**: Using `httpx.MockTransport` that yields chunked SSE data
(including a final chunk with `usage`), verify the proxy yields all chunks to the
caller and writes a `UsageRecord` with `source="exact"` after the stream ends.

### Implementation — Streaming

- [x] T038 [US1] Add `chat_complete_stream()` to `proxy/backends/openai_compat.py` — inject `stream_options: {include_usage: true}` into the forwarded request body; use `httpx.AsyncClient.stream()` to iterate SSE chunks; yield each `data:` line immediately; parse final chunk for `usage` → `UsageData(source="exact")`
- [x] T039 [US1] Add `chat_complete_stream()` to `proxy/backends/ollama.py` — Ollama streaming returns NDJSON; yield each line; final line contains `prompt_eval_count`/`eval_count` → `UsageData(source="exact")`
- [x] T040 [US1] Update `proxy/routers/proxy.py` — detect `"stream": true` in request body; use `chat_complete_stream()` returning FastAPI `StreamingResponse` with `media_type="text/event-stream"`; write `UsageRecord` after stream generator exhausted
- [x] T041 [US1] Add streaming unit tests to `proxy/tests/test_proxy.py` — mock SSE chunks via `httpx.MockTransport`; assert all chunks forwarded; assert `UsageRecord` written with correct token counts from final chunk; assert no buffering (record written only after last chunk)

**Checkpoint**: Streaming complete — all spec requirements met

---

## Phase 8: Packaging & Polish

**Purpose**: Docker packaging, README, and cross-cutting hardening

- [x] T042 [P] Create `Dockerfile` — multi-stage: Node 20 stage builds `dashboard/dist/`; Python 3.12 stage installs proxy deps and copies `dist/`; CMD runs `uvicorn proxy.main:app --host 0.0.0.0 --port 8000`
- [x] T043 [P] Create `docker-compose.yml` — `proxy` service (builds from Dockerfile, mounts `config.yml`, volume for `relay.db`); optional `ollama` service under `--profile ollama`
- [x] T044 Create `README.md` documenting: one-command start (`docker compose up`), `config.yml` structure, how to send a test request, dashboard URL — validates SC-006 (5-minute reviewer test)
- [x] T045 [P] Create `config.yml.example` with example OpenAI-compat and Ollama backend sections, two sample API keys, sample cost rates for `gpt-4o-mini` and `llama3`
- [x] T046 [P] Add `proxy/tests/test_stats.py` edge cases: empty DB returns zero totals; `timeseries` with `days=7` returns only last 7 days; `requests` pagination `offset` works correctly
- [x] T047 Run full test suite `pytest proxy/tests/` and fix any failures
- [x] T048 Smoke test: `docker compose up`, send a non-streaming request, load dashboard, verify request appears in log

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user story phases**
- **US1 / Phase 3**: Depends on Phase 2 — no dependency on US2 or US3
- **US2 / Phase 4**: Depends on Phase 2 — no dependency on US1 or US3
- **US3a / Phase 5**: Depends on Phase 2 — no dependency on US1 or US2
- **US3b / Phase 6**: Depends on Phase 5 (uses cost rates with the adapter)
- **Streaming / Phase 7**: Depends on Phase 3 (extends the proxy router and adapters)
- **Packaging / Phase 8**: Depends on all story phases complete

### User Story Dependencies

- **US1 (P1)**: Foundational complete → implement; no cross-story deps
- **US2 (P2)**: Foundational complete → implement; reads DB rows written by US1 but does not depend on US1 code
- **US3a (P3)**: Foundational complete → implement; adds a second adapter
- **US3b (P3)**: US3a complete → confirm cost logic; no new infra needed
- **Streaming**: US1 complete → extend proxy router and adapters

### Within Each Phase

- `[P]` tasks in same phase can run in parallel (different files, no shared state)
- Tests can be written before or alongside implementation (no TDD requirement stated)
- Models and config before services; services before routers

---

## Parallel Opportunities

```bash
# Phase 1 — all [P] tasks can run together:
T003 dashboard/package.json
T004 dashboard/vite.config.ts
T005 dashboard/tsconfig.json
T006 config.yml.example
T007 .gitignore

# Phase 3 — after T015 (adapter) done:
T018 proxy/tests/test_metering.py
T019 proxy/tests/test_auth.py

# Phase 4 — after T021 (stats router) done:
T023 dashboard/src/types.ts
T024 dashboard/src/api.ts
T025 dashboard/src/components/SummaryCards.tsx
T026 dashboard/src/components/CostChart.tsx
T027 dashboard/src/components/BreakdownTable.tsx
T028 dashboard/src/components/RequestLog.tsx
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational — CRITICAL, blocks everything
3. Complete Phase 3: US1 (non-streaming proxy, OpenAI-compat backend, usage recording)
4. Complete Phase 4: US2 (stats API + dashboard)
5. **STOP AND VALIDATE**: `curl` a request → check dashboard → confirm spend shown
6. Ship / demo

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → working proxy, records written → demo #1
3. US2 → dashboard live → demo #2 (core value proposition visible)
4. US3a → Ollama backend → demo #3
5. US3b → cost config verified → no separate demo needed
6. Streaming → fully spec-compliant → demo #4
7. Packaging → one-command Docker → final delivery

---

## Notes

- `[P]` = task touches different files from other `[P]` tasks in the same phase; safe to run in parallel
- `[USN]` maps each task to its user story for traceability
- Streaming (Phase 7) is intentionally last — it's the highest-risk piece and must not block the working core
- The `estimated` flag surface requirement (FR-009, Constitution §III) is enforced in T018 (metering unit test) and T028 (dashboard RequestLog marks estimated rows)
- No test tasks are marked as TDD prerequisites — add "write test first" instructions to individual tasks if TDD is desired during implementation
