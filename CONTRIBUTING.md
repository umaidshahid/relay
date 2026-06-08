# Contributing to Relay

Thanks for taking the time to contribute! Here's everything you need to get started.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Running Tests](#running-tests)
- [Submitting Changes](#submitting-changes)
- [Code Style](#code-style)

---

## Getting Started

1. **Fork** the repo and clone your fork:

   ```bash
   git clone https://github.com/<your-username>/relay.git
   cd relay
   ```

2. Create a feature branch:

   ```bash
   git checkout -b feat/your-feature-name
   ```

---

## Development Setup

### Backend (Python)

Relay uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
pip install uv
uv sync --extra dev
```

Or with plain pip:

```bash
pip install -e ".[dev]"
```

### Environment variables

Create a `.env` file (never commit this):

```bash
cat > .env << 'EOF'
RELAY_ENCRYPT_KEY=<generate with: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
JWT_SECRET=<any random string at least 32 chars>
EOF
```

### Frontend (Dashboard)

```bash
cd dashboard
npm install
npm run dev
```

### Full stack via Docker

```bash
docker compose up
```

The API will be at `http://localhost:8000` and the dashboard at `http://localhost:8000/dashboard/`.

---

## Project Structure

```
relay/
├── proxy/               # FastAPI backend
│   ├── auth.py          # JWT + user auth
│   ├── backends/        # LLM provider adapters
│   ├── db/              # Database models and migrations
│   ├── routers/         # API route handlers
│   ├── metering.py      # Token usage tracking
│   ├── crypto.py        # Credential encryption
│   └── tests/           # Backend test suite
├── dashboard/           # React frontend
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## Running Tests

The full test suite runs without a live backend or network connection:

```bash
pytest proxy/tests/
```

Please add or update tests for any behavior you change.

---

## Submitting Changes

1. Make sure all tests pass: `pytest proxy/tests/`
2. Push your branch and open a **Pull Request** against `main`
3. Fill out the PR description — what changed and why
4. A maintainer will review and merge

**Small, focused PRs are much easier to review than large ones.** If you're planning a big change, open an issue first to discuss the approach.

---

## Code Style

- **Python**: formatted with [ruff](https://github.com/astral-sh/ruff). Run `ruff format .` before committing.
- **TypeScript/React**: follow the existing patterns in `dashboard/`.
- Don't add comments that just restate what the code does.

---

## Reporting Bugs

Open a GitHub Issue with:
- Steps to reproduce
- Expected vs. actual behavior
- Relay version / commit hash
- Relevant logs or error output

---

## Feature Requests

Open a GitHub Issue describing the use case and why the current behavior doesn't cover it. PRs without a linked issue may be closed if the feature doesn't fit the project's scope.
