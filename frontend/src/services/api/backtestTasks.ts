import { api } from '../../api/apiClient';
import type {
  BacktestTask,
  BacktestTaskCreateData,
  BacktestTaskListParams,
  BacktestTaskUpdateData,
} from '../../types';
import type {
  BackendBacktestTask,
  BackendTaskExecutionSummary,
} from './contracts';
import { createTaskApi } from './taskApiFactory';

function toExecutionSummary(
  execution?: BackendTaskExecutionSummary | null
): BacktestTask['latest_execution'] {
  if (!execution) return undefined;
  return {
    ...execution,
    execution_number: Number(execution.execution_number),
    status: execution.status as BacktestTask['status'],
    started_at: execution.started_at ?? execution.created_at,
    completed_at: execution.completed_at ?? undefined,
    error_message: execution.error_message ?? undefined,
  };
}

function toBacktestTask(task: BackendBacktestTask): BacktestTask {
  return {
    ...task,
    data_source: task.data_source as BacktestTask['data_source'],
    status: task.status as BacktestTask['status'],
    sell_at_completion: false,
    latest_execution: toExecutionSummary(task.latest_execution),
    pip_size: task.pip_size ?? undefined,
    execution_id: task.execution_id ?? undefined,
    started_at: task.started_at ?? undefined,
    completed_at: task.completed_at ?? undefined,
    error_message: task.error_message ?? undefined,
  };
}

const baseApi = createTaskApi<
  BackendBacktestTask,
  BacktestTask,
  BacktestTaskListParams,
  BacktestTaskCreateData,
  BacktestTaskUpdateData
>({
  basePath: '/api/trading/tasks/backtest',
  transform: toBacktestTask,
  mapListParams: (params) => ({
    config_id: params?.config_id,
    ordering: params?.ordering,
    page: params?.page,
    page_size: params?.page_size,
    search: params?.search,
    status: params?.status,
  }),
});

export const backtestTasksApi = {
  ...baseApi,

  // Override: backtest stop accepts the same mode parameter as trading
  // tasks. Default remains ``graceful`` to preserve the previous
  // behaviour when callers omit the mode.  For drain mode, an optional
  // ``drain_duration_minutes`` override may be supplied.
  stop: async (
    id: string,
    mode: 'immediate' | 'graceful' | 'graceful_close' | 'drain' = 'graceful',
    drainDurationMinutes?: number
  ): Promise<Record<string, unknown>> => {
    const payload: Record<string, unknown> = { mode };
    if (mode === 'drain' && typeof drainDurationMinutes === 'number') {
      payload.drain_duration_minutes = drainDurationMinutes;
    }
    return api.post<Record<string, unknown>>(
      `/api/trading/tasks/backtest/${id}/stop/`,
      payload
    );
  },
};
