# Tasks: Multi-User LLM Proxy

**Input**: Design documents from `specs/002-multi-user-proxy/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Exact file paths are included in all descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization — update pyproject.toml, add new dependencies, establish module skeleton.

- [X] T001 Add new Python dependencies to pyproject.toml: `fastapi-users[sqlalchemy]`, `cryptography`, `@mantine/form`, `react-router-dom`
- [X] T002 [P] Create `proxy/crypto.py` skeleton with stub functions: `encrypt_credential`, `decrypt_credential`, `mask_credential`
- [X] T003 [P] Create `proxy/deps.py` skeleton with stub `get_current_user` dependency
- [X] T004 [P] Create `proxy/auth.py` skeleton for FastAPI-Users wiring stubs
- [X] T005 [P] Create router stubs: `proxy/routers/keys.py` and `proxy/routers/credentials.py`

**Checkpoint**: All new module files exist; `import relay` succeeds.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story work begins — DB schema, auth wiring, isolation dependency, encryption module.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Extend `proxy/db/models.py`: add `User` (FastAPI-Users SQLAlchemyBaseUserTableUUID + SQLModel, table=True), `ProxyKey`, `BackendConfig`, `UsageRecord` with all fields and `user_id` FKs per data-model.md; add all indexes defined in data-model.md
- [X] T007 Update `proxy/db/session.py`: ensure async engine + session factory initialises all new tables via `SQLModel.metadata.create_all`
- [X] T008 Implement `proxy/crypto.py`: `encrypt_credential(plaintext, key) -> str` using Fernet, `decrypt_credential(ciphertext, key) -> str`, `mask_credential(plaintext) -> str` returning `****{last4}`; key sourced from `RELAY_ENCRYPT_KEY` env var; no key value ever logged
- [X] T009 Implement `proxy/auth.py`: FastAPI-Users `UserDatabase`, `UserManager`, `JWTStrategy(secret=JWT_SECRET, lifetime_seconds=3600)`, `BearerTransport`, `AuthenticationBackend`, `FastAPIUsers[User, UUID]`; expose `current_active_user` dependency and auth routers
- [X] T010 Implement `proxy/deps.py`: `get_current_user` wrapping FastAPI-Users `current_active_user`; `get_session_dep` yielding `AsyncSession`; `get_encrypt_key` reading `RELAY_ENCRYPT_KEY` from env
- [X] T011 Update `proxy/config.py`: add `JWT_SECRET` and `RELAY_ENCRYPT_KEY` env var loading; fail fast at startup if either is missing
- [X] T012 Update `proxy/main.py`: mount FastAPI-Users auth routers at `/auth`; mount `keys` router at `/api/keys`; mount `credentials` router at `/api/credentials`; add `trusted_host` / proxy-headers config for Caddy (`--proxy-headers`)
- [X] T013 Create `proxy/tests/conftest.py`: `test_app` fixture with in-memory SQLite, two test users (`user_a`, `user_b`), seeded ProxyKeys and BackendConfigs; `async_client` for each user with JWT auth headers; test encryption key fixture

**Checkpoint**: `pytest proxy/tests/conftest.py` collects fixtures without errors; app starts with required env vars.

---

## Phase 3: User Story 1 — Account Registration & Login (Priority: P1) 🎯 MVP

**Goal**: A visitor creates an account with email + password and logs in. Protected pages redirect unauthenticated visitors to `/login`. Second user cannot see first user's workspace.

**Independent Test**: POST `/auth/register` → 201; POST `/auth/jwt/login` → JWT; GET `/stats/summary` with JWT → 200 user-scoped; GET `/stats/summary` without JWT → 401; two separate users each see only their own dashboard.

### Implementation for User Story 1

- [X] T014 [US1] Verify FastAPI-Users register route at `POST /auth/register` matches contract in `contracts/auth-api.md`: 201 with `{id, email, is_active, is_superuser, is_verified}`; 400 on duplicate email; 422 on malformed body
- [X] T015 [US1] Verify FastAPI-Users login route at `POST /auth/jwt/login` matches contract: 200 `{access_token, token_type}`; 400 on bad credentials; form-encoded request body
- [X] T016 [US1] Verify `GET /auth/me` and `PATCH /auth/me` routes work with JWT bearer; confirm 401 on missing token
- [X] T017 [US1] Write `proxy/tests/test_auth.py`: signup happy path, duplicate-email 400, login happy path, wrong-password 400, `GET /auth/me` with and without JWT, session expiry / invalid-token 401
- [X] T018 [P] [US1] Scaffold `dashboard/src/auth.tsx`: `AuthContext` with `currentUser`, `login(email, password)`, `logout()` helpers; JWT stored in `localStorage`; `RequireAuth` wrapper component redirecting unauthenticated users to `/login`
- [X] T019 [P] [US1] Scaffold `dashboard/src/App.tsx`: `MantineProvider` + `RouterProvider`; routes `/login`, `/signup`, `/` (dashboard), `/keys`, `/credentials` — all except login/signup wrapped in `<RequireAuth>`
- [X] T020 [P] [US1] Implement `dashboard/src/pages/LoginPage.tsx`: `@mantine/form` form, `POST /auth/jwt/login` via `dashboard/src/api.ts`, store JWT, redirect to `/`
- [X] T021 [P] [US1] Implement `dashboard/src/pages/SignupPage.tsx`: `@mantine/form` form, `POST /auth/register`, then auto-login and redirect to `/`
- [X] T022 [US1] Update `dashboard/src/api.ts`: add `login(email, password)`, `register(email, password)`, `logout()`, `getMe()` wrappers; attach `Authorization: Bearer <token>` header to all authenticated requests
- [X] T023 [US1] Wire `dashboard/src/main.tsx`: `MantineProvider` + `AuthProvider` + `RouterProvider` in correct nesting order

**Checkpoint**: A new user can sign up via the dashboard form, log in, reach an (empty) dashboard, and log out. Unauthenticated navigation redirects to `/login`.

---

## Phase 4: User Story 2 — Proxy Key Management (Priority: P1)

**Goal**: Authenticated user creates proxy keys (full value shown once), views masked listing, and revokes keys. Keys from other users are never visible.

**Independent Test**: POST `/api/keys` → 201 with full `key` field; GET `/api/keys` → masked `display` only, no `key` field; DELETE `/api/keys/{id}` → 204; user B cannot see user A's keys (404 on cross-user key ID).

### Implementation for User Story 2

- [X] T024 [US2] Implement `proxy/routers/keys.py`: `GET /api/keys` — query `ProxyKey` filtered by `user_id`, return `{id, label, display, is_active, created_at}` list; `POST /api/keys` — generate `secrets.token_urlsafe(32)` prefixed `sk-relay-`, compute SHA-256 `key_hash`, store `key_prefix` (first 8 chars) and `key_suffix` (last 4), return full `key` exactly once + `display`; `DELETE /api/keys/{key_id}` — set `is_active=False`, `revoked_at=now()`, 404 if not found or wrong `user_id`
- [X] T025 [US2] Write `proxy/tests/test_isolation.py` (partial — keys section): register two users; user A creates key; user B lists keys → sees zero of user A's keys; user B attempts DELETE on user A's key ID → 404
- [X] T026 [P] [US2] Implement `dashboard/src/pages/KeysPage.tsx`: fetch and display key list (`GET /api/keys`); "Create Key" button triggers `POST /api/keys`, shows full key in one-time modal/alert, then refreshes masked listing; "Revoke" button triggers `DELETE /api/keys/{id}`
- [X] T027 [P] [US2] Implement `dashboard/src/components/ProxyKeyList.tsx`: table showing `label`, `display` (masked), `created_at`, revoke button; never shows full key
- [X] T028 [US2] Add `POST /api/keys` and `DELETE /api/keys/{key_id}` and `GET /api/keys` wrappers to `dashboard/src/api.ts`
- [X] T029 [US2] Write `proxy/tests/test_isolation.py` (complete): add cross-user checks for all data endpoints — ensure every protected endpoint returns 403 or 404 when user B supplies user A's resource IDs

**Checkpoint**: User can create, list (masked), and revoke their own proxy keys. Cross-user isolation confirmed by tests.

---

## Phase 5: User Story 3 — Backend Credential Configuration (Priority: P1)

**Goal**: Authenticated user configures their LLM backend (OpenAI-compat or Ollama). Credentials stored encrypted; only masked form returned. Other users cannot see or read this credential.

**Independent Test**: `PUT /api/credentials` → 200 with `credential_masked`; `GET /api/credentials` → masked only, no plaintext; user B cannot access user A's credential config; credential can be replaced.

### Implementation for User Story 3

- [X] T030 [US3] Implement `proxy/routers/credentials.py`: `GET /api/credentials` — query `BackendConfig` by `user_id`, return `{backend_type, base_url, credential_masked, updated_at}` or `null`; `PUT /api/credentials` — encrypt `credential` with `RELAY_ENCRYPT_KEY` via `crypto.encrypt_credential`, store `credential_ciphertext` and `credential_suffix` (last 4 of plaintext), upsert row (UNIQUE on `user_id`), return masked response; `DELETE /api/credentials` — delete row, 204; full credential NEVER echoed in any response
- [X] T031 [US3] Extend `proxy/tests/test_isolation.py`: user B cannot GET user A's credential config (should see `null` or their own, not user A's)
- [X] T032 [US3] Write `proxy/tests/test_credentials.py`: encrypt/decrypt round-trip; `mask_credential` returns `****{last4}`; `PUT /api/credentials` stores ciphertext (not plaintext); `GET /api/credentials` response contains no `credential` field; update replaces old config; `DELETE` removes config
- [X] T033 [P] [US3] Implement `dashboard/src/pages/CredentialsPage.tsx`: show current masked credential (or "not configured"); `@mantine/form` form for `backend_type`, `base_url`, `credential`; submit triggers `PUT /api/credentials`; response shows `credential_masked`; never display full key
- [X] T034 [P] [US3] Implement `dashboard/src/components/BackendCredentialForm.tsx`: controlled form component; `backend_type` select (`openai_compat` | `ollama`); `base_url` text input; `credential` password input (nullable for Ollama); submit handler
- [X] T035 [US3] Add `getCredentials()`, `putCredentials(payload)`, `deleteCredentials()` wrappers to `dashboard/src/api.ts`

**Checkpoint**: User can configure and replace their LLM backend credential. Credential appears masked everywhere; plaintext confirmed absent from all responses and DB by tests.

---

## Phase 6: User Story 4 — Proxied Chat-Completion Requests (Priority: P1)

**Goal**: Application sends a chat-completion request with user's proxy key. Proxy identifies owner, decrypts their credential, forwards to their backend, records usage. Streaming works without buffering.

**Independent Test**: `POST /v1/chat/completions` with valid proxy key → response forwarded; usage row created scoped to key owner; revoked key → 401; missing backend → 400; two users' requests go to their respective backends.

### Implementation for User Story 4

- [X] T036 [US4] Implement proxy key lookup in `proxy/routers/proxy.py`: `get_user_by_proxy_key(key, session)` — SHA-256 hash key, `SELECT User JOIN ProxyKey WHERE key_hash=? AND is_active=True`; return `User` or raise 401; used as a FastAPI dependency for all `/v1/*` routes
- [X] T037 [US4] Implement `GET /v1/models` in `proxy/routers/proxy.py`: load user's `BackendConfig`; if Ollama, fetch `/api/tags` and convert to OpenAI model list shape; if openai_compat, proxy `GET /models` upstream; inject decrypted credential transiently; 401 on bad key, 400 on no backend, 503 on unreachable backend
- [X] T038 [US4] Implement `POST /v1/chat/completions` (non-streaming) in `proxy/routers/proxy.py`: load `BackendConfig` for key owner; decrypt credential via `crypto.decrypt_credential` (transient — local var only, no persistence); construct httpx request to `BackendConfig.base_url`; forward response unchanged; on success write `UsageRecord` with `user_id`, `proxy_key_id`, `proxy_key_label`, `model`, `input_tokens`, `output_tokens`, `cost` (via `metering.compute_cost`), `token_count_source`, `status_code`
- [X] T039 [US4] Implement `POST /v1/chat/completions` streaming path in `proxy/routers/proxy.py`: detect `"stream": true` in request body; inject `stream_options: {include_usage: true}` for openai_compat backends; use `httpx.AsyncClient.stream` and `StreamingResponse` to forward SSE tokens as they arrive without buffering; parse final `usage` chunk after stream ends to write `UsageRecord`
- [X] T040 [US4] Implement metering integration in `proxy/routers/proxy.py`: call `metering.compute_cost(model, input_tokens, output_tokens, cost_rates)`; set `token_count_source` to `"exact"` when provider reports usage, `"estimated"` when falling back to tiktoken; write `UsageRecord` even on backend errors (with actual `status_code`)
- [X] T041 [US4] Update `proxy/main.py`: mount `proxy` router at `/v1`; ensure proxy router uses proxy-key auth (not JWT)
- [X] T042 [US4] Write `proxy/tests/test_proxy.py`: mock httpx backend; valid key → response forwarded; revoked key → 401; no backend configured → 400; `UsageRecord` row created with correct `user_id`; cross-user: user B's request uses user B's backend, not user A's; token_count_source recorded correctly
- [X] T043 [US4] Write `proxy/tests/test_metering.py`: `compute_cost` arithmetic; tiktoken estimation path; exact path when provider reports usage (existing tests may exist — verify and extend)

**Checkpoint**: `POST /v1/chat/completions` with a valid proxy key returns the backend's response and creates a `UsageRecord`. Streaming verified end-to-end. Cross-user backend isolation confirmed by test.

---

## Phase 7: User Story 5 — Usage Dashboard (Priority: P2)

**Goal**: Authenticated user views their own usage: total spend, spend by key, spend by model, time-series chart, paginated request log. Zero/empty states render cleanly.

**Independent Test**: With usage records seeded for two users, each user's dashboard shows only their own totals, breakdowns, and log entries.

### Implementation for User Story 5

- [X] T044 [US5] Implement `proxy/routers/stats.py`: `GET /stats/summary` — aggregate `UsageRecord` by `user_id`; `GET /stats/by-key` — group by `proxy_key_id`, return with `display` field; `GET /stats/by-model` — group by `model`; `GET /stats/timeseries?days=30` — group by date, return `[{date, total_cost, total_requests}]`; `GET /stats/requests?limit&offset` — paginated log, newest first; all queries MUST include `WHERE user_id = :current_user_id`
- [X] T045 [US5] Update `proxy/main.py`: mount `stats` router at `/stats`
- [X] T046 [US5] Write `proxy/tests/test_stats.py`: seed records for two users; each stats endpoint called as user A returns only user A's data; verify `token_count_source = "estimated"` records are correctly included; empty-state returns zeroes / empty arrays not errors
- [X] T047 [P] [US5] Implement `dashboard/src/pages/DashboardPage.tsx`: on mount fetch `GET /stats/summary`, `GET /stats/by-key`, `GET /stats/by-model`, `GET /stats/timeseries`, `GET /stats/requests`; render `SummaryCards`, `CostChart`, `BreakdownTable`, `RequestLog`; handle empty state with zero/empty placeholders
- [X] T048 [P] [US5] Implement `dashboard/src/components/SummaryCards.tsx`: display `total_cost`, `total_requests`, `total_input_tokens`, `total_output_tokens` in Mantine `Card` components
- [X] T049 [P] [US5] Implement `dashboard/src/components/CostChart.tsx`: `recharts` `LineChart` over `timeseries` data; x-axis dates, y-axis cost; handle empty data gracefully
- [X] T050 [P] [US5] Implement `dashboard/src/components/BreakdownTable.tsx`: tabbed or dual-section Mantine `Table` for by-key and by-model breakdowns
- [X] T051 [P] [US5] Implement `dashboard/src/components/RequestLog.tsx`: paginated Mantine `Table`; display `~` prefix on `input_tokens`/`output_tokens` when `token_count_source === "estimated"`; pagination controls using `limit`/`offset`
- [X] T052 [US5] Add stats API wrappers to `dashboard/src/api.ts`: `getSummary()`, `getByKey()`, `getByModel()`, `getTimeseries(days?)`, `getRequests(limit?, offset?)`
- [X] T053 [US5] Define `dashboard/src/types.ts`: TypeScript interfaces for all API response shapes (`SummaryResponse`, `ByKeyItem`, `ByModelItem`, `TimeseriesItem`, `RequestLogResponse`, `RequestItem`, `ProxyKeyResponse`, `CredentialsResponse`)

**Checkpoint**: Dashboard page renders all four sections with user-scoped data. Estimated-token rows display `~` indicator. Empty state renders without errors.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Deployment config, README, cross-cutting hardening, quickstart validation.

- [X] T054 [P] Create `Caddyfile` with `reverse_proxy proxy:8000` and HTTPS config placeholder for subdomain
- [X] T055 [P] Update `docker-compose.yml`: add `proxy` service (FastAPI + uvicorn `--proxy-headers`), `caddy` service; `RELAY_ENCRYPT_KEY` and `JWT_SECRET` via `env_file: .env`; SQLite volume mount `- /opt/relay/data:/data`
- [X] T056 [P] Create `Dockerfile`: multi-stage — Node build stage for dashboard, Python runtime stage; copy `dashboard/dist` into proxy static files directory; expose port 8000
- [X] T057 [P] Create `config.yml.example`: operator cost rates only, no credentials; document `RELAY_ENCRYPT_KEY` generation command
- [X] T058 Update `README.md`: document `docker compose up` start command; Fernet key generation one-liner; quickstart walkthrough referencing `quickstart.md`
- [X] T059 Run `quickstart.md` validation end-to-end: register → login → configure credential → create proxy key → send `POST /v1/chat/completions` → verify usage appears in dashboard
- [X] T060 [P] Security hardening: verify no route returns plaintext credentials; verify all `/api/*` and `/stats/*` routes require JWT; verify `/v1/*` routes require proxy key; grep codebase for any accidental `print(credential)` or `log(key)` patterns
- [X] T061 [P] Run full test suite: `pytest proxy/tests/` — all tests green without live backend or network; verify `test_isolation.py` covers every data endpoint

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 — auth infrastructure must exist
- **US2 (Phase 4)**: Depends on Phase 2 — proxy key model + isolation dep must exist
- **US3 (Phase 5)**: Depends on Phase 2 — `crypto.py` and `BackendConfig` model must exist
- **US4 (Phase 6)**: Depends on US2 (proxy key lookup) and US3 (backend config + decrypt)
- **US5 (Phase 7)**: Depends on US4 (usage records must exist to aggregate)
- **Polish (Phase 8)**: Depends on all user stories complete

### User Story Dependencies

- **US1** (auth): Can start immediately after Phase 2 — no dependency on other stories
- **US2** (proxy keys): Can start immediately after Phase 2 — no dependency on US1
- **US3** (credentials): Can start immediately after Phase 2 — no dependency on US1 or US2
- **US4** (proxy forwarding): Depends on US2 (key lookup) AND US3 (backend + decrypt)
- **US5** (dashboard): Depends on US4 (needs usage records)

> **US1, US2, US3 can be worked in parallel once Phase 2 is complete.**

### Within Each User Story

- Models before services
- Services before endpoints
- Backend (proxy/) before frontend (dashboard/)
- Story complete before moving to next priority

### Parallel Opportunities

- T002, T003, T004, T005 (Phase 1 skeleton files) — all in parallel
- T018–T023 (US1 dashboard components) — T018–T021 in parallel; T022 before T023
- T026, T027 (US2 dashboard components) — in parallel
- T033, T034 (US3 dashboard components) — in parallel
- T047–T051 (US5 dashboard components) — all in parallel after T044–T046
- T054–T057 (Phase 8 config files) — all in parallel

---

## Parallel Example: Phase 2 Foundation

```bash
# These can start in parallel once Phase 1 is complete:
Task T006: Extend db/models.py with all tables
Task T008: Implement crypto.py (independent file)
Task T011: Update config.py (independent file)
# T007, T009, T010 depend on T006 and T008 respectively — run sequentially after
```

## Parallel Example: US1 + US2 + US3 (after Phase 2)

```bash
# All three stories can run simultaneously:
Developer A: T014–T023 (US1 — auth + login/signup UI)
Developer B: T024–T029 (US2 — proxy key management)
Developer C: T030–T035 (US3 — credential config)
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US3 + US4 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (**CRITICAL** — blocks all stories)
3. Complete Phase 3 (US1) + Phase 4 (US2) + Phase 5 (US3) in parallel
4. Complete Phase 6 (US4) — proxy forwarding
5. **STOP and VALIDATE**: Full proxy flow works end-to-end (quickstart.md steps 1–7)
6. Deploy if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 + US2 + US3 (parallel) → User can sign up, manage keys, configure backend
3. US4 → Proxy forwarding works → **Product is functional** (MVP!)
4. US5 → Dashboard shows usage → Observability complete
5. Phase 8 → Production-ready

### Parallel Team Strategy

With three developers:

1. All complete Phase 1 + Phase 2 together
2. Once Foundational is done:
   - Developer A: US1 (auth)
   - Developer B: US2 (proxy keys)
   - Developer C: US3 (credentials)
3. Once US2 + US3 done: all converge on US4 (proxy forwarding)
4. US5 follows US4

---

## Notes

- `[P]` tasks touch different files with no inter-task deps — safe to parallelize
- `[Story]` label maps each task to its user story for traceability
- Credential plaintext MUST NEVER appear in any response, log, or test assertion
- `test_isolation.py` covers every data endpoint — do not skip
- All backend tests run without a live LLM or network (`pytest proxy/tests/` must be green in CI)
- Commit after each checkpoint to preserve working state
- Constitution §II governs all credential-handling decisions — when in doubt, encrypt and mask
