# Contract: Settings API

**Base path**: `/api`
**Auth**: `Authorization: Bearer <jwt>` (FastAPI-Users session token) on all endpoints

---

## Proxy Key Management

### GET /api/keys

List the authenticated user's proxy keys (masked).

### Response — 200 OK

```json
[
  {
    "id": "uuid",
    "label": "my-app",
    "display": "sk-relay-...abc4",
    "is_active": true,
    "created_at": "2026-06-03T10:00:00Z"
  }
]
```

`display` format: `{key_prefix}...{key_suffix}` — never the full plaintext.

---

### POST /api/keys

Create a new proxy key.

### Request

```json
{ "label": "my-app" }
```

### Response — 201 Created

```json
{
  "id": "uuid",
  "label": "my-app",
  "key": "sk-relay-<random-full-value>",
  "display": "sk-relay-...abc4",
  "created_at": "2026-06-03T10:00:00Z"
}
```

`key` is the full plaintext — returned exactly once. All subsequent responses
use `display` only.

---

### DELETE /api/keys/{key_id}

Revoke a proxy key owned by the authenticated user.

### Response — 204 No Content

### Errors

| Status | Condition |
|--------|-----------|
| 404 | Key not found, or belongs to a different user |

---

## Backend Credential Management

### GET /api/credentials

Return the authenticated user's current backend configuration (masked).

### Response — 200 OK (configured)

```json
{
  "backend_type": "openai_compat",
  "base_url": "https://api.openai.com/v1",
  "credential_masked": "****6789",
  "updated_at": "2026-06-03T10:00:00Z"
}
```

`credential_masked` is `****{last_4}`. The full credential is never returned.

### Response — 200 OK (not yet configured)

```json
null
```

---

### PUT /api/credentials

Create or replace the authenticated user's backend credential.

### Request

```json
{
  "backend_type": "openai_compat",
  "base_url": "https://api.openai.com/v1",
  "credential": "sk-real-provider-key-here"
}
```

For Ollama with no auth key:

```json
{
  "backend_type": "ollama",
  "base_url": "http://192.168.1.10:11434",
  "credential": null
}
```

### Response — 200 OK

```json
{
  "backend_type": "openai_compat",
  "base_url": "https://api.openai.com/v1",
  "credential_masked": "****here",
  "updated_at": "2026-06-03T10:00:00Z"
}
```

The `credential` field from the request is never echoed back. Only the masked
form is returned.

### Errors

| Status | Condition |
|--------|-----------|
| 400 | Missing required field or invalid backend_type |
| 422 | Malformed request body |

---

### DELETE /api/credentials

Remove the authenticated user's backend configuration.

### Response — 204 No Content
