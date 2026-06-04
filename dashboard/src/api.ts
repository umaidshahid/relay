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

async function get<T>(path: string, token?: string | null): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const response = await fetch(path, { headers });
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

export async function logout(token: string): Promise<void> {
  await fetch("/auth/jwt/logout", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function getMe(token: string): Promise<UserInfo> {
  return get<UserInfo>("/auth/me", token);
}

// ---------------------------------------------------------------------------
// Stats endpoints (all require JWT)
// ---------------------------------------------------------------------------

export function getSummary(token: string): Promise<Summary> {
  return get<Summary>("/stats/summary", token);
}

export function getByKey(token: string): Promise<KeyBreakdown[]> {
  return get<KeyBreakdown[]>("/stats/by-key", token);
}

export function getByModel(token: string): Promise<ModelBreakdown[]> {
  return get<ModelBreakdown[]>("/stats/by-model", token);
}

export function getTimeseries(token: string, days = 30): Promise<TimeseriesPoint[]> {
  return get<TimeseriesPoint[]>(`/stats/timeseries?days=${days}`, token);
}

export function getRequests(
  token: string,
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
