import { ApiError, api } from '../../api/apiClient';
import { TaskType } from '../../types/common';

function buildTaskPrefix(taskType: TaskType): string {
  return taskType === TaskType.BACKTEST
    ? '/api/trading/tasks/backtest'
    : '/api/trading/tasks/trading';
}

export function isApiErrorWithStatus(
  error: unknown
): error is ApiError & { status: number } {
  return error instanceof ApiError;
}

export async function fetchTaskResourcePage<T>(
  taskType: TaskType,
  taskId: string | number,
  resource: string,
  params: Record<string, string>
): Promise<{
  count?: number;
  next?: string | null;
  previous?: string | null;
  results: T[];
}> {
  const prefix = buildTaskPrefix(taskType);
  return api
    .get<{
      count?: number;
      next?: string | null;
      previous?: string | null;
      results?: T[];
    }>(`${prefix}/${taskId}/${resource}/`, params)
    .then((data) => ({
      count: data.count,
      next: data.next,
      previous: data.previous,
      results: data.results ?? [],
    }));
}
