# Relay

A self-hosted HTTP proxy that sits between your applications and LLM backends,
recording token usage and cost for every request.

## Quick Start (under 5 minutes)

### 1. Configure

```bash
cp config.yml.example config.yml
```

Edit `config.yml` — set your backend URL and API key, and add at least one
client API key:

```yaml
backend:
  type: openai_compat
  base_url: https://api.openai.com/v1
  api_key: sk-your-openai-key

api_keys:
  - key: sk-relay-myapp
    label: my-app

cost_rates:
  gpt-4o-mini:
    input_per_token: 0.00000015
    output_per_token: 0.00000060
```

### 2. Start

```bash
docker compose up
```

The proxy starts on **port 8000**.
The dashboard is at **http://localhost:8000/dashboard/**.

### 3. Send a request

Point your application at the proxy instead of the backend directly.
Pass one of your configured API keys:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-relay-myapp" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

The response is identical to calling the backend directly.

### 4. View usage

Open **http://localhost:8000/dashboard/** in your browser to see:
- Total spend
- Spend per API key and per model
- Daily cost chart
- Full request log

---

## Using Ollama (local models)

```bash
docker compose --profile ollama up
```

Update `config.yml`:

```yaml
backend:
  type: ollama
  base_url: http://ollama:11434
```

Pull a model inside the Ollama container:

```bash
docker compose exec ollama ollama pull llama3
```

---

## Configuration Reference

| Key | Description |
|-----|-------------|
| `backend.type` | `openai_compat` or `ollama` |
| `backend.base_url` | Base URL of the backend (no trailing slash) |
| `backend.api_key` | Credential forwarded to the backend. Use `${VAR}` for env var interpolation, or set `BACKEND_API_KEY` env var |
| `api_keys[].key` | Secret token clients send in `Authorization: Bearer <key>` |
| `api_keys[].label` | Human-readable name stored in usage records |
| `cost_rates.<model>.input_per_token` | USD cost per input token |
| `cost_rates.<model>.output_per_token` | USD cost per output token |

If a model has no configured rate, its cost is recorded as `0.0`.

---

## Running Tests

```bash
pip install -e ".[dev]"
pytest proxy/tests/
```

All tests run without a live backend or network connection.

---

## Architecture

```
Client app
    │  Authorization: Bearer sk-relay-*
    ▼
┌─────────────────────┐
│  Relay (FastAPI)     │
│  POST /v1/chat/      │
│  completions         │
│                     │
│  ┌───────────────┐  │
│  │ BackendAdapter│  │   Writes UsageRecord to SQLite
│  │  openai_compat│  │──────────────────────────────►
│  │  ollama       │  │
│  └───────────────┘  │
└─────────────────────┘
    │  (identical response)
    ▼
Backend LLM API
```

Token counts come from the backend's own `usage` field whenever available
(`exact`). Only when the backend returns no usage does Relay fall back to
a tiktoken estimate, which is always labelled `estimated` in the dashboard.
