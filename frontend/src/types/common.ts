// Common types and enums for task-based strategy configuration
// Re-export generated types for consistency

export { StatusEnum as TaskStatus } from '../api/types';
export { DataSourceEnum as DataSource } from '../api/types';

export enum TaskType {
  BACKTEST = 'backtest',
  TRADING = 'trading',
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
