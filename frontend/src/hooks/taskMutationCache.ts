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

function getTaskDerivedKeys(taskKind: TaskKind, taskId: string) {
  const taskType = taskKind === 'backtest' ? 'backtest' : 'trading';
  return {
    summaries: queryKeys.taskResources.summary(taskType, taskId),
    strategyEvents: queryKeys.taskResources.strategyEvents(taskType, taskId),
    logComponents: queryKeys.taskResources.logComponents(taskType, taskId),
  };
}

function getListParams(
  queryKey: readonly unknown[]
): Record<string, unknown> | undefined {
  const candidate = queryKey[2];
  return candidate && typeof candidate === 'object'
    ? (candidate as Record<string, unknown>)
    : undefined;
}

function matchesTaskListFilter(
  taskKind: TaskKind,
  task: TaskEntity,
  params?: Record<string, unknown>
): boolean {
  if (!params) {
    return true;
  }

  const status = params.status;
  if (typeof status === 'string' && status && task.status !== status) {
    return false;
  }

  const configId = params.config_id;
  if (typeof configId === 'string' && configId && task.config_id !== configId) {
    return false;
  }

  const strategyType = params.strategy_type;
  if (
    typeof strategyType === 'string' &&
    strategyType &&
    task.strategy_type !== strategyType
  ) {
    return false;
  }

  if (taskKind === 'trading') {
    const accountId = params.account_id;
    if (
      typeof accountId === 'string' &&
      accountId &&
      (task as TradingTask).account_id !== accountId
    ) {
      return false;
    }
  }

  const search = params.search;
  if (typeof search === 'string' && search.trim()) {
    const haystack = [
      task.name,
      task.description,
      task.config_name,
      task.strategy_type,
    ]
      .join(' ')
      .toLowerCase();
    if (!haystack.includes(search.trim().toLowerCase())) {
      return false;
    }
  }

  return true;
}

function patchListEntry<T extends TaskEntity>(
  taskKind: TaskKind,
  cached: PaginatedResponse<T> | undefined,
  task: T,
  params?: Record<string, unknown>
): PaginatedResponse<T> | undefined {
  if (!cached) {
    return cached;
  }

  const matches = matchesTaskListFilter(taskKind, task, params);
  const index = cached.results.findIndex((entry) => entry.id === task.id);

  if (index >= 0) {
    if (!matches) {
      const nextResults = cached.results.filter(
        (entry) => entry.id !== task.id
      );
      return {
        ...cached,
        count: Math.max(0, cached.count - 1),
        results: nextResults,
      };
    }
    const nextResults = [...cached.results];
    nextResults[index] = { ...nextResults[index], ...task };
    return { ...cached, results: nextResults };
  }

  const page = Number(params?.page ?? 1);
  if (!matches || page > 1) {
    return cached;
  }

  return {
    ...cached,
    count: cached.count + 1,
    results: [task, ...cached.results],
  };
}

export function upsertTaskCaches<T extends TaskEntity>(
  taskKind: TaskKind,
  task: T
): void {
  const keys = getTaskKeys(taskKind);
  queryClient.setQueryData(keys.detail(task.id), task);
  for (const query of queryClient
    .getQueryCache()
    .findAll({ queryKey: keys.lists })) {
    const params = getListParams(query.queryKey);
    queryClient.setQueryData<PaginatedResponse<T> | undefined>(
      query.queryKey,
      (cached) => patchListEntry(taskKind, cached, task, params)
    );
  }
}

export function removeTaskCaches(taskKind: TaskKind, taskId: string): void {
  const keys = getTaskKeys(taskKind);
  const derivedKeys = getTaskDerivedKeys(taskKind, taskId);
  queryClient.removeQueries({ queryKey: keys.detail(taskId) });
  queryClient.removeQueries({ queryKey: keys.executions(taskId) });
  queryClient.removeQueries({ queryKey: derivedKeys.summaries });
  queryClient.removeQueries({ queryKey: derivedKeys.strategyEvents });
  queryClient.removeQueries({ queryKey: derivedKeys.logComponents });
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
  for (const query of queryClient
    .getQueryCache()
    .findAll({ queryKey: keys.lists })) {
    const params = getListParams(query.queryKey);
    queryClient.setQueryData<PaginatedResponse<TaskEntity> | undefined>(
      query.queryKey,
      (cached) => {
        if (!cached) {
          return cached;
        }
        const current = cached.results.find((entry) => entry.id === taskId);
        if (!current) {
          return cached;
        }
        return patchListEntry(
          taskKind,
          cached,
          { ...current, status } as TaskEntity,
          params
        );
      }
    );
  }
}

export async function invalidateTaskDerivedCaches(
  taskKind: TaskKind,
  taskId: string
): Promise<void> {
  await invalidateTaskDerivedByKind(taskId, taskKind);
}
