# Contract: Stats API

**Service**: Relay proxy (same process as proxy API)
**Base path**: `/stats`
**Auth**: None (read-only, internal dashboard use)

---

## GET /stats/summary

Returns aggregated totals across all recorded usage.

### Response

```json
{
  "total_cost": 1.2345,
  "total_requests": 312,
  "total_input_tokens": 84200,
  "total_output_tokens": 22100
}
```

---

## GET /stats/by-key

Returns per-API-key aggregated usage, sorted by total cost descending.

### Response

```json
[
  {
    "api_key_label": "my-app",
    "total_cost": 0.98,
    "total_requests": 240,
    "total_input_tokens": 61000,
    "total_output_tokens": 15000
  },
  ...
]
```

---

## GET /stats/by-model

Returns per-model aggregated usage, sorted by total cost descending.

### Response

```json
[
  {
    "model": "gpt-4o",
    "backend": "openai_compat",
    "total_cost": 1.10,
    "total_requests": 200,
    "total_input_tokens": 54000,
    "total_output_tokens": 18000
  },
  ...
]
```

---

## GET /stats/timeseries

Returns daily aggregated cost and request count for the chart.

### Query parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 30 | Number of past days to include |

### Response

```json
[
  {
    "date": "2026-06-01",
    "total_cost": 0.45,
    "total_requests": 110
  },
  {
    "date": "2026-06-02",
    "total_cost": 0.38,
    "total_requests": 95
  },
  ...
]
```

Dates are ISO 8601 (`YYYY-MM-DD`). Days with no requests are omitted.

---

## GET /stats/requests

Returns the raw request log, paginated, newest first.

### Query parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Rows per page (max 500) |
| `offset` | integer | 0 | Pagination offset |

### Response

```json
{
  "total": 312,
  "offset": 0,
  "limit": 50,
  "items": [
    {
      "id": 312,
      "timestamp": "2026-06-03T14:22:01Z",
      "api_key_label": "my-app",
      "model": "gpt-4o",
      "backend": "openai_compat",
      "input_tokens": 340,
      "output_tokens": 82,
      "cost": 0.00167,
      "token_count_source": "exact",
      "status_code": 200
    },
    ...
  ]
}
```

`token_count_source` is `"exact"` or `"estimated"`. The dashboard MUST render
estimated records with a visible indicator (e.g., a tilde prefix or tooltip).
