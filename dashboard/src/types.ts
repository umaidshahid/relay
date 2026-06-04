// TypeScript interfaces matching contracts/*.md

// --- Auth ---

export interface UserInfo {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
}

// --- Stats ---

export interface Summary {
  total_cost: number;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  avg_tokens_per_second: number | null;
}

export interface KeyBreakdown {
  proxy_key_id: string;
  proxy_key_label: string;
  total_cost: number;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
}

export interface ModelBreakdown {
  model: string;
  backend_type: string;
  total_cost: number;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
}

export interface TimeseriesPoint {
  date: string;
  total_cost: number;
  total_requests: number;
  avg_tokens_per_second: number | null;
}

export interface RequestRecord {
  id: number;
  timestamp: string;
  proxy_key_label: string;
  model: string;
  backend_type: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  token_count_source: "exact" | "estimated";
  status_code: number;
  tokens_per_second: number | null;
}

export interface RequestsResponse {
  total: number;
  offset: number;
  limit: number;
  items: RequestRecord[];
}

// --- Proxy Keys ---

export interface ProxyKeyResponse {
  id: string;
  label: string | null;
  display: string;
  is_active: boolean;
  created_at: string;
  backend_config_id: string | null;
  backend_name: string | null;
  requests_per_minute: number | null;
}

export interface CreateKeyResponse extends ProxyKeyResponse {
  key: string; // full value — shown exactly once
}

// --- Credentials ---

export interface CredentialResponse {
  id: string;
  name: string;
  backend_type: string;
  base_url: string;
  credential_masked: string | null;
  updated_at: string;
}
