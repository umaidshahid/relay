# Quickstart: Relay (Multi-User)

**Goal**: Run the stack locally, create an account, configure a backend, and
send a proxied request — all in under 10 minutes.

## Prerequisites

- Docker and Docker Compose
- An OpenAI-compatible API key (or a local Ollama instance)

## 1. Clone and configure

```bash
git clone <repo-url>
cd relay
```

Generate an encryption key (do this once; keep it safe):

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Create `.env` (never commit this file):

```bash
cat > .env << 'EOF'
RELAY_ENCRYPT_KEY=<paste-generated-key>
JWT_SECRET=<random-long-string>
EOF
```

Copy the operator config:

```bash
cp config.yml.example config.yml
# Edit cost_rates if desired
```

## 2. Start the stack

```bash
docker compose up
```

The API is at **http://localhost:8000** and the dashboard at
**http://localhost:8000/dashboard/**.

## 3. Create an account

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"me@example.com","password":"changeme123"}' | jq
```

## 4. Log in

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/jwt/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=me@example.com&password=changeme123" | jq -r .access_token)
echo "Got token: ${TOKEN:0:20}..."
```

## 5. Configure your backend credential

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

## 6. Create a proxy key

```bash
PROXY_KEY=$(curl -s -X POST http://localhost:8000/api/keys \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"label":"my-app"}' | jq -r .key)
echo "Proxy key: $PROXY_KEY"
# Save this — it is shown exactly once
```

## 7. Send a proxied request

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $PROXY_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

The response is identical to calling OpenAI directly.

## 8. View your dashboard

Open **http://localhost:8000/dashboard/** → Log in → your usage appears.

---

## Using Ollama

```bash
# Start with Ollama service
docker compose --profile ollama up

# Configure credential (no API key for Ollama)
curl -s -X PUT http://localhost:8000/api/credentials \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "backend_type": "ollama",
    "base_url": "http://ollama:11434",
    "credential": null
  }'

# Pull a model
docker compose exec ollama ollama pull llama3
```

---

## Production deployment (GCP e2-micro)

1. Copy the repo to the VM.
2. Create `.env` on the VM with `RELAY_ENCRYPT_KEY` and `JWT_SECRET`.
3. Edit `Caddyfile` with your subdomain.
4. `docker compose up -d`
5. Caddy handles HTTPS automatically via Let's Encrypt.

---

## Running tests

```bash
pip install -e ".[dev]"
pytest proxy/tests/
# All tests run without a live backend or network connection
```
