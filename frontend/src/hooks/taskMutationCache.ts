import { queryClient, queryKeys } from '../config/reactQuery';
import type { BacktestTask, PaginatedResponse, TradingTask } from '../types';
import { TaskType } from '../types/common';
import {
  clearTaskExecutions,
  invalidateTaskDerivedByKind,
  patchTaskSummaryStatus,
  prependTaskExecution,
} from './taskResourceCache';

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

function compareValues(
  left: string | number | boolean | undefined,
  right: string | number | boolean | undefined,
  ordering: string
): number {
  const direction = ordering.startsWith('-') ? -1 : 1;
  const leftValue = left ?? '';
  const rightValue = right ?? '';
  if (leftValue < rightValue) {
    return -1 * direction;
  }
  if (leftValue > rightValue) {
    return 1 * direction;
  }
  return 0;
}

function sortTaskResults<T extends TaskEntity>(
  results: T[],
  ordering?: string
): T[] {
  if (!ordering) {
    return results;
  }

  const field = ordering.replace(/^-/, '');
  const sorted = [...results];
  sorted.sort((left, right) => {
    switch (field) {
      case 'name':
      case 'status':
      case 'strategy_type':
      case 'config_name':
      case 'updated_at':
      case 'created_at':
      case 'instrument':
        return compareValues(
          left[field as keyof TaskEntity] as string | undefined,
          right[field as keyof TaskEntity] as string | undefined,
          ordering
        );
      case 'account_name':
        return compareValues(
          (left as TradingTask).account_name,
          (right as TradingTask).account_name,
          ordering
        );
      default:
        return 0;
    }
  });
  return sorted;
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
    return {
      ...cached,
      results: sortTaskResults(
        nextResults,
        typeof params?.ordering === 'string' ? params.ordering : undefined
      ),
    };
  }

  const page = Number(params?.page ?? 1);
  if (!matches || page > 1) {
    return cached;
  }

  return {
    ...cached,
    count: cached.count + 1,
    results: sortTaskResults(
      [task, ...cached.results],
      typeof params?.ordering === 'string' ? params.ordering : undefined
    ),
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
  patchTaskSummaryStatus(
    taskId,
    taskKind === 'backtest' ? TaskType.BACKTEST : TaskType.TRADING,
    status
  );
}

export async function invalidateTaskDerivedCaches(
  taskKind: TaskKind,
  taskId: string
): Promise<void> {
  await invalidateTaskDerivedByKind(taskId, taskKind);
}

export function removeTaskListEntry(taskKind: TaskKind, taskId: string): void {
  const keys = getTaskKeys(taskKind);
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

export function patchTaskDerivedCaches(
  taskKind: TaskKind,
  task: TaskEntity
): void {
  const taskType =
    taskKind === 'backtest' ? TaskType.BACKTEST : TaskType.TRADING;
  patchTaskSummaryStatus(task.id, taskType, String(task.status));

  const latestExecution = task.latest_execution;
  if (!latestExecution?.id) {
    if (task.status === 'created') {
      clearTaskExecutions(task.id, taskType);
    }
    return;
  }

  prependTaskExecution(task.id, taskType, {
    id: latestExecution.id,
    task_type: taskType,
    task_id: task.id,
    execution_number: latestExecution.execution_number,
    status: latestExecution.status,
    progress: latestExecution.progress,
    started_at: latestExecution.started_at,
    completed_at: latestExecution.completed_at,
    error_message: latestExecution.error_message,
    created_at: latestExecution.started_at,
    metrics: {
      total_return: latestExecution.total_return,
      total_pnl: latestExecution.total_pnl,
      total_trades: latestExecution.total_trades,
      winning_trades: latestExecution.winning_trades,
      losing_trades: latestExecution.losing_trades,
      win_rate: latestExecution.win_rate,
    },
  });
}
