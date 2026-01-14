// Execution API service for real-time task monitoring

import { apiClient } from './client';
import type {
  ExecutionMetricsCheckpoint,
  EquityPoint,
  BacktestStrategyEvent,
  Trade,
} from '../../types';

export interface ExecutionStatusResponse {
  execution_id: number;
  task_id: number;
  task_type: 'backtest' | 'trading';
  status: string;
  progress: number;
  ticks_processed: number;
  trades_executed: number;
  current_balance: string;
  current_pnl: string;
  realized_pnl?: string;
  unrealized_pnl?: string;
  last_tick_timestamp?: string;
  started_at: string;
  completed_at?: string;
}

export interface ExecutionEventsResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: BacktestStrategyEvent[];
}

export interface ExecutionTradesResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Trade[];
}

export interface ExecutionEquityResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: EquityPoint[];
}

export const executionApi = {
  /**
   * Get current status of an execution
   */
  getStatus: (executionId: number): Promise<ExecutionStatusResponse> => {
    return apiClient.get<ExecutionStatusResponse>(
      `/trading/executions/${executionId}/status/`
    );
  },

  /**
   * Get events for an execution with incremental fetching
   */
  getEvents: (
    executionId: number,
    params?: {
      since_sequence?: number;
      event_type?: string;
      page_size?: number;
    }
  ): Promise<ExecutionEventsResponse> => {
    return apiClient.get<ExecutionEventsResponse>(
      `/trading/executions/${executionId}/events/`,
      params
    );
  },

  /**
   * Get trades for an execution with incremental fetching
   */
  getTrades: (
    executionId: number,
    params?: {
      since_sequence?: number;
      instrument?: string;
      direction?: 'long' | 'short';
      page_size?: number;
    }
  ): Promise<ExecutionTradesResponse> => {
    return apiClient.get<ExecutionTradesResponse>(
      `/trading/executions/${executionId}/trades/`,
      params
    );
  },

  /**
   * Get equity curve for an execution with incremental fetching
   */
  getEquity: (
    executionId: number,
    params?: { since_sequence?: number; page_size?: number }
  ): Promise<ExecutionEquityResponse> => {
    return apiClient.get<ExecutionEquityResponse>(
      `/trading/executions/${executionId}/equity/`,
      params
    );
  },

  /**
   * Get latest metrics checkpoint for an execution
   */
  getMetricsLatest: (
    executionId: number
  ): Promise<ExecutionMetricsCheckpoint> => {
    return apiClient.get<ExecutionMetricsCheckpoint>(
      `/trading/executions/${executionId}/metrics/latest/`
    );
  },
};
