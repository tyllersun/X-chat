# X-chat Chat API — Response Specification

## Overview

The `/v1/chat` endpoint returns a **block-based response** that the Streamlit frontend
renders sequentially. All text, charts, maps, and metrics are expressed as typed blocks,
allowing the LLM / backend to fully control layout and content without any frontend changes.

---

## Request

```http
POST /v1/chat
Authorization: Bearer <api_key>
Content-Type: application/json
```

```json
{
  "prompt": "Show me the product sales trend for the last 30 days",
  "user_id": "admin",
  "chat_id": "New Chat 1",
  "history": [
    { "role": "user",      "content": "Hello" },
    { "role": "assistant", "content": "Hi! How can I help?" }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | ✅ | The user's current message |
| `user_id` | string | ✅ | Authenticated user identifier |
| `chat_id` | string | ✅ | Current chat session ID |
| `history` | array | ✅ | Last N messages for context (recommend last 10) |

---

## Response

```json
{
  "blocks": [ ...see Block Types below... ],
  "trace":  [ ...see Trace Events below... ]
}
```

---

## Block Types

All blocks share a `type` field. Unknown types are silently skipped by the frontend.

### `text`
Plain markdown text rendered inline.

```json
{ "type": "text", "content": "Here is your sales analysis:" }
```

| Field | Type | Description |
|-------|------|-------------|
| `content` | string | Markdown-formatted text |

---

### `plotly` ⭐ (preferred for all charts)
A full [Plotly.js figure dict](https://plotly.com/python/reference/) serialized to JSON.
Supports 60+ chart types (line, bar, scatter, pie, heatmap, funnel, candlestick, etc.).

```json
{
  "type": "plotly",
  "spec": {
    "data": [
      {
        "type": "bar",
        "x": ["Product A", "Product B", "Product C"],
        "y": [52000, 78000, 43000],
        "marker": { "color": ["#4C9BE8", "#E8834C", "#4CE87C"] }
      }
    ],
    "layout": {
      "title": "Monthly Revenue by Product",
      "xaxis": { "title": "Product" },
      "yaxis": { "title": "Revenue (USD)" },
      "template": "plotly_dark"
    }
  },
  "insight": "Product B leads revenue by 50% vs Product A. Consider increasing Q2 budget allocation."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `spec` | object | ✅ | Plotly figure dict (same as `fig.to_dict()` in Python) |
| `insight` | string | ❌ | AI-generated insight text shown below the chart |

> **Backend tip**: Generate with `plotly.graph_objects.Figure(...).to_dict()` or ask the LLM to produce a valid Plotly spec directly.

---

### `map`
An interactive point map (latitude/longitude data).

```json
{
  "type": "map",
  "title": "🗺️ User Geographic Distribution",
  "data": [
    { "lat": 25.033, "lon": 121.565 },
    { "lat": 22.627, "lon": 120.301 }
  ],
  "insight": "68% of users concentrated in northern Taiwan."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | ❌ | Section heading |
| `data` | array | ✅ | Array of `{ lat, lon }` objects |
| `insight` | string | ❌ | AI-generated insight text |

---

### `metric`
A row of KPI metric cards.

```json
{
  "type": "metric",
  "metrics": [
    { "label": "Total Users",     "value": "10,245", "delta": "+5.2%" },
    { "label": "Active Sessions", "value": "1,203",  "delta": "-1.5%" },
    { "label": "Revenue",         "value": "$45,231", "delta": "+12.3%" }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `metrics` | array | ✅ | Array of metric objects |
| `metrics[].label` | string | ✅ | Metric name |
| `metrics[].value` | string | ✅ | Current value (formatted as string) |
| `metrics[].delta` | string | ❌ | Change indicator (e.g., `"+5.2%"`) |

---

## Trace Events

The `trace` array documents what happened internally (LLM calls, tool calls, sub-agents).
Displayed in a collapsible **"🔍 View reasoning trace"** expander below the response.

```json
{
  "trace": [
    {
      "type": "llm_call",
      "label": "Intent detection",
      "duration_ms": 310
    },
    {
      "type": "tool_call",
      "label": "query_sales_trend(period=30d)",
      "duration_ms": 820,
      "detail": "Returned 30 rows from BigQuery"
    },
    {
      "type": "sub_agent",
      "label": "Anomaly detection sub-agent",
      "duration_ms": 1200,
      "detail": "No anomalies detected"
    },
    {
      "type": "llm_call",
      "label": "Insight generation",
      "duration_ms": 540
    }
  ]
}
```

| `type` value | Icon | Description |
|-------------|------|-------------|
| `llm_call`  | 🧠 | A call to the LLM (intent detection, insight generation, etc.) |
| `tool_call` | 🔧 | A function/tool execution (database query, API call, etc.) |
| `sub_agent` | 🤖 | A specialized sub-agent invocation |
| `query`     | 🗄️ | A raw database query |

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | ✅ | One of: `llm_call`, `tool_call`, `sub_agent`, `query` |
| `label` | string | ✅ | Human-readable step name |
| `duration_ms` | int | ❌ | Execution time in milliseconds |
| `detail` | string | ❌ | Additional detail (e.g., row count, model used) |

---

## Full Response Example

```json
{
  "blocks": [
    {
      "type": "text",
      "content": "Here is the 30-day sales trend for all products:"
    },
    {
      "type": "plotly",
      "spec": {
        "data": [
          { "type": "scatter", "mode": "lines", "name": "Product A", "x": ["2026-01-01", "..."], "y": [52, 58, 61] },
          { "type": "scatter", "mode": "lines", "name": "Product B", "x": ["2026-01-01", "..."], "y": [40, 55, 74] }
        ],
        "layout": { "title": "30-Day Sales Trend", "template": "plotly_dark" }
      },
      "insight": "Product B grew 85% over 30 days — significantly outpacing Product A."
    },
    {
      "type": "text",
      "content": "Would you like a breakdown by region or user segment?"
    }
  ],
  "trace": [
    { "type": "llm_call",  "label": "Intent detection",             "duration_ms": 310 },
    { "type": "tool_call", "label": "query_sales_trend(period=30d)", "duration_ms": 820, "detail": "30 rows from BigQuery" },
    { "type": "llm_call",  "label": "Insight generation",           "duration_ms": 540 }
  ]
}
```
