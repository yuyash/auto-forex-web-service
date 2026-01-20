# API Service Layer

This directory contains the API service layer for the Auto Forex trading application, now using the generated OpenAPI client for type-safe API calls.

## Overview

The API layer has been refactored to use a generated OpenAPI client (from `openapi-typescript-codegen`) with execution-centric endpoints. This provides:

- **Type Safety**: All API calls are fully typed based on the OpenAPI specification
- **Consistency**: Standardized error handling and retry logic
- **Execution-Centric**: Data is accessed through execution endpoints rather than task-specific endpoints
- **Maintainability**: API client is auto-generated from the backend OpenAPI spec

## Structure

### Generated Client (`src/api/generated/`)

- **services/** - Auto-generated service classes (ExecutionsService, TradingService, etc.)
- **models/** - Auto-generated TypeScript types from OpenAPI schemas
- **core/** - Core client functionality (request handling, error types)

### API Wrappers (`src/services/api/`)

- **client.ts** - Legacy API client (being phased out)
- **executionApi.ts** - Execution-based endpoints (status, logs, events, trades, equity, metrics)
- **backtestTasks.ts** - Backtest task operations (CRUD + lifecycle control)
- **tradingTasks.ts** - Trading task operations (CRUD + lifecycle control)
- **configurations.ts** - Strategy configuration CRUD operations
- **accounts.ts** - OANDA account operations
- **strategies.ts** - Strategy listing and defaults

## Key Changes from Previous Architecture

### Execution-Based Data Access

**Before**: Data was accessed through task-specific endpoints

```typescript
// Old approach - task-specific endpoints
GET /api/backtest-tasks/{task_id}/logs/
GET /api/backtest-tasks/{task_id}/equity-curve/
GET /api/backtest-tasks/{task_id}/strategy-events/
```

**After**: Data is accessed through execution endpoints

```typescript
// New approach - execution-based endpoints
GET /api/executions/{execution_id}/logs/
GET /api/executions/{execution_id}/equity/
GET /api/executions/{execution_id}/events/
```

### Task Control Returns Execution ID

All task control endpoints (start, resume, restart) now return an `execution_id`:

```typescript
const response = await backtestTasksApi.start(taskId);
// response includes: { execution_id: number, status: string, message: string }
```

### Status Endpoints Include Execution ID

Task status endpoints include the current `execution_id` when running:

```typescript
const status = await backtestTasksApi.getStatus(taskId);
// status includes: { execution_id: number, status: 'running', ... }
```

## Usage Examples

### Starting a Task and Accessing Execution Data

```typescript
import { backtestTasksApi, executionApi } from '../services/api';

// Start a backtest task
const startResponse = await backtestTasksApi.start(taskId);
const executionId = startResponse.execution_id;

// Access execution data
const status = await executionApi.getStatus(executionId);
const logs = await executionApi.getLogs(executionId, { limit: 100 });
const events = await executionApi.getEvents(executionId);
const trades = await executionApi.getTrades(executionId);
const equity = await executionApi.getEquity(executionId, { granularity: 60 });
const metrics = await executionApi.getMetrics(executionId);
```

### Granular Equity Curve

The equity endpoint supports configurable time granularity for binning:

```typescript
// Get equity curve with 5-minute bins
const equity = await executionApi.getEquity(executionId, {
  granularity: 300, // seconds
  startTime: '2024-01-01T00:00:00Z',
  endTime: '2024-01-02T00:00:00Z',
});

// Response includes statistical aggregations per bin:
// - realized_pnl_min/max/avg/median
// - unrealized_pnl_min/max/avg/median
// - tick_ask/bid/mid_min/max/avg/median
// - trade_count
```

### Incremental Data Fetching

Events and trades support incremental fetching with `sinceSequence`:

```typescript
// Initial fetch
const events = await executionApi.getEvents(executionId);

// Later, fetch only new events
const newEvents = await executionApi.getEvents(executionId, {
  sinceSequence: lastSequence,
});
```

### Task Lifecycle Control

```typescript
import { backtestTasksApi } from '../services/api';

// Start a task
const startResp = await backtestTasksApi.start(taskId);
console.log('Execution ID:', startResp.execution_id);

// Stop a task
await backtestTasksApi.stop(taskId);

// Resume a paused task
const resumeResp = await backtestTasksApi.resume(taskId);
console.log('Resumed execution ID:', resumeResp.execution_id);

// Restart a task (closes positions, reinitializes strategy)
const restartResp = await backtestTasksApi.restart(taskId);
console.log('New execution ID:', restartResp.execution_id);
```

## API Endpoints

### Execution Endpoints (New)

- `GET /api/executions/{id}/` - Get execution details
- `GET /api/executions/{id}/status/` - Get execution status
- `GET /api/executions/{id}/logs/` - Get execution logs (with filtering)
- `GET /api/executions/{id}/events/` - Get strategy events (with incremental fetch)
- `GET /api/executions/{id}/trades/` - Get trade logs (with incremental fetch)
- `GET /api/executions/{id}/equity/` - Get equity curve (with granularity binning)
- `GET /api/executions/{id}/metrics/` - Get metrics (with granularity binning)
- `GET /api/executions/{id}/metrics/latest/` - Get latest metrics snapshot

### Backtest Task Endpoints

- `GET /api/trading/backtest-tasks/` - List backtest tasks
- `POST /api/trading/backtest-tasks/` - Create backtest task
- `GET /api/trading/backtest-tasks/{id}/` - Get backtest task
- `PUT /api/trading/backtest-tasks/{id}/` - Update backtest task
- `PATCH /api/trading/backtest-tasks/{id}/` - Partially update backtest task
- `DELETE /api/trading/backtest-tasks/{id}/` - Delete backtest task
- `POST /api/trading/backtest-tasks/{id}/copy/` - Copy task
- `POST /api/trading/backtest-tasks/{id}/start/` - Start execution (returns execution_id)
- `POST /api/trading/backtest-tasks/{id}/stop/` - Stop execution
- `POST /api/trading/backtest-tasks/{id}/resume/` - Resume execution (returns execution_id)
- `POST /api/trading/backtest-tasks/{id}/restart/` - Restart execution (returns execution_id)
- `GET /api/trading/backtest-tasks/{id}/status/` - Get status (includes execution_id when running)
- `GET /api/trading/backtest-tasks/{id}/executions/` - Get execution history

### Trading Task Endpoints

- `GET /api/trading/trading-tasks/` - List trading tasks
- `POST /api/trading/trading-tasks/` - Create trading task
- `GET /api/trading/trading-tasks/{id}/` - Get trading task
- `PUT /api/trading/trading-tasks/{id}/` - Update trading task
- `PATCH /api/trading/trading-tasks/{id}/` - Partially update trading task
- `DELETE /api/trading/trading-tasks/{id}/` - Delete trading task
- `POST /api/trading/trading-tasks/{id}/copy/` - Copy task
- `POST /api/trading/trading-tasks/{id}/start/` - Start execution (returns execution_id)
- `POST /api/trading/trading-tasks/{id}/stop/` - Stop execution
- `POST /api/trading/trading-tasks/{id}/resume/` - Resume execution (returns execution_id)
- `POST /api/trading/trading-tasks/{id}/restart/` - Restart execution (returns execution_id)
- `GET /api/trading/trading-tasks/{id}/status/` - Get status (includes execution_id when running)
- `GET /api/trading/trading-tasks/{id}/executions/` - Get execution history

### Strategy Configuration Endpoints

- `GET /api/trading/strategy-configs/` - List configurations
- `POST /api/trading/strategy-configs/` - Create configuration
- `GET /api/trading/strategy-configs/{id}/` - Get configuration
- `PUT /api/trading/strategy-configs/{id}/` - Update configuration
- `DELETE /api/trading/strategy-configs/{id}/` - Delete configuration

## Error Handling

The API client provides consistent error handling through the `withRetry` wrapper:

- Automatic retry for transient failures (network errors, 5xx errors, rate limits)
- Exponential backoff for retries
- Transformed error objects with consistent structure
- Type-safe error responses

```typescript
import { withRetry, transformApiError } from '../api/client';

try {
  const data = await withRetry(() => ExecutionsService.getExecutionStatus(id));
} catch (error) {
  const transformedError = transformApiError(error);
  console.error(transformedError.message);
}
```

## Regenerating the API Client

When the backend OpenAPI spec changes, regenerate the client:

```bash
cd frontend
npm run generate:api
```

This reads `backend/openapi.yaml` and generates TypeScript client code in `frontend/src/api/generated/`.

## Migration Notes

### Removed Endpoints

The following task-specific data endpoints have been removed:

- `GET /api/backtest-tasks/{id}/logs/` → Use `GET /api/executions/{execution_id}/logs/`
- `GET /api/backtest-tasks/{id}/export/` → Removed (no replacement)
- `GET /api/backtest-tasks/{id}/results/` → Removed (no replacement)
- `GET /api/backtest-tasks/{id}/equity-curve/` → Use `GET /api/executions/{execution_id}/equity/`
- `GET /api/backtest-tasks/{id}/strategy-events/` → Use `GET /api/executions/{execution_id}/events/`
- `GET /api/backtest-tasks/{id}/trade-logs/` → Use `GET /api/executions/{execution_id}/trades/`
- `GET /api/backtest-tasks/{id}/metrics-checkpoint/` → Use `GET /api/executions/{execution_id}/metrics/latest/`

Same removals apply to trading task endpoints.

### Components Need Updates

Components that previously used task-specific endpoints need to:

1. Get the `execution_id` from task status or start/resume/restart responses
2. Use execution-based endpoints for data access
3. Handle the new response formats (especially equity curve with statistical bins)
