# Feature Specification: LLM Proxy with Usage Metering

**Feature Branch**: `001-llm-proxy-metering`

**Created**: 2026-06-03

**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Transparent Proxy Pass-Through (Priority: P1)

An operator configures their existing application to send chat-completion
requests to the proxy URL instead of directly to the LLM backend. The
application sets an API key in the `Authorization` header. The proxy forwards
the request to the configured backend and returns a response that is
functionally identical to a direct backend call — same status code, same
response body, same streaming behavior.

**Why this priority**: This is the foundational capability. Without transparent
pass-through, none of the other stories are reachable.

**Independent Test**: Configure a client to hit the proxy with a valid API key.
The client must receive the same response shape it would receive from the
backend directly. No application code changes should be required.

**Acceptance Scenarios**:

1. **Given** a client configured with a valid API key and the proxy URL,
   **When** it sends a non-streaming chat-completion request,
   **Then** the response body and status code are identical to calling the
   backend directly, and a usage record is persisted.

2. **Given** a client configured with a valid API key,
   **When** it sends a streaming chat-completion request (`"stream": true`),
   **Then** tokens are forwarded to the client incrementally as they arrive
   (server-sent events / chunked transfer), with no buffering delay, and a
   usage record is persisted once the stream completes.

3. **Given** an incoming request with no `Authorization` header or an
   unrecognized API key,
   **When** the proxy receives it,
   **Then** the request is rejected with an appropriate error response before
   it reaches the backend.

---

### User Story 2 — Usage & Cost Dashboard (Priority: P2)

An operator opens a dashboard URL in a browser and sees an overview of proxy
usage: total spend, spend broken down by API key, spend broken down by model,
and a time-series chart. A detailed log of individual requests (timestamp, key,
model, tokens, cost) is also available.

**Why this priority**: Visibility into spend is the primary value proposition.
Without the dashboard, recorded data has no accessible presentation layer.

**Independent Test**: With recorded usage data present, loading the dashboard
URL must display aggregated totals, a chart, and a request log without
requiring any backend interaction beyond the proxy's own storage.

**Acceptance Scenarios**:

1. **Given** recorded usage across multiple API keys and models,
   **When** an operator opens the dashboard,
   **Then** they see: total spend, a per-key spend breakdown, a per-model spend
   breakdown, a time-series chart of requests or cost over time, and a
   paginated or scrollable request log.

2. **Given** no recorded usage yet,
   **When** an operator opens the dashboard,
   **Then** the page renders without errors and displays zero/empty states
   clearly.

---

### User Story 3 — Configurable Per-Model Cost Rates (Priority: P3)

An operator updates the cost-rate configuration (e.g., adds a new model or
changes an existing model's price per token) and sends new requests through the
proxy. Future requests are costed using the updated rates; historical records
are not retroactively changed.

**Why this priority**: Cost rates change over time and vary by deployment. The
proxy must not hard-code rates.

**Independent Test**: Update the cost rate config for a model, send a request
through the proxy, and verify the recorded cost in the request log matches the
new rate.

**Acceptance Scenarios**:

1. **Given** a cost rate configured for a model,
   **When** a request using that model completes,
   **Then** the recorded cost equals `(input_tokens × input_price) +
   (output_tokens × output_price)` using the configured rates.

2. **Given** a cost rate updated in configuration and the service restarted,
   **When** new requests arrive,
   **Then** they are costed at the new rate; existing records retain their
   original cost.

3. **Given** a request for a model with no configured cost rate,
   **When** it completes,
   **Then** the usage record is saved with a cost of zero and the entry is
   clearly marked as having no rate configured (not silently treated as zero-
   cost).

---

### Edge Cases

- What happens when the backend returns an error (4xx/5xx)? The error response
  is forwarded to the client unchanged; no usage record is created (or a record
  is created with zero tokens and the error status noted).
- What happens when a streaming response is interrupted mid-stream? Any tokens
  already observed are recorded; the record is marked incomplete.
- What happens when two backends are configured and a request does not specify
  which to use? The proxy uses the default backend defined in configuration.
- What happens when token counts are not present in the backend response (e.g.,
  an older or non-standard backend)? Counts are estimated and the usage record
  is explicitly labelled `estimated` — never silently treated as exact.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The proxy MUST accept chat-completion requests at a standard
  OpenAI-compatible endpoint path and forward them to a configured backend.
- **FR-002**: The proxy MUST return the backend's response to the client
  unchanged in both body and status code.
- **FR-003**: The proxy MUST support streaming responses, forwarding tokens to
  the client incrementally without buffering the full response.
- **FR-004**: The proxy MUST reject requests that do not present a recognized
  API key, before forwarding to the backend.
- **FR-005**: The proxy MUST record, for each completed request: timestamp,
  API key, model identifier, backend identifier, input token count, output
  token count, and computed cost.
- **FR-006**: The proxy MUST support at least two backend types: a locally-
  hosted OpenAI-compatible server (e.g., Ollama) and a hosted OpenAI-compatible
  API.
- **FR-007**: The active backend MUST be selectable via configuration without
  code changes.
- **FR-008**: Per-model cost rates (price per input token, price per output
  token) MUST be configurable without code changes.
- **FR-009**: When token counts are not available from the backend response,
  the proxy MUST estimate them and label the record as `estimated`; it MUST NOT
  silently present an estimate as an exact count.
- **FR-010**: The dashboard MUST display: total spend, spend per API key, spend
  per model, a time-series chart, and a detailed request log.
- **FR-011**: The complete service stack MUST start via a single documented
  command.

### Key Entities

- **API Key**: A static secret that identifies a calling application or user.
  Attributes: key value, display label.
- **Usage Record**: One record per completed proxied request. Attributes:
  timestamp, api_key, backend, model, input_tokens, output_tokens, cost,
  token_count_source (`exact` | `estimated`).
- **Cost Rate**: Price configuration per model. Attributes: model identifier,
  input price per token, output price per token.
- **Backend**: A configured LLM endpoint. Attributes: type (`local` |
  `openai`), base URL, default model.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An application using the proxy as a drop-in replacement receives
  functionally identical responses to calling the backend directly, verified by
  response-shape comparison in tests.
- **SC-002**: Streaming responses begin reaching the client within the same
  latency window as a direct backend call — no full-response buffering
  introduced.
- **SC-003**: Every completed non-error request results in a usage record; zero
  records are silently dropped.
- **SC-004**: The dashboard loads and displays correct aggregated totals within
  a reasonable time for up to 10,000 stored records.
- **SC-005**: Adding a new model cost rate via configuration takes effect on the
  next request without redeploying code.
- **SC-006**: The service starts and accepts a proxied request within 5 minutes
  of a reviewer cloning the repo and running the documented start command.

## Assumptions

- API keys are static strings defined in configuration; there is no
  self-service key registration UI in this version.
- The proxy handles one backend at a time per deployment; multi-backend
  routing (e.g., by model prefix) is out of scope for v1.
- Usage data is stored locally (e.g., SQLite or flat file) suitable for a
  single-node deployment; distributed storage is out of scope.
- The dashboard is a read-only interface served by the proxy process itself;
  no separate frontend build step is required.
- Non-chat endpoints (embeddings, images, completions) are out of scope.
- Content of prompts and responses is not stored; only token counts and
  metadata are persisted.
- No rate limiting, quotas, or billing integrations are in scope for v1.
