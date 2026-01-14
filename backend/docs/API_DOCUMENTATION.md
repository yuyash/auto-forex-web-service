# Trading System API Documentation

## Overview

This document provides comprehensive documentation for the Trading System API endpoints, focusing on the execution-specific endpoints that enable real-time monitoring and historical analysis of trading tasks.

## Base URL

All API endpoints are prefixed with `/api/trading/`

## Authentication

All endpoints require authentication using JWT tokens. Include the token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

## Execution Endpoints

These endpoints work directly with execution IDs rather than task IDs, allowing access to specific historical executions and enabling comparison across multiple executions.

### 1. Get Execution Status

Retrieve the current status and latest metrics for a specific execution.

**Endpoint:** `GET /api/trading/executions/{execution_id}/status/`

**Path Parameters:**

- `execution_id` (integer, required): The unique identifier of the execution

**Response:**

```json
{
  "execution_id": 123,
  "task_type": "backtest",
  "task_id": 456,
  "execution_number": 1,
  "status": "running",
  "progress": 45.5,
  "started_at": "2026-01-12T10:00:00Z",
  "completed_at": null,
  "error_message": null,
  "has_checkpoint": true,
  "checkpoint": {
    "id": 789,
    "processed": 45500,
    "total_return": "12.50",
    "total_pnl": "1250.00",
    "realized_pnl": "1000.00",
    "unrealized_pnl": "250.00",
    "total_trades": 25,
    "winning_trades": 15,
    "losing_trades": 10,
    "win_rate": "60.00",
    "max_drawdown": "5.25",
    "sharpe_ratio": "1.85",
    "profit_factor": "2.15",
    "average_win": "100.00",
    "average_loss": "50.00",
    "created_at": "2026-01-12T10:30:00Z"
  }
}
```

**Status Codes:**

- `200 OK`: Success
- `403 Forbidden`: User does not have access to this execution
- `404 Not Found`: Execution not found

**Example:**

```bash
curl -X GET \
  https://api.example.com/api/trading/executions/123/status/ \
  -H 'Authorization: Bearer your_jwt_token'
```

---

### 2. Get Execution Events

Retrieve strategy events for a specific execution with support for incremental fetching and filtering.

**Endpoint:** `GET /api/trading/executions/{execution_id}/events/`

**Path Parameters:**

- `execution_id` (integer, required): The unique identifier of the execution

**Query Parameters:**

- `since_sequence` (integer, optional): Fetch only events with sequence number greater than this value (for incremental updates)
- `event_type` (string, optional): Filter events by type (e.g., "tick_received", "strategy_signal", "trade_executed")
- `page` (integer, optional): Page number for pagination (default: 1)
- `page_size` (integer, optional): Number of results per page (default: 1000, max: 1000)

**Response:**

```json
{
  "execution_id": 123,
  "task_type": "backtest",
  "task_id": 456,
  "events": [
    {
      "sequence": 1,
      "event_type": "strategy_signal",
      "strategy_type": "floor",
      "timestamp": "2026-01-12T10:00:00Z",
      "event": {
        "signal": "buy",
        "layer_number": 1,
        "price": "1.2345"
      },
      "created_at": "2026-01-12T10:00:01Z"
    },
    {
      "sequence": 2,
      "event_type": "trade_executed",
      "strategy_type": "floor",
      "timestamp": "2026-01-12T10:00:02Z",
      "event": {
        "direction": "long",
        "units": 1000,
        "price": "1.2345"
      },
      "created_at": "2026-01-12T10:00:03Z"
    }
  ],
  "count": 2,
  "next": null,
  "previous": null
}
```

**Status Codes:**

- `200 OK`: Success
- `400 Bad Request`: Invalid query parameters
- `403 Forbidden`: User does not have access to this execution
- `404 Not Found`: Execution not found

**Example - Initial Fetch:**

```bash
curl -X GET \
  'https://api.example.com/api/trading/executions/123/events/?page_size=100' \
  -H 'Authorization: Bearer your_jwt_token'
```

**Example - Incremental Update:**

```bash
curl -X GET \
  'https://api.example.com/api/trading/executions/123/events/?since_sequence=50' \
  -H 'Authorization: Bearer your_jwt_token'
```

**Example - Filter by Event Type:**

```bash
curl -X GET \
  'https://api.example.com/api/trading/executions/123/events/?event_type=trade_executed' \
  -H 'Authorization: Bearer your_jwt_token'
```

---

### 3. Get Execution Trades

Retrieve trade logs for a specific execution with support for incremental fetching and filtering.

**Endpoint:** `GET /api/trading/executions/{execution_id}/trades/`

**Path Parameters:**

- `execution_id` (integer, required): The unique identifier of the execution

**Query Parameters:**

- `since_sequence` (integer, optional): Fetch only trades with sequence number greater than this value
- `instrument` (string, optional): Filter trades by instrument (e.g., "EUR_USD")
- `direction` (string, optional): Filter trades by direction ("long" or "short")
- `page` (integer, optional): Page number for pagination (default: 1)
- `page_size` (integer, optional): Number of results per page (default: 1000, max: 1000)

**Response:**

```json
{
  "execution_id": 123,
  "task_type": "backtest",
  "task_id": 456,
  "trades": [
    {
      "sequence": 1,
      "trade": {
        "instrument": "EUR_USD",
        "direction": "long",
        "entry_time": "2026-01-12T10:00:00Z",
        "entry_price": "1.2345",
        "units": 1000,
        "exit_time": "2026-01-12T11:00:00Z",
        "exit_price": "1.2355",
        "pnl": "10.00",
        "pips": "10.0",
        "details": {
          "layer_number": 1,
          "retracement_count": 0
        }
      },
      "created_at": "2026-01-12T11:00:01Z"
    }
  ],
  "count": 1,
  "next": null,
  "previous": null
}
```

**Status Codes:**

- `200 OK`: Success
- `400 Bad Request`: Invalid query parameters
- `403 Forbidden`: User does not have access to this execution
- `404 Not Found`: Execution not found

**Example - Filter by Instrument:**

```bash
curl -X GET \
  'https://api.example.com/api/trading/executions/123/trades/?instrument=EUR_USD' \
  -H 'Authorization: Bearer your_jwt_token'
```

**Example - Filter by Direction:**

```bash
curl -X GET \
  'https://api.example.com/api/trading/executions/123/trades/?direction=long' \
  -H 'Authorization: Bearer your_jwt_token'
```

---

### 4. Get Execution Equity Curve

Retrieve equity curve data for a specific execution with support for incremental fetching, time range filtering, and downsampling.

**Endpoint:** `GET /api/trading/executions/{execution_id}/equity/`

**Path Parameters:**

- `execution_id` (integer, required): The unique identifier of the execution

**Query Parameters:**

- `since_sequence` (integer, optional): Fetch only equity points with sequence number greater than this value
- `start_time` (ISO 8601 datetime, optional): Filter points after this timestamp
- `end_time` (ISO 8601 datetime, optional): Filter points before this timestamp
- `max_points` (integer, optional): Maximum number of points to return (triggers downsampling if exceeded)
- `page` (integer, optional): Page number for pagination (default: 1)
- `page_size` (integer, optional): Number of results per page (default: 500, max: 1000)

**Response:**

```json
{
  "execution_id": 123,
  "task_type": "backtest",
  "task_id": 456,
  "equity_curve": [
    {
      "sequence": 1,
      "timestamp": "2026-01-12T10:00:00Z",
      "balance": 10000.0
    },
    {
      "sequence": 2,
      "timestamp": "2026-01-12T10:05:00Z",
      "balance": 10050.0
    }
  ],
  "count": 2,
  "next": null,
  "previous": null,
  "granularity_seconds": null
}
```

**Response Fields:**

- `granularity_seconds`: If downsampling was applied, this indicates the time interval between points in seconds

**Status Codes:**

- `200 OK`: Success
- `400 Bad Request`: Invalid query parameters
- `403 Forbidden`: User does not have access to this execution
- `404 Not Found`: Execution not found

**Example - Time Range Filter:**

```bash
curl -X GET \
  'https://api.example.com/api/trading/executions/123/equity/?start_time=2026-01-12T10:00:00Z&end_time=2026-01-12T12:00:00Z' \
  -H 'Authorization: Bearer your_jwt_token'
```

**Example - Downsampling:**

```bash
curl -X GET \
  'https://api.example.com/api/trading/executions/123/equity/?max_points=100' \
  -H 'Authorization: Bearer your_jwt_token'
```

---

### 5. Get Latest Metrics

Retrieve the latest metrics checkpoint for a specific execution.

**Endpoint:** `GET /api/trading/executions/{execution_id}/metrics/latest/`

**Path Parameters:**

- `execution_id` (integer, required): The unique identifier of the execution

**Response:**

```json
{
  "execution_id": 123,
  "task_type": "backtest",
  "task_id": 456,
  "has_checkpoint": true,
  "checkpoint": {
    "id": 789,
    "processed": 100000,
    "total_return": "15.75",
    "total_pnl": "1575.00",
    "realized_pnl": "1500.00",
    "unrealized_pnl": "75.00",
    "total_trades": 50,
    "winning_trades": 32,
    "losing_trades": 18,
    "win_rate": "64.00",
    "max_drawdown": "4.50",
    "sharpe_ratio": "2.10",
    "profit_factor": "2.45",
    "average_win": "75.00",
    "average_loss": "35.00",
    "created_at": "2026-01-12T12:00:00Z"
  }
}
```

**Status Codes:**

- `200 OK`: Success
- `403 Forbidden`: User does not have access to this execution
- `404 Not Found`: Execution not found

**Example:**

```bash
curl -X GET \
  https://api.example.com/api/trading/executions/123/metrics/latest/ \
  -H 'Authorization: Bearer your_jwt_token'
```

---

## Common Response Patterns

### Error Responses

All endpoints return consistent error responses:

```json
{
  "error": "Error message describing what went wrong"
}
```

### Pagination

Endpoints that support pagination include these fields in the response:

- `count`: Total number of items
- `next`: URL for the next page (null if no more pages)
- `previous`: URL for the previous page (null if on first page)
- `results` or specific data field: Array of items for current page

---

## Real-Time Monitoring Pattern

For real-time monitoring of running executions, use this polling pattern:

1. **Status Updates** (every 3 seconds):

   ```
   GET /api/trading/executions/{id}/status/
   ```

2. **Incremental Events** (every 5 seconds):

   ```
   GET /api/trading/executions/{id}/events/?since_sequence={last_sequence}
   ```

3. **Incremental Equity** (every 10 seconds):

   ```
   GET /api/trading/executions/{id}/equity/?since_sequence={last_sequence}
   ```

4. **Latest Metrics** (every 30 seconds):
   ```
   GET /api/trading/executions/{id}/metrics/latest/
   ```

---

## Data Types

### Task Types

- `backtest`: Historical data simulation
- `trading`: Live trading execution

### Execution Status

- `created`: Execution has been created but not started
- `running`: Execution is currently processing
- `paused`: Execution has been paused
- `stopped`: Execution has been stopped by user
- `completed`: Execution finished successfully
- `failed`: Execution encountered a critical error

### Event Types

- `tick_received`: Market data tick received
- `strategy_signal`: Strategy generated a trading signal
- `trade_executed`: Trade was executed
- `status_changed`: Execution status changed
- `error_occurred`: An error occurred

### Trade Directions

- `long`: Buy position
- `short`: Sell position

---

## Rate Limiting

API requests are subject to rate limiting:

- Standard endpoints: 100 requests per minute per user
- Real-time endpoints: 200 requests per minute per user

Rate limit headers are included in responses:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1673524800
```

---

## Best Practices

1. **Use Incremental Fetching**: Always use `since_sequence` parameter for events, trades, and equity to minimize data transfer

2. **Implement Backoff**: If you receive a 429 (Too Many Requests) response, implement exponential backoff

3. **Cache Responses**: Cache completed execution data as it won't change

4. **Batch Requests**: When fetching data for multiple executions, batch your requests efficiently

5. **Handle Errors Gracefully**: Always check status codes and handle errors appropriately

6. **Use Appropriate Page Sizes**: Request only the data you need to minimize response times

---

## Support

For API support or to report issues, please contact the development team or file an issue in the project repository.
