import type {
  KeyBreakdown,
  ModelBreakdown,
  RequestsResponse,
  Summary,
  TimeseriesPoint,
} from "./types";

const BASE = "/stats";

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${path}`);
  }
  return response.json() as Promise<T>;
}

export function getSummary(): Promise<Summary> {
  return get<Summary>(`${BASE}/summary`);
}

export function getByKey(): Promise<KeyBreakdown[]> {
  return get<KeyBreakdown[]>(`${BASE}/by-key`);
}

export function getByModel(): Promise<ModelBreakdown[]> {
  return get<ModelBreakdown[]>(`${BASE}/by-model`);
}

export function getTimeseries(days = 30): Promise<TimeseriesPoint[]> {
  return get<TimeseriesPoint[]>(`${BASE}/timeseries?days=${days}`);
}

export function getRequests(limit = 50, offset = 0): Promise<RequestsResponse> {
  return get<RequestsResponse>(`${BASE}/requests?limit=${limit}&offset=${offset}`);
}
