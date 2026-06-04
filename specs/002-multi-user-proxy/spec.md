# Feature Specification: Multi-User LLM Proxy

**Feature Branch**: `002-multi-user-proxy`

**Created**: 2026-06-03

**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Account Registration & Login (Priority: P1)

A person visits the application, creates an account with an email address and
password, and logs in. Once authenticated, they have access to their own private
workspace with no ability to view or interact with any other user's data.

**Why this priority**: All other stories depend on a user having an authenticated
session. Without this, no per-user isolation is possible.

**Independent Test**: A new user can complete sign-up and log in without any
prior account existing. After login they reach their own dashboard. A second
user signing up in the same session cannot see the first user's workspace.

**Acceptance Scenarios**:

1. **Given** a visitor with no account, **When** they submit a valid email and
   password through the sign-up form, **Then** an account is created, they are
   logged in, and they arrive at an empty personal dashboard.

2. **Given** a registered user, **When** they submit their credentials through
   the login form, **Then** they are authenticated and reach their personal
   dashboard.

3. **Given** an unauthenticated visitor, **When** they attempt to access any
   protected page (dashboard, settings, key management), **Then** they are
   redirected to the login page.

4. **Given** a user submitting an incorrect password, **When** the login form is
   submitted, **Then** an error is shown and no session is created.

---

### User Story 2 — Proxy Key Management (Priority: P1)

An authenticated user creates one or more proxy API keys that their applications
will use when calling the proxy endpoint. They can also revoke any key they own.
Keys from other users are never visible.

**Why this priority**: Proxy keys are the mechanism by which usage is attributed
to a user. This must exist before any proxying can happen.

**Independent Test**: A logged-in user creates a proxy key, sees it listed on
their dashboard, and can revoke it. A second user logged in on a separate session
cannot see the first user's keys.

**Acceptance Scenarios**:

1. **Given** an authenticated user, **When** they create a proxy key with an
   optional label, **Then** the full key value is shown exactly once (at
   creation), a masked representation (last 4 characters) is stored and
   displayed in subsequent listings, and the key is associated only with their
   account.

2. **Given** an authenticated user with existing proxy keys, **When** they view
   their key list, **Then** only their own keys are shown, each displaying the
   label and masked value, never another user's keys.

3. **Given** an authenticated user, **When** they revoke a proxy key, **Then**
   that key is immediately invalidated and removed from their list. Subsequent
   requests using that key are rejected by the proxy.

4. **Given** two users each with proxy keys, **When** either user lists their
   keys, **Then** each sees only their own keys and neither can see, copy, or
   revoke the other's keys.

---

### User Story 3 — Backend Credential Configuration (Priority: P1)

An authenticated user configures their own LLM backend: either an
OpenAI-compatible provider (with their own API key) or an Ollama endpoint (with
their own URL). These credentials are stored securely and are never visible to
other users or returned in full in any response.

**Why this priority**: Without a configured backend, the proxy cannot forward
requests on behalf of the user. Credential security is a core constitutional
requirement.

**Independent Test**: A user adds an OpenAI API key. The system confirms it is
saved. The key is never shown in full in any subsequent response — only a masked
form (last 4 characters). A different logged-in user cannot see or read this
credential.

**Acceptance Scenarios**:

1. **Given** an authenticated user, **When** they submit a provider API key and
   backend type (OpenAI-compatible or Ollama URL), **Then** the credential is
   saved and a confirmation is shown. The response and all subsequent displays
   show only the masked form (e.g., `****6789`). The full value is never
   returned.

2. **Given** a user who has configured a backend, **When** another authenticated
   user views their own settings page, **Then** they see only their own
   configuration; the other user's credentials, backend type, and endpoint are
   invisible.

3. **Given** a user updating an existing backend credential, **When** they
   submit a new value, **Then** the old credential is replaced and the new
   masked value is displayed. The previous credential is no longer used.

4. **Given** a user who has not yet configured a backend, **When** a proxy
   request arrives using their proxy key, **Then** the request is rejected with
   a clear error indicating no backend is configured; no other user's backend
   is used as a fallback.

---

### User Story 4 — Proxied Chat-Completion Requests (Priority: P1)

An application sends a chat-completion request to the proxy endpoint using one
of the user's proxy keys. The proxy identifies the key owner, uses that user's
own configured backend and credentials to forward the request, returns the
response to the caller, and records the usage against that user.

**Why this priority**: This is the core value of the product. Every other story
exists to support this one.

**Independent Test**: With a configured backend and a valid proxy key, an
application sends a non-streaming `POST /v1/chat/completions` to the proxy and
receives a functionally identical response to calling the backend directly. A
usage record appears in that user's dashboard. No other user's backend or
credentials are involved.

**Acceptance Scenarios**:

1. **Given** a proxy key owned by User A with a configured backend, **When** an
   application sends a non-streaming chat-completion request with that key,
   **Then** the proxy uses User A's backend credentials, returns the response
   unchanged, and records the usage against User A.

2. **Given** a proxy key owned by User A, **When** a streaming
   (`"stream": true`) chat-completion request is sent, **Then** response tokens
   are forwarded to the caller as they arrive (server-sent events), with no
   buffering, and usage is recorded after the stream ends.

3. **Given** an invalid or revoked proxy key, **When** a request arrives,
   **Then** the request is rejected with a 401 error before reaching any backend.

4. **Given** User A and User B each with different backends, **When** requests
   arrive using each user's key respectively, **Then** User A's request goes to
   User A's backend with User A's credentials, and User B's request goes to
   User B's backend with User B's credentials. Neither user's credentials are
   ever used for the other's requests.

---

### User Story 5 — Usage Dashboard (Priority: P2)

An authenticated user opens their dashboard and sees their own token usage and
cost, broken down by proxy key and by model, including a time-series chart and
a request log showing only their own requests.

**Why this priority**: Observability is the product's core value. However, it
depends on the proxy being operational (US4), so it is P2.

**Independent Test**: With recorded usage for two separate users, each user's
dashboard shows only their own totals, breakdowns, and request log entries.
No cross-user data appears in any view.

**Acceptance Scenarios**:

1. **Given** a user with recorded usage across multiple proxy keys and models,
   **When** they open their dashboard, **Then** they see: their total spend,
   spend broken down by proxy key, spend broken down by model, a time-series
   chart, and a request log — all containing only their own data.

2. **Given** two users with recorded usage, **When** each views their dashboard,
   **Then** each sees only their own records. Neither user's totals, keys, model
   usage, or requests appear in the other's view.

3. **Given** a user with no recorded usage, **When** they open their dashboard,
   **Then** the page renders with clear zero/empty states.

---

### Edge Cases

- A proxy request arrives with a key belonging to a user who has since deleted
  or invalidated their backend configuration: the request is rejected with a
  clear error; no other user's backend is used as a fallback.
- A user attempts to configure an Ollama endpoint but the URL is unreachable: an
  appropriate error is shown; no credential is stored until validation passes (or
  validation is deferred and the error surfaces at request time).
- Simultaneous requests using the same proxy key are handled correctly without
  one request leaking context into another.
- A user's session expires mid-use: the next protected action redirects to login.
- A backend provider credential is stored but later becomes invalid (e.g., key
  revoked at the provider): the proxy returns an error on the next request;
  usage is not recorded for failed backend calls.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow a visitor to create an account with an email
  address and password.
- **FR-002**: The system MUST allow a registered user to authenticate with their
  email and password and receive a session.
- **FR-003**: All protected resources MUST be inaccessible to unauthenticated
  requests; such requests MUST be redirected to login.
- **FR-004**: An authenticated user MUST be able to create named proxy API keys
  associated with their account.
- **FR-005**: The full value of a newly created proxy key MUST be displayed
  exactly once at creation and never again.
- **FR-006**: Proxy key listings MUST show only a masked representation (last 4
  characters); the full key MUST NOT be returned by any API endpoint after
  creation.
- **FR-007**: An authenticated user MUST be able to revoke any of their own
  proxy keys; revocation MUST take effect immediately for subsequent requests.
- **FR-008**: An authenticated user MUST be able to configure a backend provider:
  either an OpenAI-compatible API (with their provider API key and endpoint URL)
  or an Ollama endpoint (with the endpoint URL).
- **FR-009**: Provider API keys MUST be stored encrypted. They MUST NOT be
  returned in any API response (beyond masked form), logged, or accessible to
  any user other than the owner.
- **FR-010**: The proxy endpoint MUST accept `POST /v1/chat/completions` requests
  authenticated with a user's proxy key.
- **FR-011**: For each proxied request, the system MUST identify the key owner,
  use that user's configured backend and decrypted credentials, forward the
  request, and record the usage against that user.
- **FR-012**: The proxy MUST support streaming responses, forwarding tokens to
  the caller incrementally as they arrive.
- **FR-013**: The proxy MUST support both OpenAI-compatible and Ollama backends.
- **FR-014**: For each completed request, the system MUST record: timestamp,
  proxy key used, model, backend type, input tokens, output tokens, and computed
  cost.
- **FR-015**: Token counts reported as estimated MUST be clearly labelled as
  such in all views.
- **FR-016**: The dashboard MUST display: total spend, spend by proxy key, spend
  by model, a time-series chart, and a paginated request log — all scoped
  strictly to the authenticated user.
- **FR-017**: No API endpoint or UI view MAY return data belonging to any user
  other than the authenticated requester.

### Key Entities

- **User**: An account in the system. Attributes: email, hashed password, created
  date. All other entities belong to exactly one user.
- **ProxyKey**: A credential an application uses to authenticate requests to the
  proxy. Attributes: key value (stored hashed or masked after creation), label,
  owner (User), active/revoked status, created date.
- **BackendConfig**: A user's configured LLM provider. Attributes: backend type
  (`openai_compat` | `ollama`), endpoint URL, provider API key (stored encrypted),
  owner (User).
- **UsageRecord**: One record per completed proxied request. Attributes:
  timestamp, proxy key used, model, backend type, input tokens, output tokens,
  cost, token count source (`exact` | `estimated`), HTTP status code, owner
  (User).
- **CostRate**: Operator-configured price per token per model. Attributes: model
  identifier, input price per token, output price per token. (Shared across all
  users; set by the operator.)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can complete sign-up, configure a backend, create a
  proxy key, send a proxied request, and see usage on their dashboard — all
  without assistance and within 10 minutes of first visiting the application.
- **SC-002**: No test or manual verification can produce an API response
  containing one user's data when authenticated as a different user.
- **SC-003**: No test or manual verification can retrieve a provider API key in
  its full, unmasked form from any API endpoint after the credential has been
  saved.
- **SC-004**: Streaming responses begin reaching the caller within the same
  latency window as a direct backend call — no full-response buffering.
- **SC-005**: The dashboard correctly reflects all and only the authenticated
  user's usage across a test dataset containing records for multiple users.
- **SC-006**: The complete service starts and accepts a proxied request within 5
  minutes of a reviewer cloning the repo and running the documented start
  command.

## Assumptions

- Email addresses are unique across the system; duplicate registration is
  rejected.
- Password requirements follow industry-standard minimums (e.g., minimum length)
  without requiring complexity rules unless specified later.
- A user configures at most one active backend at a time; updating replaces the
  previous configuration.
- Cost rates (price per token per model) are configured by the operator, not by
  individual users.
- The proxy key value is a randomly generated secret; the system need not
  validate it against any external service.
- Ollama endpoint reachability is validated at request time, not at configuration
  time, to avoid blocking the configuration flow when the endpoint is
  temporarily unavailable.
- Session management uses standard web session practices (secure, HTTP-only
  cookies or equivalent); the specific token format is an implementation detail.
- The application is single-region, single-node for v1; distributed or
  multi-region concerns are out of scope.
- Support for non-chat endpoints (embeddings, images, completions) is out of
  scope.
- Team/organization accounts, shared workspaces, and role-based permissions are
  out of scope.
- Operator admin panels (e.g., viewing all users, global usage) are out of scope
  for this feature; the focus is per-user self-service.
