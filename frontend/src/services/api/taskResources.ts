import { ApiError, api } from '../../api/apiClient';
import { TaskType } from '../../types/common';
import { fetchPaginatedResults, type PaginatedApiResponse } from './pagination';

function buildTaskPrefix(taskType: TaskType): string {
  return taskType === TaskType.BACKTEST
    ? '/api/trading/tasks/backtest'
    : '/api/trading/tasks/trading';
}

function getTaskResourcePath(
  taskType: TaskType,
  taskId: string | number,
  resource: string
): string {
  return `${buildTaskPrefix(taskType)}/${taskId}/${resource}/`;
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
  const path = getTaskResourcePath(taskType, taskId, resource);
  return api.get<PaginatedApiResponse<T>>(path, params).then((data) => ({
    count: data.count,
    next: data.next,
    previous: data.previous,
    results: data.results ?? [],
  }));
}

export async function fetchTaskResourceObject<T>(
  taskType: TaskType,
  taskId: string | number,
  resource: string,
  params?: Record<string, string | number | undefined>
): Promise<T> {
  return api.get<T>(getTaskResourcePath(taskType, taskId, resource), params);
}

export async function fetchPaginatedTaskResource<T>(
  taskType: TaskType,
  taskId: string | number,
  resource: string,
  params: Record<string, string | number | undefined>
): Promise<T[]> {
  return fetchPaginatedResults(
    getTaskResourcePath(taskType, taskId, resource),
    params
  );
}
