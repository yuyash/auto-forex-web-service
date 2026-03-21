import { apiConfig } from '../../api/apiConfig';
import { ApiError, api } from '../../api/apiClient';
import { TaskType } from '../../types/common';

type PaginatedResult<T> = {
  count?: number;
  next?: string | null;
  previous?: string | null;
  results?: T[];
};

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

function parseNextRequest(nextUrl: string): {
  path: string;
  query: Record<string, string>;
} {
  const fallbackBase =
    apiConfig.BASE ||
    (typeof window !== 'undefined'
      ? window.location.origin
      : 'http://localhost');
  const parsedUrl = new URL(nextUrl, fallbackBase);

  return {
    path: `${parsedUrl.pathname}${parsedUrl.hash ?? ''}`,
    query: Object.fromEntries(parsedUrl.searchParams.entries()),
  };
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
  return api.get<PaginatedResult<T>>(path, params).then((data) => ({
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

export async function fetchAllTaskResourcePages<T>(
  taskType: TaskType,
  taskId: string | number,
  resource: string,
  params: Record<string, string | number | undefined>
): Promise<T[]> {
  const results: T[] = [];
  let nextRequest: {
    path: string;
    query?: Record<string, string | number | undefined>;
  } | null = {
    path: getTaskResourcePath(taskType, taskId, resource),
    query: params,
  };

  while (nextRequest) {
    const response = await api.get<PaginatedResult<T>>(
      nextRequest.path,
      nextRequest.query
    );
    results.push(...(response.results ?? []));
    nextRequest = response.next ? parseNextRequest(response.next) : null;
  }

  return results;
}
