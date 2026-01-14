# Task-Based Strategy Configuration API Layer

This directory contains the API service layer and React hooks for the task-based strategy configuration feature.

## Overview

The task-based architecture separates strategy configuration from execution, allowing reusable configurations to be shared across multiple backtesting and live trading tasks.

## Structure

### Types (`src/types/`)

- **common.ts** - Common enums and types (TaskStatus, TaskType, DataSource, PaginatedResponse)
- **configuration.ts** - Strategy configuration types
- **backtestTask.ts** - Backtest task types
- **tradingTask.ts** - Trading task types
- **execution.ts** - Task execution and metrics types

### API Services (`src/services/api/`)

- **client.ts** - Base API client with authentication and error handling
- **configurations.ts** - Strategy configuration CRUD operations
- **backtestTasks.ts** - Backtest task operations (CRUD + lifecycle)
- **tradingTasks.ts** - Trading task operations (CRUD + lifecycle)

### Data Fetching Hooks (`src/hooks/`)

- **useConfigurations.ts** - Fetch configurations and related tasks
- **useBacktestTasks.ts** - Fetch backtest tasks with polling support
- **useTradingTasks.ts** - Fetch trading tasks with polling support
- **useTaskExecutions.ts** - Fetch execution history

### Mutation Hooks (`src/hooks/`)

- **useConfigurationMutations.ts** - Create, update, delete configurations
- **useBacktestTaskMutations.ts** - Backtest task lifecycle (start, stop, resume, restart, copy)
- **useTradingTaskMutations.ts** - Trading task lifecycle (start, stop, resume, restart, copy)

## Usage Examples

### Fetching Configurations

```typescript
import { useConfigurations } from '../hooks/useConfigurations';

function ConfigurationsList() {
  const { data, isLoading, error, refetch } = useConfigurations({
    page: 1,
    page_size: 20,
    strategy_type: 'ma_crossover',
  });

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div>
      {data?.results.map((config) => (
        <div key={config.id}>{config.name}</div>
      ))}
    </div>
  );
}
```

### Creating a Configuration

```typescript
import { useCreateConfiguration } from '../hooks/useConfigurationMutations';

function CreateConfigForm() {
  const { mutate, isLoading, error } = useCreateConfiguration({
    onSuccess: (data) => {
      console.log('Configuration created:', data);
    },
    onError: (error) => {
      console.error('Failed to create:', error);
    },
  });

  const handleSubmit = async (formData) => {
    await mutate({
      name: formData.name,
      strategy_type: 'ma_crossover',
      parameters: {
        fast_period: 50,
        slow_period: 200,
      },
    });
  };

  return <form onSubmit={handleSubmit}>...</form>;
}
```

### Starting a Backtest Task

```typescript
import { useStartBacktestTask } from '../hooks/useBacktestTaskMutations';

function BacktestTaskCard({ taskId }) {
  const { mutate: startTask, isLoading } = useStartBacktestTask({
    onSuccess: (data) => {
      console.log('Task started, execution ID:', data.execution_id);
    },
  });

  return (
    <button onClick={() => startTask(taskId)} disabled={isLoading}>
      {isLoading ? 'Starting...' : 'Start Task'}
    </button>
  );
}
```

### Polling Running Tasks

```typescript
import { useBacktestTaskPolling } from '../hooks/useBacktestTasks';
import { TaskStatus } from '../types';

function RunningTaskMonitor({ taskId }) {
  const { data, isLoading } = useBacktestTaskPolling(
    taskId,
    true, // enabled
    10000 // poll every 10 seconds
  );

  const isRunning = data?.status === TaskStatus.RUNNING;

  return (
    <div>
      <div>Status: {data?.status}</div>
      {data?.latest_execution && (
        <div>Progress: {data.latest_execution.progress}%</div>
      )}
    </div>
  );
}
```

## API Endpoints

### Strategy Configurations

- `GET /api/strategy-configs/` - List configurations
- `POST /api/strategy-configs/` - Create configuration
- `GET /api/strategy-configs/{id}/` - Get configuration
- `PUT /api/strategy-configs/{id}/` - Update configuration
- `DELETE /api/strategy-configs/{id}/` - Delete configuration
- `GET /api/strategy-configs/{id}/tasks/` - Get tasks using config

### Backtest Tasks

- `GET /api/backtest-tasks/` - List backtest tasks
- `POST /api/backtest-tasks/` - Create backtest task
- `GET /api/backtest-tasks/{id}/` - Get backtest task
- `PUT /api/backtest-tasks/{id}/` - Update backtest task
- `DELETE /api/backtest-tasks/{id}/` - Delete backtest task
- `POST /api/backtest-tasks/{id}/copy/` - Copy task
- `POST /api/backtest-tasks/{id}/start/` - Start execution
- `POST /api/backtest-tasks/{id}/stop/` - Stop execution (state is persisted)
- `POST /api/backtest-tasks/{id}/resume/` - Resume execution from persisted state
- `POST /api/backtest-tasks/{id}/restart/` - Restart from beginning (clears state)
- `GET /api/backtest-tasks/{id}/executions/` - Get execution history

### Trading Tasks

- `GET /api/trading-tasks/` - List trading tasks
- `POST /api/trading-tasks/` - Create trading task
- `GET /api/trading-tasks/{id}/` - Get trading task
- `PUT /api/trading-tasks/{id}/` - Update trading task
- `DELETE /api/trading-tasks/{id}/` - Delete trading task
- `POST /api/trading-tasks/{id}/copy/` - Copy task
- `POST /api/trading-tasks/{id}/start/` - Start execution
- `POST /api/trading-tasks/{id}/stop/` - Stop execution (state is persisted)
- `POST /api/trading-tasks/{id}/resume/` - Resume execution from persisted state
- `POST /api/trading-tasks/{id}/restart/` - Restart from beginning (clears state)
- `GET /api/trading-tasks/{id}/executions/` - Get execution history

## Authentication

All API requests automatically include the Bearer token from localStorage. The token is managed by the AuthContext.

## Error Handling

The API client provides consistent error handling:

- Network errors are caught and formatted
- HTTP errors include status code and response data
- Mutation hooks support onSuccess and onError callbacks
- All hooks expose error state for UI display

## Future Enhancements

- Add React Query for better caching and state management
- Add optimistic updates for mutations
- Add WebSocket support for real-time updates
- Add request cancellation for long-running operations
