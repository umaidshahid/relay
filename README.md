# Relay

A self-hosted multi-user LLM proxy. Each user signs up, configures their own
backend credential, creates proxy API keys, and sends requests through them.
The proxy meters token usage and cost per user. A React dashboard shows each
user only their own data.

## Quick Start (under 5 minutes)

### 1. Clone and configure

```bash
git clone <repo-url>
cd relay
```

Generate a Fernet encryption key (do this once; keep it safe):

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Create `.env` (never commit this file):

```bash
cat > .env << 'EOF'
RELAY_ENCRYPT_KEY=<paste-generated-key>
JWT_SECRET=<random-string-at-least-32-chars>
EOF
```

Optionally, set per-model cost rates. If you skip this, all usage costs are
recorded as `0.0`:

```bash
cp config.yml.example config.yml
# Edit cost_rates, then mount it into the proxy container if desired
```

### 2. Start

```bash
docker compose up
```

The API is at **http://localhost:8000** and the dashboard at
**http://localhost:8000/dashboard/**.

### 3. Create an account

Open **http://localhost:8000/dashboard/** in your browser, click **Sign up**,
and create an account.

Or via curl:

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"me@example.com","password":"changeme123"}' | jq
```

### 4. Log in and get a JWT

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/jwt/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=me@example.com&password=changeme123" | jq -r .access_token)
```

### 5. Configure your LLM backend

```bash
curl -s -X PUT http://localhost:8000/api/credentials \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "backend_type": "openai_compat",
    "base_url": "https://api.openai.com/v1",
    "credential": "sk-your-openai-key"
  }' | jq
# Response shows credential_masked: "****<last4>" — never the full key
```

### 6. Create a proxy key

```bash
PROXY_KEY=$(curl -s -X POST http://localhost:8000/api/keys \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"label":"my-app"}' | jq -r .key)
echo "Proxy key: $PROXY_KEY"
# Save this — it is shown exactly once
```

### 7. Send a proxied request

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $PROXY_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### 8. View your dashboard

Open **http://localhost:8000/dashboard/** → log in → your usage appears.

---

## Using Ollama (local models)

```bash
docker compose --profile ollama up
```

Configure credential (no API key for Ollama):

```bash
curl -s -X PUT http://localhost:8000/api/credentials \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"backend_type":"ollama","base_url":"http://ollama:11434","credential":null}'
```

Pull a model:

```bash
docker compose exec ollama ollama pull llama3
```

---

## Production deployment (GCP e2-micro)

1. Copy the repo to the VM.
2. Create `.env` on the VM with `RELAY_ENCRYPT_KEY` and `JWT_SECRET`.
3. Edit `Caddyfile` — replace `relay.example.com` with your subdomain.
4. `docker compose up -d`

Caddy handles HTTPS automatically via Let's Encrypt.

---

## Running Tests

```bash
pip install -e ".[dev]"
pytest proxy/tests/
# All tests run without a live backend or network connection
```

---

## Configuration Reference

`config.yml` contains only operator-level settings (cost rates).
Per-user backend credentials are stored encrypted in the database.

| Key | Description |
|-----|-------------|
| `cost_rates.<model>.input_per_token` | USD cost per input token |
| `cost_rates.<model>.output_per_token` | USD cost per output token |

If a model has no configured rate, its cost is recorded as `0.0`.

**Required environment variables** (set in `.env`):

| Variable | Description |
|----------|-------------|
| `RELAY_ENCRYPT_KEY` | Fernet key for encrypting provider credentials (generate once with `Fernet.generate_key()`) |
| `JWT_SECRET` | Secret for signing JWT sessions (any random string ≥ 32 chars) |
