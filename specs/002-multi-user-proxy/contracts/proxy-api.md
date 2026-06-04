# Contract: Proxy API

**Base path**: `/v1`
**Auth**: `Authorization: Bearer <proxy-key>` (NOT the JWT session token)

The proxy key identifies the calling user. The system looks up the key owner,
loads and decrypts their backend credential, and forwards the request.

---

## GET /v1/models

Return an OpenAI-shaped model list for the key owner's configured backend.

**Behaviour**:
- Ollama backend: fetches `/api/tags` from the user's Ollama URL → converts to
  OpenAI model objects.
- OpenAI-compat backend: proxies `GET /models` to the upstream.

### Response — 200 OK

```json
{
  "object": "list",
  "data": [
    { "id": "gpt-4o-mini", "object": "model", "created": 1700000000, "owned_by": "openai" }
  ]
}
```

### Errors

| Status | Condition |
|--------|-----------|
| 401 | Missing, unknown, or revoked proxy key |
| 503 | User's backend is unreachable |

---

## POST /v1/chat/completions

Forward a chat-completion request to the key owner's configured backend.

### Request

Standard OpenAI chat-completion request body. Passed through to the backend
unchanged (except `stream_options` injection for streaming calls — see below).

```
POST /v1/chat/completions
Authorization: Bearer <proxy-key>
Content-Type: application/json

{
  "model": "gpt-4o-mini",
  "messages": [{"role": "user", "content": "Hello!"}]
}
```

### Response — non-streaming

Backend response forwarded unchanged.

### Response — streaming (`"stream": true`)

Server-Sent Events forwarded verbatim from the backend as they arrive.
`stream_options: {include_usage: true}` is injected for OpenAI-compat backends.

### Errors

| Status | Condition |
|--------|-----------|
| 401 | Missing, unknown, or revoked proxy key |
| 400 | User has no configured backend |
| 502 | Backend returned an error (forwarded) |
| 503 | Backend unreachable |

**Security**: The user's decrypted provider credential is used only to construct
the upstream Authorization header. It is never included in any response or log.

---

## Security Notes

- The proxy key in the Authorization header is hashed on lookup; the plaintext
  is never stored or logged.
- The user's provider credential is decrypted transiently in memory for the
  duration of a single request only.
- Error responses from the backend are forwarded but any credential data is
  stripped from error bodies before forwarding.
