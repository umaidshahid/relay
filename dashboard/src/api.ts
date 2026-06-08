import type {
  CreateKeyResponse,
  CredentialResponse,
  KeyBreakdown,
  ModelBreakdown,
  ProxyKeyResponse,
  RequestsResponse,
  Summary,
  TimeseriesPoint,
  UserInfo,
} from "./types";

// ---------------------------------------------------------------------------
// Base fetch helpers
// ---------------------------------------------------------------------------

// credentials: "include" sends the httpOnly `relay_session` cookie set by the
// OAuth flow, so OAuth users authenticate even without a bearer token in
// localStorage. Password users still send Authorization: Bearer.
async function get<T>(path: string, token?: string | null): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const response = await fetch(path, { headers, credentials: "include" });
  if (!response.ok) throw new Error(`API error ${response.status}: ${path}`);
  return response.json() as Promise<T>;
}

async function post<T>(
  path: string,
  body: unknown,
  token?: string | null
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const response = await fetch(path, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`API error ${response.status}: ${path}`);
  return response.json() as Promise<T>;
}


async function patch<T>(
  path: string,
  body: unknown,
  token?: string | null
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const response = await fetch(path, {
    method: "PATCH",
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`API error ${response.status}: ${path}`);
  return response.json() as Promise<T>;
}

async function del(path: string, token?: string | null): Promise<void> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const response = await fetch(path, { method: "DELETE", headers });
  if (!response.ok) throw new Error(`API error ${response.status}: ${path}`);
}

// ---------------------------------------------------------------------------
// Auth endpoints
// ---------------------------------------------------------------------------

export async function register(email: string, password: string): Promise<UserInfo> {
  const response = await fetch("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(
      (err as { detail?: string }).detail || `Registration failed (${response.status})`
    );
  }
  return response.json() as Promise<UserInfo>;
}

export async function login(
  email: string,
  password: string
): Promise<{ access_token: string; token_type: string }> {
  const body = new URLSearchParams({ username: email, password });
  const response = await fetch("/auth/jwt/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!response.ok) {
    throw new Error(`Login failed (${response.status})`);
  }
  return response.json();
}

export async function logout(token: string | null): Promise<void> {
  // Clear the bearer session (if any)…
  if (token) {
    await fetch("/auth/jwt/logout", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    }).catch(() => {});
  }
  // …and the OAuth cookie session (if any). The cookie backend's logout
  // expires the relay_session cookie.
  await fetch("/auth/cookie/logout", {
    method: "POST",
    credentials: "include",
  }).catch(() => {});
}

// token is optional: OAuth users have no bearer token and authenticate via the
// httpOnly cookie that `credentials: "include"` sends automatically.
export function getMe(token?: string | null): Promise<UserInfo> {
  return get<UserInfo>("/auth/me", token);
}

// ---------------------------------------------------------------------------
// OAuth
// ---------------------------------------------------------------------------

export interface AuthConfig {
  google: boolean;
  github: boolean;
}

export function getAuthConfig(): Promise<AuthConfig> {
  return get<AuthConfig>("/auth/config");
}

/**
 * Begin the OAuth sign-in flow for a provider.
 *
 * Asks the backend for the provider's authorization URL (the backend embeds a
 * signed state param and the request-derived callback URL), then sends the
 * browser there. After the user approves, the provider redirects to
 * /auth/{provider}/callback, which sets the httpOnly session cookie.
 */
export async function startOAuth(provider: "google" | "github"): Promise<void> {
  const res = await fetch(`/auth/${provider}/authorize`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Could not start ${provider} sign-in`);
  const { authorization_url } = (await res.json()) as {
    authorization_url: string;
  };
  window.location.href = authorization_url;
}

// ---------------------------------------------------------------------------
// Stats endpoints (all require JWT)
// ---------------------------------------------------------------------------

// token is optional: OAuth users have no bearer token and authenticate via the
// httpOnly cookie that get()'s credentials: "include" sends automatically.
export function getSummary(token?: string | null): Promise<Summary> {
  return get<Summary>("/stats/summary", token);
}

export function getByKey(token?: string | null): Promise<KeyBreakdown[]> {
  return get<KeyBreakdown[]>("/stats/by-key", token);
}

export function getByModel(token?: string | null): Promise<ModelBreakdown[]> {
  return get<ModelBreakdown[]>("/stats/by-model", token);
}

export function getTimeseries(token?: string | null, days = 30): Promise<TimeseriesPoint[]> {
  return get<TimeseriesPoint[]>(`/stats/timeseries?days=${days}`, token);
}

export function getRequests(
  token?: string | null,
  limit = 50,
  offset = 0
): Promise<RequestsResponse> {
  return get<RequestsResponse>(
    `/stats/requests?limit=${limit}&offset=${offset}`,
    token
  );
}

// ---------------------------------------------------------------------------
// Proxy key endpoints
// ---------------------------------------------------------------------------

export function getKeys(token: string): Promise<ProxyKeyResponse[]> {
  return get<ProxyKeyResponse[]>("/api/keys", token);
}

export function createKey(
  token: string,
  payload: { label?: string; backend_config_id: string; requests_per_minute?: number | null }
): Promise<CreateKeyResponse> {
  return post<CreateKeyResponse>("/api/keys", payload, token);
}

export function updateKey(
  token: string,
  keyId: string,
  payload: { label?: string; backend_config_id?: string; requests_per_minute?: number | null }
): Promise<ProxyKeyResponse> {
  return patch<ProxyKeyResponse>(`/api/keys/${keyId}`, payload, token);
}

export async function revokeKey(token: string, keyId: string): Promise<void> {
  return del(`/api/keys/${keyId}`, token);
}

// ---------------------------------------------------------------------------
// Credential endpoints
// ---------------------------------------------------------------------------

export function getCredentials(token: string): Promise<CredentialResponse[]> {
  return get<CredentialResponse[]>("/api/credentials", token);
}

export function createCredential(
  token: string,
  payload: { name: string; backend_type: string; base_url: string; credential?: string | null }
): Promise<CredentialResponse> {
  return post<CredentialResponse>("/api/credentials", payload, token);
}

export function updateCredential(
  token: string,
  id: string,
  payload: { name?: string; backend_type?: string; base_url?: string; credential?: string | null }
): Promise<CredentialResponse> {
  return patch<CredentialResponse>(`/api/credentials/${id}`, payload, token);
}

export function deleteCredential(token: string, id: string): Promise<void> {
  return del(`/api/credentials/${id}`, token);
}
