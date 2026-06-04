<!--
SYNC IMPACT REPORT
==================
Version change: 2.0.0 → 2.1.0 (MINOR)

Rationale for MINOR bump:
  Principle II (Multi-Tenant Isolation) is materially expanded with concrete,
  enforceable credential-security rules: encryption at rest with an out-of-band
  key, masked display (last-4 only), transient in-memory decryption, and an
  explicit breach-resistance requirement. These are new binding technical rules
  that did not exist in 2.0.0. No existing principle is removed or reversed.

Modified principles:
  II. Multi-Tenant Isolation → II. Multi-Tenant Isolation & Credential Security
      (title updated to reflect the expanded scope; rules materially expanded)

Added to Scope Boundaries:
  - Credential storage: provider API keys MUST be encrypted at rest; plain-text
    storage is a constitutional violation.

Templates reviewed:
  - .specify/templates/plan-template.md    ✅ no changes needed
  - .specify/templates/spec-template.md   ✅ no changes needed
  - .specify/templates/tasks-template.md  ✅ no changes needed

Deferred TODOs: none
-->

# Relay Constitution

## Core Principles

### I. Single Purpose

Relay is a multi-tenant LLM proxy that meters token usage and cost per user.
Every feature MUST directly serve request proxying, user authentication,
per-user usage/cost measurement, or reporting of that usage to the
authenticated user.

The following remain explicitly out of scope and MUST be rejected:
- Rate limiting or quota enforcement
- Billing integrations or payment flows
- Features that store or process prompt/response content beyond token counts

When evaluating a proposed feature, ask: "Does this forward a request, identify
a user, or help that user understand their own usage?" If the answer is no,
reject it.

### II. Multi-Tenant Isolation & Credential Security

Relay stores users' third-party LLM provider API keys. Custody of those
credentials is a first-class obligation. Isolation and credential security are
non-negotiable; they take priority over feature breadth.

**Data isolation**:
- Every data access (usage records, keys, cost summaries) MUST be scoped to the
  authenticated user. No query MAY return another user's records.
- No endpoint MAY expose one user's data, keys, or costs to another user,
  regardless of request parameters.
- Isolation MUST be enforced at the data layer, not only at the API layer. A
  missing `WHERE user_id = ?` clause is a security defect, not a missing
  feature.

**Provider credential protection**:
- User-stored LLM provider API keys MUST be encrypted at rest using a dedicated
  encryption key held outside the database (e.g., an environment-provided
  secret or key-management service). A full breach of the datastore alone MUST
  NOT yield usable provider credentials.
- Provider credentials MUST be decrypted only transiently in memory at the
  moment a request is forwarded to the backend. They MUST NOT be cached,
  serialised to disk, or held in memory beyond the lifetime of a single request.
- Provider credentials MUST NEVER appear in logs, error messages, tracebacks,
  or any API response.
- API responses that reference a stored credential MUST display only a masked
  form — for example, the last four characters with the remainder replaced by
  asterisks (e.g. `****6789`). The full value MUST NOT be returned even to the
  credential's owner.
- A feature that cannot be implemented without weakening any of the above
  credential rules MUST NOT be shipped.

### III. Minimal Dependencies

The standard library MUST be the first tool considered. A new dependency MUST
be justified by one of: capability the stdlib cannot provide, significant
reduction in correctness risk (e.g., a battle-tested HTTP client over a
hand-rolled one), or dramatically less code to maintain.

Each dependency addition requires a one-line comment in the manifest explaining
why the stdlib was insufficient.

### IV. Observability Is the Product

Accurate, transparent usage and cost accounting is Relay's core value. Token
counts and cost figures reported to users MUST be correct or explicitly labelled.

- If a token count is exact (from the provider response), report it as-is.
- If a token count is estimated (e.g., pre-response tokenization), it MUST be
  labelled `estimated` in every place it is surfaced — logs, API responses, and
  reports. Silent guessing is a defect.
- All observability endpoints MUST enforce Principle II: a user MUST only see
  their own usage.

### V. Backend-Agnostic Core

All LLM provider integrations MUST implement a common backend interface. The
metering and cost-calculation logic MUST NOT import or reference any provider-
specific package or constant. New backends MUST be addable by implementing the
interface alone, without touching metering code.

### VI. Testable Units

The following concerns MUST be unit-testable without a live LLM or network
connection:

1. Request forwarding logic (routing, header rewriting, body pass-through)
2. Token counting (both exact and estimation paths)
3. Cost calculation (price-per-token arithmetic)
4. Isolation enforcement (a query scoped to user A MUST NOT return user B's
   records — verifiable with an in-memory database fixture)
5. Credential encryption/decryption round-trip and masking (verifiable without
   a live key-management service, using a test encryption key)

Tests for these concerns MUST NOT require environment variables pointing to a
live provider endpoint to pass.

### VII. Runnable in One Command

The complete stack MUST start via `docker compose up` (or an equivalent single
documented command at the repo root). The command MUST be documented in
`README.md`. A reviewer with Docker installed MUST be able to send a proxied
request within five minutes of cloning the repo.

## Scope Boundaries

The following boundaries apply at all times and MUST be enforced during
design review:

- **Authentication**: User identity is established by API key. More complex
  auth mechanisms (OAuth, session cookies, JWT) are out of scope unless a
  future amendment explicitly introduces them.
- **Credential storage**: Provider API keys MUST be stored encrypted. Plain-text
  storage of provider credentials is a constitutional violation regardless of
  other mitigations.
- **Storage**: Usage records and user/key metadata only. No prompt or response
  content storage.
- **Isolation priority**: Correctness of per-user isolation and credential
  security takes precedence over shipping new features. An isolated partial
  feature is preferable to a complete feature with a data-exposure risk.
- **UI**: A per-user read-only usage report endpoint/dashboard is in scope.
  Cross-user admin views are out of scope.
- **Billing**: Relay reports cost per user; it does not charge, invoice, or
  integrate with payment providers.

## Governance

This constitution supersedes all other development guidelines for Relay.
Amendments require updating this file, bumping the version, and noting the
change in git history.

**Versioning policy**:
- MAJOR — principle removed or its meaning changed in a backward-incompatible
  way (e.g., a formerly out-of-scope concern is brought in-scope, or vice
  versa).
- MINOR — new principle or section added, or scope boundary meaningfully
  expanded.
- PATCH — wording clarification, typo fix, or non-semantic refinement.

Compliance is reviewed at the start of every feature plan (Constitution Check
in `plan.md`) and again after Phase 1 design.

**Version**: 2.1.0 | **Ratified**: 2026-06-03 | **Last Amended**: 2026-06-03
