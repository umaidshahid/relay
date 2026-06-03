// TypeScript interfaces matching contracts/stats-api.md

export interface Summary {
  total_cost: number;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
}

export interface KeyBreakdown {
  api_key_label: string;
  total_cost: number;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
}

export interface ModelBreakdown {
  model: string;
  backend: string;
  total_cost: number;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
}

export interface TimeseriesPoint {
  date: string;
  total_cost: number;
  total_requests: number;
}

export interface RequestRecord {
  id: number;
  timestamp: string;
  api_key_label: string;
  model: string;
  backend: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  token_count_source: "exact" | "estimated";
  status_code: number;
}

export interface RequestsResponse {
  total: number;
  offset: number;
  limit: number;
  items: RequestRecord[];
}
