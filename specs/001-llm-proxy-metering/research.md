# Research: LLM Proxy with Usage Metering

**Date**: 2026-06-03

## Decision Log

### 1. Web Framework

**Decision**: FastAPI with uvicorn

**Rationale**: FastAPI provides native async support and automatic OpenAPI docs.
`StreamingResponse` handles SSE pass-through without buffering. Pydantic models
(already a FastAPI dependency) cover config validation at no extra cost.

**Alternatives considered**:
- Flask/Starlette-only: Flask is synchronous; Starlette alone would require
  more boilerplate for routing and dependency injection.
- Django: Far too heavy for a single-endpoint proxy service.

---

### 2. HTTP Client for Backend Forwarding

**Decision**: `httpx` with `AsyncClient` and streaming

**Rationale**: `httpx` supports async streaming via `stream()` context manager,
which allows iterating response chunks as they arrive and forwarding each chunk
immediately to the client. This is the correct primitive for SSE pass-through.
`aiohttp` is an alternative but `httpx` has a cleaner API and a mock transport
(`httpx.MockTransport`) that makes unit tests straightforward.

**Alternatives considered**:
- `aiohttp`: Viable but `httpx` mock transport makes testing easier.
- `urllib3` / `http.client`: Synchronous only; cannot stream without threads.

---

### 3. Token Counting Strategy

**Decision**: Exact-first, tiktoken-fallback, always-labelled

**Rationale** (per user specification):
1. OpenAI-compatible backends: The non-streaming response includes a `usage`
   object (`prompt_tokens`, `completion_tokens`). For streaming, request
   `stream_options: {include_usage: true}` — OpenAI returns a final chunk with
   `usage` populated.
2. Ollama backend: The final response JSON contains `prompt_eval_count`
   (input tokens) and `eval_count` (output tokens). Map these to the common
   `UsageData` struct.
3. Fallback: If neither source is available, use `tiktoken` with the
   `cl100k_base` encoding (safe default for GPT-family; documents uncertainty).
   Record `token_count_source = "estimated"`.

This keeps metering accurate and avoids re-implementing per-model tokenizers.

---

### 4. ORM and Storage

**Decision**: SQLModel + SQLite

**Rationale**: SQLModel unifies SQLAlchemy (async engine) and Pydantic model
definitions into one class, eliminating the dual-definition pattern
(SQLAlchemy table + Pydantic schema). SQLite requires no separate server
process, is appropriate for single-node deployments, and its file can be volume-
mounted in Docker.

**Alternatives considered**:
- Raw SQLAlchemy: More boilerplate (separate Pydantic schemas required).
- PostgreSQL: Unnecessary infra for a single-developer weekend project; adds a
  second required container.
- Peewee: No async support.

---

### 5. Dashboard Technology

**Decision**: Vite + React + Mantine UI + recharts, built to static files served by FastAPI

**Rationale**: The dashboard is purely read-only, consuming a JSON stats API.
No SSR needed. Vite builds to a `dist/` directory that FastAPI mounts as a
`StaticFiles` route — no separate web server.

- **Mantine UI** (`@mantine/core`, `@mantine/hooks`) provides layout primitives
  (`Grid`, `Card`, `AppShell`), a `Table` component for the request log, and
  consistent theming — replacing hand-rolled CSS for structural UI. Mantine has
  no built-in chart components, so it composes cleanly with recharts.
- **recharts** remains for the time-series cost chart (`LineChart`/`BarChart`).
  Mantine does not ship charts; the two libraries have no overlap.

**Component mapping**:
- Summary stats → `Mantine Card` + `Grid`
- Per-key / per-model breakdowns → `Mantine Table`
- Request log → `Mantine Table` (scrollable, paginated)
- Time-series chart → `recharts LineChart` inside a `Mantine Card`
- Page layout → `Mantine AppShell` + `NavLink`

**Alternatives considered**:
- Next.js: SSR overhead for a static read dashboard is unnecessary (per user).
- MUI (Material UI): Heavier bundle; Mantine is leaner and has better TypeScript
  ergonomics for this scale.
- Tailwind + headless UI: More setup for a weekend project; Mantine is batteries-
  included.
- Plain HTML + vanilla JS: No component model; harder to maintain data-binding
  for live stats.

---

### 6. Configuration Format

**Decision**: `config.yml` as primary config, with env var overrides for secrets

**Rationale**: YAML is human-readable for multi-key, multi-model config
(nested structures). Sensitive values (backend API keys) can be overridden via
environment variables (Pydantic `BaseSettings` reads both). A single `config.yml`
at the repo root satisfies "configurable without code changes" and is easy to
mount in Docker.

**Structure**:
```yaml
backend:
  type: openai_compat   # or ollama
  base_url: https://api.openai.com/v1
  api_key: ${BACKEND_API_KEY}   # env override

api_keys:
  - key: sk-relay-abc123
    label: my-app

cost_rates:
  gpt-4o:
    input_per_token: 0.0000025
    output_per_token: 0.000010
  llama3:
    input_per_token: 0.0
    output_per_token: 0.0
```

---

### 7. Backend Adapter Interface

**Decision**: Python `Protocol` class with async methods

**Rationale**: A `Protocol` (structural subtyping) lets each adapter be a
standalone class without inheriting from a shared base, keeping them
independently importable. The metering layer only imports `BackendAdapter`
(the protocol), never the concrete adapter classes.

**Interface**:
```python
class BackendAdapter(Protocol):
    async def chat_complete(
        self, request: ChatRequest
    ) -> tuple[ChatResponse, UsageData]: ...

    async def chat_complete_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[tuple[str, UsageData | None]]: ...
```

`UsageData` is a plain dataclass with `input_tokens`, `output_tokens`,
`source: Literal["exact", "estimated"]`.

---

### 8. Build Order

**Decision**: Non-streaming core first, streaming and second backend last

**Rationale** (per user specification): Streaming SSE pass-through and correct
Ollama token extraction are the two riskiest implementation pieces. Keeping them
last means there is always a working, shippable product. The build phases:

1. OpenAI-compat non-streaming proxy + SQLite recording + stats API + dashboard
2. Ollama adapter (second backend)
3. Streaming pass-through (SSE)

---

### 9. Docker / Packaging

**Decision**: Single `Dockerfile` for the proxy; `docker-compose.yml` with
optional Ollama service

**Rationale**: The Dockerfile builds the dashboard (Node stage), copies
`dist/` into the Python image (multi-stage), and runs uvicorn. One compose
command brings up everything. Ollama is an optional profile so reviewers
without a GPU aren't forced to pull it.
