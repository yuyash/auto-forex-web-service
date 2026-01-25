// Common types and enums for task-based strategy configuration
// Re-export generated types for consistency

export { StatusEnum as TaskStatus } from '../api/generated';
export { DataSourceEnum as DataSource } from '../api/generated';
export { TradingModeEnum as TradingMode } from '../api/generated';

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
