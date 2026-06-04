# Research: Multi-User LLM Proxy

**Date**: 2026-06-03

## Decision Log

### 1. Authentication Library

**Decision**: FastAPI-Users with SQLAlchemy (SQLModel-compatible) backend, JWT
bearer tokens for API access, cookie-based sessions for browser clients.

**Rationale**: FastAPI-Users is the de-facto standard for self-hosted auth in
FastAPI applications. It provides: bcrypt password hashing, email verification
hooks, JWT and cookie transport, and a UserManager base class for customisation.
It integrates directly with SQLAlchemy async sessions and therefore works with
SQLModel. Using a maintained library for auth reduces the risk of subtle
implementation errors (timing attacks, hash misuse, token replay).

**FastAPI-Users wiring summary**:
```python
# User table extends fastapi_users.db.SQLAlchemyBaseUserTableUUID
# UserDatabase wraps the async session
# UserManager subclasses BaseUserManager[User, UUID]
# auth_backend = AuthenticationBackend(name="jwt", transport=BearerTransport,
#     get_strategy=lambda: JWTStrategy(secret=SECRET, lifetime=3600))
# fastapi_users = FastAPIUsers[User, UUID](get_user_manager, [auth_backend])
# app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt")
# app.include_router(fastapi_users.get_register_router(...), prefix="/auth")
```

The `current_active_user` dependency from FastAPI-Users is wrapped in
`proxy/deps.py` and re-exported as `get_current_user` for all session-
authenticated routes.

**Alternatives considered**:
- Hand-rolled JWT auth: higher implementation risk; no bcrypt handling out of box
- Authlib: more complex, designed for OAuth server use cases, heavier
- External provider (Auth0, Clerk): ruled out per user specification

---

### 2. Encryption for Provider Credentials

**Decision**: Fernet symmetric authenticated encryption (`cryptography` library)

**Rationale**: Fernet provides AES-128-CBC + HMAC-SHA256 in a single
authenticated operation — any tampering with ciphertext is detected before
decryption. The key is a URL-safe base64-encoded 32-byte value, easily supplied
via environment variable. One-line encrypt/decrypt API reduces the surface area
for implementation mistakes.

AES-256-GCM (via `cryptography.hazmat`) is a valid alternative with a slightly
larger key and authenticated encryption natively, but requires managing nonces
manually. Fernet's simpler API is preferred for this project's scope given the
equivalent security guarantees.

**Key management**:
- Key generated once: `Fernet.generate_key()` → stored in systemd environment
  (`/etc/relay.env`) and passed to the Docker container via `docker-compose.yml`
  `environment:` block referencing a `.env` file on the VM.
- Key NEVER committed to the repo; `.env` is in `.gitignore`.
- `proxy/crypto.py` exposes:
  ```python
  def encrypt_credential(plaintext: str, key: bytes) -> str: ...
  def decrypt_credential(ciphertext: str, key: bytes) -> str: ...
  def mask_credential(plaintext: str) -> str:  # returns "****" + last4
  ```
- `decrypt_credential` is called only inside the proxy request path, immediately
  before constructing the httpx request. The decrypted value is never assigned
  to a variable that persists beyond the request function scope.

**Alternatives considered**:
- AES-GCM via hazmat: equivalent security, more code surface area, chosen Fernet
  for simplicity
- Key stored in DB alongside ciphertext: defeated by a single DB breach — ruled
  out by Constitution §II

---

### 3. User-Scoped Data Access Pattern

**Decision**: Shared `deps.py` dependency that injects `current_user_id` as a
required argument to all data-access functions.

**Rationale**: Making user_id a required function parameter (not a global or
optional argument) means the type checker will catch any omission at development
time. Every query uses a pattern like:

```python
async def get_proxy_keys(user_id: UUID, session: AsyncSession) -> list[ProxyKey]:
    result = await session.exec(
        select(ProxyKey).where(ProxyKey.user_id == user_id, ProxyKey.is_active == True)
    )
    return result.all()
```

Routes are structured as:
```python
@router.get("/api/keys")
async def list_keys(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session_dep),
):
    return await get_proxy_keys(user.id, session)
```

**Cross-user access tests** (`test_isolation.py`) register two users, seed data
for each, then attempt every data endpoint as user B requesting user A's resource
IDs. All such attempts MUST return 403 or 404.

**Alternatives considered**:
- Row-level security in the DB: SQLite doesn't support it; PostgreSQL path would
  benefit from this later
- Middleware-based filtering: harder to test in isolation; filter logic mixed
  with HTTP concerns

---

### 4. Proxy Key Auth vs Session Auth

**Decision**: `/v1/*` endpoints authenticate by proxy key (Bearer token in
Authorization header, looked up in `proxy_keys` table). All other API endpoints
(`/api/*`, `/stats/*`) authenticate by FastAPI-Users JWT session.

**Rationale**: The proxy endpoint is used by non-browser applications (OpenWebUI,
curl, etc.) that supply a static key — the same UX as the v1 single-operator
design. The dashboard and settings APIs are used by the browser SPA with a
FastAPI-Users JWT.

**Proxy key lookup**:
```python
async def get_user_by_proxy_key(key: str, session: AsyncSession) -> User | None:
    result = await session.exec(
        select(User)
        .join(ProxyKey, ProxyKey.user_id == User.id)
        .where(ProxyKey.key_hash == hash_key(key), ProxyKey.is_active == True)
    )
    return result.first()
```

Proxy keys are stored as SHA-256 hashes in the DB (the plaintext is shown once
at creation only). The full plaintext is never stored.

---

### 5. Dashboard Auth Gating

**Decision**: React Router + `AuthContext` (`auth.tsx`). All routes except
`/login` and `/signup` are wrapped in a `<RequireAuth>` component that checks
for a valid JWT in localStorage (or httpOnly cookie) and redirects to `/login`
if absent. The JWT is obtained via `POST /auth/jwt/login` (FastAPI-Users).

**Alternatives considered**:
- Server-side rendering with session cookies: ruled out (Vite SPA is the
  existing choice)
- Storing JWT in httpOnly cookie: more CSRF-safe; feasible as a follow-up;
  localStorage is acceptable for the v2 SPA scope

---

### 6. Deployment: GCP e2-micro + Docker + Caddy

**Decision**: Single `docker-compose.yml` with two services: `proxy` (FastAPI +
uvicorn) and `caddy` (Caddy v2 reverse-proxy).

**Caddy** handles:
- Automatic TLS from Let's Encrypt for the subdomain
- HTTP → HTTPS redirect
- Reverse proxy to `proxy:8000`
- `X-Forwarded-For` / `Proxy-Proto` headers for uvicorn (`--proxy-headers`)

**Caddyfile** (minimal):
```
relay.example.com {
    reverse_proxy proxy:8000
}
```

**Encryption key** supplied via `.env` file on the VM (not committed):
```
RELAY_ENCRYPT_KEY=<base64-fernet-key>
JWT_SECRET=<random-string>
```

Referenced in `docker-compose.yml`:
```yaml
env_file: .env
```

SQLite file volume-mounted from VM disk:
```yaml
volumes:
  - /opt/relay/data:/data
```

**Alternatives considered**:
- Nginx + certbot: more configuration, no auto-renewal simplicity
- Traefik: heavier for a single-service deployment
- Cloud Run: doesn't support persistent SQLite; PostgreSQL required for that path

---

### 7. FastAPI-Users + SQLModel Compatibility

**Decision**: Declare the `User` table by inheriting from both
`fastapi_users_db_sqlalchemy.SQLAlchemyBaseUserTableUUID` and `SQLModel` with
`table=True`. Use the `AsyncSession` from SQLModel's async engine.

**Known integration note**: FastAPI-Users' `SQLAlchemyUserDatabase` expects a
`SQLAlchemy` `AsyncSession`, which is what SQLModel's `AsyncSession` is under
the hood. The integration works without an adapter layer. See FastAPI-Users docs
for the pattern.

```python
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlmodel import SQLModel, Field
import uuid

class User(SQLAlchemyBaseUserTableUUID, SQLModel, table=True):
    __tablename__ = "users"
    # FastAPI-Users adds: id, email, hashed_password, is_active, is_superuser,
    #                      is_verified
    display_name: str | None = Field(default=None, max_length=100)
```

---

### 8. Build Order Rationale

The 8-phase build order (from user specification) ensures security is never
deferred:

1. FastAPI-Users auth wiring → establishes user_id provenance
2. user_id FK on schema + `deps.py` scoping dependency → structural isolation
3. Migrate existing endpoints (stats, proxy) → user-scoped, with cross-user tests
4. Encrypted credential storage → Constitution §II encryption rules met
5. Proxy key ownership + per-user backend forwarding → full proxy path complete
6. Credential + key management UIs → self-service frontend complete
7. OAuth (GitHub/Google) → optional enhancement
8. Deploy to GCP e2-micro → production
