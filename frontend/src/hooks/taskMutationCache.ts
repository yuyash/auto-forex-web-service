import { queryClient, queryKeys } from '../config/reactQuery';
import type { BacktestTask, PaginatedResponse, TradingTask } from '../types';
import { invalidateTaskDerivedByKind } from './taskResourceCache';

type TaskEntity = BacktestTask | TradingTask;
type TaskKind = 'backtest' | 'trading';

function getTaskKeys(taskKind: TaskKind) {
  if (taskKind === 'backtest') {
    return {
      lists: queryKeys.backtestTasks.lists(),
      detail: queryKeys.backtestTasks.detail,
      executions: queryKeys.backtestTasks.executions,
    };
  }
  return {
    lists: queryKeys.tradingTasks.lists(),
    detail: queryKeys.tradingTasks.detail,
    executions: queryKeys.tradingTasks.executions,
  };
}

function patchPaginatedTask<T extends TaskEntity>(
  cached: PaginatedResponse<T> | undefined,
  task: T
): PaginatedResponse<T> | undefined {
  if (!cached) {
    return cached;
  }
  const nextResults = cached.results.map((entry) =>
    entry.id === task.id ? { ...entry, ...task } : entry
  );
  const exists = nextResults.some((entry) => entry.id === task.id);
  return exists ? { ...cached, results: nextResults } : cached;
}

export function upsertTaskCaches<T extends TaskEntity>(
  taskKind: TaskKind,
  task: T
): void {
  const keys = getTaskKeys(taskKind);
  queryClient.setQueryData(keys.detail(task.id), task);
  queryClient.setQueriesData<PaginatedResponse<T>>(
    { queryKey: keys.lists },
    (cached) => patchPaginatedTask(cached, task)
  );
}

export function removeTaskCaches(taskKind: TaskKind, taskId: string): void {
  const keys = getTaskKeys(taskKind);
  queryClient.removeQueries({ queryKey: keys.detail(taskId) });
  queryClient.setQueriesData<PaginatedResponse<TaskEntity>>(
    { queryKey: keys.lists },
    (cached) => {
      if (!cached) {
        return cached;
      }
      const nextResults = cached.results.filter((entry) => entry.id !== taskId);
      if (nextResults.length === cached.results.length) {
        return cached;
      }
      return {
        ...cached,
        count: Math.max(0, cached.count - 1),
        results: nextResults,
      };
    }
  );
}

export function patchTaskStatusCache(
  taskKind: TaskKind,
  taskId: string,
  status: string
): void {
  const keys = getTaskKeys(taskKind);
  queryClient.setQueryData<TaskEntity | undefined>(
    keys.detail(taskId),
    (cached) => (cached ? { ...cached, status } : cached)
  );
  queryClient.setQueriesData<PaginatedResponse<TaskEntity>>(
    { queryKey: keys.lists },
    (cached) => {
      if (!cached) {
        return cached;
      }
      return {
        ...cached,
        results: cached.results.map((entry) =>
          entry.id === taskId ? { ...entry, status } : entry
        ),
      };
    }
  );
}

export async function invalidateTaskDerivedCaches(
  taskKind: TaskKind,
  taskId: string
): Promise<void> {
  await invalidateTaskDerivedByKind(taskId, taskKind);
}
