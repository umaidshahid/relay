# Data Model: LLM Proxy with Usage Metering

**Date**: 2026-06-03

## Entities

### UsageRecord

One row per completed proxied request. This is the core persistent entity.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | integer | PK, auto-increment | Row identifier |
| `timestamp` | datetime | NOT NULL, indexed | UTC time the request completed |
| `api_key_label` | string | NOT NULL | Display label of the API key used |
| `backend` | string | NOT NULL | Backend identifier (e.g. `openai_compat`, `ollama`) |
| `model` | string | NOT NULL | Model name as reported by or sent to the backend |
| `input_tokens` | integer | NOT NULL, ≥ 0 | Prompt / input token count |
| `output_tokens` | integer | NOT NULL, ≥ 0 | Completion / output token count |
| `cost` | float | NOT NULL, ≥ 0.0 | Computed cost in USD |
| `token_count_source` | string | NOT NULL, `exact`\|`estimated` | Whether counts came from provider or tiktoken |
| `status_code` | integer | NOT NULL | HTTP status code returned to the client |

**Notes**:
- No prompt or response content is stored — only token counts and metadata.
- `cost = 0.0` when no rate is configured for the model; `token_count_source`
  still reflects how tokens were counted.
- Error responses (status ≥ 400) are recorded with `input_tokens = 0`,
  `output_tokens = 0`, `cost = 0.0`.
- Interrupted streams are recorded with whatever token counts were observed
  at the time of interruption; `token_count_source` applies to those partial
  counts.

---

### Configuration (file-based, not a DB table)

API keys and cost rates live in `config.yml` and are loaded at startup. They
are not stored in SQLite.

#### ApiKey (config entry)

| Field | Type | Description |
|-------|------|-------------|
| `key` | string | The secret value clients send in `Authorization: Bearer <key>` |
| `label` | string | Human-readable name stored in `UsageRecord.api_key_label` |

#### CostRate (config entry)

| Field | Type | Description |
|-------|------|-------------|
| `model` | string | Model identifier (must match what the backend reports) |
| `input_per_token` | float | USD cost per input token |
| `output_per_token` | float | USD cost per output token |

#### BackendConfig (config entry)

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `openai_compat` or `ollama` |
| `base_url` | string | Base URL of the backend endpoint |
| `api_key` | string \| None | Credential forwarded to the backend (env-overridable) |

---

## Value Objects (in-memory only)

### UsageData

Returned by backend adapters; never persisted directly.

```python
@dataclass
class UsageData:
    input_tokens: int
    output_tokens: int
    source: Literal["exact", "estimated"]
```

### ChatRequest / ChatResponse

Thin wrappers around the incoming request body and outgoing response. Not
persisted — exist only for the duration of a request.

---

## Relationships

```
config.yml
  └── ApiKey[]           (looked up by incoming Bearer token)
  └── CostRate[]         (looked up by model name at record-write time)
  └── BackendConfig      (single active backend)

UsageRecord
  └── api_key_label      (denormalised from ApiKey.label at write time)
  └── model              (from request or backend response)
  └── backend            (from BackendConfig.type)
```

Denormalising `api_key_label` into `UsageRecord` means historical records
remain accurate even if a key is renamed or removed from config later.

---

## Indexes

- `UsageRecord.timestamp` — for time-range queries in dashboard stats
- `UsageRecord.api_key_label` — for per-key aggregation
- `UsageRecord.model` — for per-model aggregation
