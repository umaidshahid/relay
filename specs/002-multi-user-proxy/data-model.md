# Data Model: Multi-User LLM Proxy

**Date**: 2026-06-03

---

## Entities

### User

Managed by FastAPI-Users. Every other entity has a `user_id` FK pointing here.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK | FastAPI-Users default |
| `email` | string | NOT NULL, UNIQUE | Login identifier |
| `hashed_password` | string | NOT NULL | bcrypt hash; plaintext never stored |
| `is_active` | bool | NOT NULL, default true | FastAPI-Users: inactive users cannot log in |
| `is_superuser` | bool | NOT NULL, default false | FastAPI-Users: reserved for future operator use |
| `is_verified` | bool | NOT NULL, default false | FastAPI-Users: email verification hook |
| `display_name` | string \| null | max 100 chars | Optional human-readable name |

---

### ProxyKey

A key a user creates and gives to their applications. The proxy uses this key
to identify the calling user and route the request.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK, auto | Row identifier |
| `user_id` | UUID | FK → User.id, NOT NULL, indexed | Owner |
| `key_hash` | string | NOT NULL, UNIQUE, indexed | SHA-256 hex of the plaintext key; used for lookup |
| `key_prefix` | string | NOT NULL, max 8 chars | First 8 chars of plaintext; shown in listings for recognition |
| `key_suffix` | string | NOT NULL, max 4 chars | Last 4 chars of plaintext; shown as masked form |
| `label` | string | max 100 chars, nullable | Human-readable name |
| `is_active` | bool | NOT NULL, default true | False = revoked |
| `created_at` | datetime | NOT NULL | UTC creation timestamp |
| `revoked_at` | datetime | nullable | UTC revocation timestamp |

**Display rule**: Listings show `{key_prefix}...{key_suffix}` (e.g.
`sk-relay-...abc4`). The full plaintext is shown exactly once at creation and
never stored or returned again.

**Security note**: Only the hash is stored. A DB breach does not yield usable
proxy keys.

---

### BackendConfig

A user's configured LLM provider. One active config per user at a time.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK, auto | Row identifier |
| `user_id` | UUID | FK → User.id, NOT NULL, UNIQUE | Owner; UNIQUE enforces one config per user |
| `backend_type` | string | NOT NULL, `openai_compat`\|`ollama` | Backend kind |
| `base_url` | string | NOT NULL | Provider endpoint URL |
| `credential_ciphertext` | string \| null | nullable | Fernet-encrypted provider API key; null for Ollama with no auth |
| `credential_suffix` | string \| null | max 4 chars, nullable | Last 4 chars of the plaintext key; for masked display only |
| `updated_at` | datetime | NOT NULL | UTC last-updated timestamp |

**Security rules**:
- `credential_ciphertext` is the only form persisted; plaintext is never stored.
- `credential_suffix` enables masked display (`****{suffix}`) without
  storing the full key.
- At request time: `credential_ciphertext` is decrypted transiently using the
  `RELAY_ENCRYPT_KEY` env var. The plaintext is placed in the httpx request
  header and then goes out of scope.
- No field in this table appears in any API response except `credential_suffix`
  (as the masked string) and `backend_type` / `base_url`.

---

### UsageRecord

One row per completed proxied request. All rows are user-scoped.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | integer | PK, auto-increment | Row identifier |
| `user_id` | UUID | FK → User.id, NOT NULL, indexed | Owner |
| `timestamp` | datetime | NOT NULL, indexed | UTC time the request completed |
| `proxy_key_id` | UUID | FK → ProxyKey.id, NOT NULL | Which key was used |
| `proxy_key_label` | string | NOT NULL | Denormalised label at write time |
| `backend_type` | string | NOT NULL | `openai_compat` or `ollama` |
| `model` | string | NOT NULL, indexed | Model name as reported by/sent to backend |
| `input_tokens` | integer | NOT NULL, ≥ 0 | Prompt token count |
| `output_tokens` | integer | NOT NULL, ≥ 0 | Completion token count |
| `cost` | float | NOT NULL, ≥ 0.0 | Computed cost in USD (0.0 if no rate configured) |
| `token_count_source` | string | NOT NULL, `exact`\|`estimated` | Provider-reported or tiktoken fallback |
| `status_code` | integer | NOT NULL | HTTP status returned to caller |

**Notes**:
- `proxy_key_label` is denormalised so history survives key renames / revocations.
- No prompt or response content is stored.

---

### CostRate

Operator-configured pricing per model. Shared across all users (set by the
operator in config.yml, not per-user).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `model` | string | PK | Model identifier (must match what backend reports) |
| `input_per_token` | float | NOT NULL, ≥ 0 | USD per input token |
| `output_per_token` | float | NOT NULL, ≥ 0 | USD per output token |

**Note**: CostRate is loaded from `config.yml` at startup, not from SQLite.
It is not a DB table in v2 — operator edits the config file and restarts.
Included here as a logical entity for completeness.

---

## Relationships

```
User (1) ──── (N) ProxyKey
     (1) ──── (0..1) BackendConfig
     (1) ──── (N) UsageRecord

ProxyKey (1) ──── (N) UsageRecord (via proxy_key_id)

CostRate ──── (looked up by model name at UsageRecord write time)
```

---

## Indexes

| Table | Column(s) | Purpose |
|-------|-----------|---------|
| ProxyKey | `user_id` | Listing a user's keys |
| ProxyKey | `key_hash` | O(1) lookup on each proxy request |
| UsageRecord | `user_id` | All dashboard queries |
| UsageRecord | `timestamp` | Time-range aggregations |
| UsageRecord | `model` | Per-model aggregation |
| UsageRecord | `user_id, timestamp` | Combined filter + sort (composite) |

---

## Isolation Invariant

Every query against `ProxyKey`, `BackendConfig`, and `UsageRecord` MUST include
a `WHERE user_id = :current_user_id` clause (or equivalent ORM filter). This is
enforced structurally by requiring `user_id` as a positional argument to all
data-access functions — omission is a type error.

The cross-user access tests in `test_isolation.py` verify this invariant
end-to-end for every data endpoint.
