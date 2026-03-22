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

export interface TaskTrendReplayPosition {
  id: string;
  instrument: string;
  direction: 'long' | 'short';
  units: number;
  entry_price: string;
  entry_time: string;
  exit_price?: string | null;
  exit_time?: string | null;
  planned_exit_price?: string | null;
  planned_exit_price_formula?: string | null;
  is_open: boolean;
  layer_index?: number | null;
  retracement_count?: number | null;
  trade_ids?: string[];
  updated_at?: string | null;
}

export interface TaskTrendReplayTrade {
  id?: string;
  direction?: string | null;
  units: string | number;
  instrument: string;
  price: string | number;
  execution_method?: string;
  execution_method_display?: string;
  layer_index?: number | null;
  retracement_count?: number | null;
  description?: string;
  timestamp: string;
  position_id?: string | null;
  updated_at?: string | null;
}

export interface TaskTrendReplayTradeMarker {
  trade_id: string;
  timestamp: string;
  direction: 'long' | 'short';
  action: 'open' | 'close';
  lots: number | null;
  label: string;
}

export interface TaskTrendReplayResponse {
  trades: TaskTrendReplayTrade[];
  positions: TaskTrendReplayPosition[];
  trade_markers: TaskTrendReplayTradeMarker[];
  meta: {
    mode: 'latest' | 'windowed';
    page: number;
    page_size: number;
    total_trades: number;
    returned_trades: number;
    has_more_trades: boolean;
    latest_trade_updated_at: string | null;
    range_from: string | null;
    range_to: string | null;
  };
}

export async function fetchTaskTrendReplay(
  taskType: TaskType,
  taskId: string | number,
  params?: Record<string, string | number | undefined>
): Promise<TaskTrendReplayResponse> {
  return fetchTaskResourceObject<TaskTrendReplayResponse>(
    taskType,
    taskId,
    'trend-replay',
    params
  );
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
