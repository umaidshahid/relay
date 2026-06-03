# Quickstart: Relay

**Goal**: Start Relay and send a proxied chat-completion request in under 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- An OpenAI-compatible API key (or a local Ollama instance)

## 1. Clone and configure

```bash
git clone <repo-url>
cd relay
cp config.yml.example config.yml
```

Edit `config.yml`:

```yaml
backend:
  type: openai_compat
  base_url: https://api.openai.com/v1
  api_key: sk-your-openai-key   # or set BACKEND_API_KEY env var

api_keys:
  - key: sk-relay-myapp
    label: my-app

cost_rates:
  gpt-4o-mini:
    input_per_token: 0.00000015
    output_per_token: 0.0000006
```

## 2. Start the stack

```bash
docker compose up
```

The proxy starts on port 8000. The dashboard is available at
`http://localhost:8000/dashboard/`.

## 3. Send a request

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-relay-myapp" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

You should receive the same JSON response you'd get from the backend directly.

## 4. Check the dashboard

Open `http://localhost:8000/dashboard/` in a browser. You should see:
- Total spend updated to reflect the request you just sent
- One entry in the request log

## Using Ollama (local model)

```bash
docker compose --profile ollama up
```

Update `config.yml`:

```yaml
backend:
  type: ollama
  base_url: http://ollama:11434
```

Then pull a model:

```bash
docker compose exec ollama ollama pull llama3
```

## Running tests (without Docker)

```bash
pip install -e ".[dev]"
pytest proxy/tests/
```

All tests run without a live backend.
