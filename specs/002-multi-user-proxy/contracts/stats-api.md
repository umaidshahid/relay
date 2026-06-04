# Contract: Stats API

**Base path**: `/stats`
**Auth**: `Authorization: Bearer <jwt>` (FastAPI-Users session token)

All endpoints return data scoped exclusively to the authenticated user.
No cross-user data is ever returned.

---

## GET /stats/summary

Aggregated totals for the authenticated user.

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

Per-proxy-key aggregated usage, sorted by total cost descending.

### Response

```json
[
  {
    "proxy_key_id": "uuid",
    "proxy_key_label": "my-app",
    "display": "sk-relay-...abc4",
    "total_cost": 0.98,
    "total_requests": 240,
    "total_input_tokens": 61000,
    "total_output_tokens": 15000
  }
]
```

---

## GET /stats/by-model

Per-model aggregated usage for the authenticated user, sorted by cost descending.

### Response

```json
[
  {
    "model": "gpt-4o-mini",
    "backend_type": "openai_compat",
    "total_cost": 1.10,
    "total_requests": 200,
    "total_input_tokens": 54000,
    "total_output_tokens": 18000
  }
]
```

---

## GET /stats/timeseries

Daily cost and request count for the authenticated user.

### Query parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 30 | Number of past days to include |

### Response

```json
[
  { "date": "2026-06-01", "total_cost": 0.45, "total_requests": 110 },
  { "date": "2026-06-02", "total_cost": 0.38, "total_requests": 95 }
]
```

---

## GET /stats/requests

Paginated request log for the authenticated user, newest first.

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
      "proxy_key_label": "my-app",
      "model": "gpt-4o-mini",
      "backend_type": "openai_compat",
      "input_tokens": 340,
      "output_tokens": 82,
      "cost": 0.00167,
      "token_count_source": "exact",
      "status_code": 200
    }
  ]
}
```

`token_count_source` is `"exact"` or `"estimated"`. The dashboard MUST display
an indicator for estimated records (e.g., `~` prefix on token counts).

**Isolation guarantee**: The `user_id` filter is applied at the database layer
on every query. No record belonging to another user can appear in these responses.
