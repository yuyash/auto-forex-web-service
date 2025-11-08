// Common types and enums for task-based strategy configuration

export enum TaskStatus {
  CREATED = 'created',
  RUNNING = 'running',
  STOPPED = 'stopped',
  PAUSED = 'paused',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export enum TaskType {
  BACKTEST = 'backtest',
  TRADING = 'trading',
}

export enum DataSource {
  POSTGRESQL = 'postgresql',
  ATHENA = 'athena',
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ApiError {
  error?: {
    code?: string;
    message: string;
    details?: Record<string, unknown>;
  };
  message?: string;
  detail?: string;
  [key: string]: unknown;
}

export interface ListParams {
  page?: number;
  page_size?: number;
  search?: string;
  ordering?: string;
}
