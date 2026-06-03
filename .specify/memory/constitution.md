<!--
SYNC IMPACT REPORT
==================
Version change: (unversioned template) → 1.0.0
Ratification: First adoption — 2026-06-03

Modified principles: N/A (first adoption, all principles new)

Added sections:
- Core Principles (6 principles)
- Scope Boundaries
- Governance

Removed sections:
- [SECTION_2_NAME] placeholder
- [SECTION_3_NAME] placeholder

Templates reviewed:
- .specify/templates/plan-template.md    ✅ no changes needed; Constitution Check section is generic
- .specify/templates/spec-template.md   ✅ no changes needed; requirements format is compatible
- .specify/templates/tasks-template.md  ✅ no changes needed; task phases are generic

Deferred TODOs: none
-->

# Relay Constitution

## Core Principles

### I. Single Purpose

Relay is an LLM proxy that meters token usage and cost. Every feature MUST
directly serve request proxying or usage/cost measurement and reporting.

The following are explicitly out of scope and MUST be rejected:
- Auth systems beyond simple static API keys
- Rate limiting or quota enforcement
- Multi-tenant admin interfaces
- Billing integrations or payment flows

When evaluating a proposed feature, ask: "Does this forward a request or does
this help the operator understand usage?" If the answer is no, reject it.

### II. Minimal Dependencies

The standard library MUST be the first tool considered. A new dependency MUST
be justified by one of: capability the stdlib cannot provide, significant
reduction in correctness risk (e.g., a battle-tested HTTP client over a
hand-rolled one), or dramatically less code to maintain.

Each dependency addition requires a one-line comment in the manifest explaining
why the stdlib was insufficient.

### III. Observability Is the Product

Accurate, transparent usage and cost accounting is Relay's core value. Token
counts and cost figures reported to users MUST be correct or explicitly labelled.

- If a token count is exact (from the provider response), report it as-is.
- If a token count is estimated (e.g., pre-response tokenization), it MUST be
  labelled `estimated` in every place it is surfaced — logs, API responses, and
  reports. Silent guessing is a defect.

### IV. Backend-Agnostic Core

All LLM provider integrations MUST implement a common backend interface. The
metering and cost-calculation logic MUST NOT import or reference any provider-
specific package or constant. New backends MUST be addable by implementing the
interface alone, without touching metering code.

### V. Testable Units

The following three concerns MUST be unit-testable without a live LLM or
network connection:

1. Request forwarding logic (routing, header rewriting, body pass-through)
2. Token counting (both exact and estimation paths)
3. Cost calculation (price-per-token arithmetic)

Tests for these concerns MUST NOT require environment variables pointing to a
live provider endpoint to pass.

### VI. Runnable in One Command

The complete stack MUST start via `docker compose up` (or an equivalent single
documented command at the repo root). The command MUST be documented in
`README.md`. A reviewer with Docker installed MUST be able to send a proxied
request within five minutes of cloning the repo.

## Scope Boundaries

The following boundaries apply at all times and MUST be enforced during
design review:

- **Authentication**: Static API key comparison only. No JWT, OAuth, or session
  management.
- **Storage**: Usage records only. No user accounts, no configuration DB.
- **UI**: A minimal read-only usage report endpoint is acceptable. No
  interactive admin dashboard.
- **Billing**: Relay reports cost; it does not charge, invoice, or integrate
  with payment providers.

## Governance

This constitution supersedes all other development guidelines for Relay.
Amendments require updating this file, bumping the version, and noting the
change in git history.

**Versioning policy**:
- MAJOR — principle removed or its meaning changed in a backward-incompatible way.
- MINOR — new principle or section added, or scope boundary meaningfully expanded.
- PATCH — wording clarification, typo fix, or non-semantic refinement.

Compliance is reviewed at the start of every feature plan (Constitution Check
in `plan.md`) and again after Phase 1 design.

**Version**: 1.0.0 | **Ratified**: 2026-06-03 | **Last Amended**: 2026-06-03
