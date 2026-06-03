# Contract: Proxy API

**Service**: Relay proxy
**Base path**: `/v1`
**Auth**: `Authorization: Bearer <api-key>` on all endpoints

---

## POST /v1/chat/completions

Accepts a chat-completion request, forwards it to the configured backend,
and returns the backend's response. Functionally identical to calling the
backend directly.

### Request

```
POST /v1/chat/completions
Authorization: Bearer sk-relay-abc123
Content-Type: application/json
```

Body: standard OpenAI chat-completion request object. Relay passes the body
through to the backend unchanged, with one modification for streaming calls
(see below).

**Streaming**: when `"stream": true` is present, Relay injects
`"stream_options": {"include_usage": true}` before forwarding (OpenAI-compat
backends) so the final chunk contains usage data. This injection is transparent
to the client.

### Response — non-streaming

```
HTTP 200 OK
Content-Type: application/json
```

Body: backend's response object, forwarded unchanged.

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "model": "gpt-4o",
  "choices": [...],
  "usage": {
    "prompt_tokens": 42,
    "completion_tokens": 18,
    "total_tokens": 60
  }
}
```

### Response — streaming

```
HTTP 200 OK
Content-Type: text/event-stream
```

Server-Sent Events forwarded verbatim from the backend as they arrive.
Each chunk is a `data: {...}` line. The final chunk (OpenAI-compat) contains
`usage` when `include_usage` was injected.

### Error responses

| Status | Condition |
|--------|-----------|
| 401 | Missing or unrecognised `Authorization` header |
| 502 | Backend returned an error; body contains the backend error forwarded as-is |
| 503 | Backend unreachable |

On 401, the request is rejected before it reaches the backend and no usage
record is created.

On 502/503, the error response is forwarded to the client and a usage record
is created with `input_tokens = 0`, `output_tokens = 0`, `cost = 0.0`.

---

## GET /health

Liveness check. Returns 200 with `{"status": "ok"}`. No auth required.
