import { api } from '../../api/apiClient';
import type {
  PaginatedResponse,
  TradingTask,
  TradingTaskListParams,
} from '../../types';
import type { BackendTradingTask } from './contracts';
import { createTaskApi } from './taskApiFactory';

interface TradingTaskCreateRequest {
  config_id: string;
  account_id: string;
  name: string;
  description?: string;
  instrument?: string;
  sell_on_stop?: boolean;
  dry_run?: boolean;
  hedging_enabled?: boolean;
}

interface TradingTaskUpdateRequest {
  config_id?: string;
  account_id?: string;
  name?: string;
  description?: string;
  sell_on_stop?: boolean;
  dry_run?: boolean;
  hedging_enabled?: boolean;
  debug_options?: Record<string, unknown>;
}

function toTradingTask(task: BackendTradingTask): TradingTask {
  return {
    ...task,
    account_id: String(task.account_id),
    status: task.status as TradingTask['status'],
    pip_size: task.pip_size ?? undefined,
    execution_id: task.execution_id ?? undefined,
    started_at: task.started_at ?? undefined,
    completed_at: task.completed_at ?? undefined,
    error_message: task.error_message ?? undefined,
  };
}

const baseApi = createTaskApi<
  BackendTradingTask,
  TradingTask,
  TradingTaskListParams,
  TradingTaskCreateRequest,
  TradingTaskUpdateRequest
>({
  basePath: '/api/trading/tasks/trading',
  transform: toTradingTask,
  mapListParams: (params) => ({
    account_id: params?.account_id ? Number(params.account_id) : undefined,
    config_id: params?.config_id,
    ordering: params?.ordering,
    page: params?.page,
    page_size: params?.page_size,
    search: params?.search,
    status: params?.status,
  }),
});

export const tradingTasksApi = {
  ...baseApi,

  // Override: trading stop accepts a mode parameter
  stop: async (
    id: string,
    mode: 'immediate' | 'graceful' | 'graceful_close' = 'graceful'
  ): Promise<Record<string, unknown>> => {
    return api.post<Record<string, unknown>>(
      `/api/trading/tasks/trading/${id}/stop/`,
      { mode }
    );
  },

  // Override: list needs the same signature for callers expecting PaginatedResponse
  list: baseApi.list as (
    params?: TradingTaskListParams
  ) => Promise<PaginatedResponse<TradingTask>>,
};
