# Contract: Auth API

**Provider**: FastAPI-Users (self-hosted)
**Base path**: `/auth`
**Auth**: None required on these endpoints (they establish auth)

---

## POST /auth/register

Create a new user account.

### Request

```json
{
  "email": "user@example.com",
  "password": "mysecretpassword"
}
```

### Response — 201 Created

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "is_active": true,
  "is_superuser": false,
  "is_verified": false
}
```

### Errors

| Status | Condition |
|--------|-----------|
| 400 | Email already registered, or password too short |
| 422 | Malformed request body |

---

## POST /auth/jwt/login

Authenticate and receive a JWT bearer token.

### Request

`Content-Type: application/x-www-form-urlencoded`

```
username=user@example.com&password=mysecretpassword
```

### Response — 200 OK

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

### Errors

| Status | Condition |
|--------|-----------|
| 400 | Invalid credentials |
| 400 | Account inactive |

---

## POST /auth/jwt/logout

Invalidate the current JWT (adds to a denylist if configured; for stateless JWT
this is a client-side action but the endpoint exists for convention).

**Auth**: `Authorization: Bearer <jwt>`

### Response — 200 OK

```json
{}
```

---

## GET /auth/me

Return the currently authenticated user's profile.

**Auth**: `Authorization: Bearer <jwt>`

### Response — 200 OK

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "is_active": true,
  "is_superuser": false,
  "is_verified": false
}
```

---

## PATCH /auth/me

Update the authenticated user's profile (password change, display name).

**Auth**: `Authorization: Bearer <jwt>`

### Request

```json
{
  "password": "newpassword"
}
```

### Response — 200 OK

Updated user object (same shape as GET /auth/me).
