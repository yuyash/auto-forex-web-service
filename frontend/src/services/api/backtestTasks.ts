/**
 * Backtest Task API service using generated OpenAPI client
 *
 * This module provides a wrapper around the generated TradingService
 * for backtest task operations with consistent error handling.
 */

import { TradingService } from '../../api/generated/services/TradingService';
import { withRetry } from '../../api/client';
import type {
  BacktestTaskRequest,
  PatchedBacktestTaskRequest,
} from '../../api/generated';

export const backtestTasksApi = {
  /**
   * List all backtest tasks for the current user
   */
  list: (params?: {
    ordering?: string;
    page?: number;
    search?: string;
    status?: string;
    config_id?: number;
    strategy_type?: string;
  }) => {
    return withRetry(() =>
      TradingService.tradingTasksBacktestList(
        params?.ordering,
        params?.page,
        params?.search
      )
    );
  },

  /**
   * Get a single backtest task by ID
   */
  get: (id: number) => {
    return withRetry(() => TradingService.tradingTasksBacktestRetrieve(id));
  },

  /**
   * Create a new backtest task
   */
  create: (data: BacktestTaskRequest) => {
    return withRetry(() => TradingService.tradingTasksBacktestCreate(data));
  },

  /**
   * Update an existing backtest task
   */
  update: (id: number, data: BacktestTaskRequest) => {
    return withRetry(() => TradingService.tradingTasksBacktestUpdate(id, data));
  },

  /**
   * Partially update an existing backtest task
   */
  partialUpdate: (id: number, data: PatchedBacktestTaskRequest) => {
    return withRetry(() =>
      TradingService.tradingTasksBacktestPartialUpdate(id, data)
    );
  },

  /**
   * Delete a backtest task
   */
  delete: (id: number) => {
    return withRetry(() => TradingService.tradingTasksBacktestDestroy(id));
  },

  /**
   * Submit a backtest task for execution (new task-based API)
   */
  start: (id: number) => {
    return withRetry(() =>
      TradingService.tradingTasksBacktestSubmitCreate(id, {} as any)
    );
  },

  /**
   * Stop a running backtest task (new task-based API)
   */
  stop: (id: number) => {
    return withRetry(() =>
      TradingService.tradingTasksBacktestStopCreate(id, {} as any)
    );
  },

  /**
   * Pause a running backtest task (new task-based API)
   */
  pause: (id: number) => {
    return withRetry(() =>
      TradingService.tradingTasksBacktestPauseCreate(id, {} as any)
    );
  },

  /**
   * Resume a paused backtest task (new task-based API)
   */
  resume: (id: number) => {
    return withRetry(() =>
      TradingService.tradingTasksBacktestResumeCreate(id, {} as any)
    );
  },

  /**
   * Restart a backtest task with fresh state (new task-based API)
   */
  restart: (id: number) => {
    return withRetry(() =>
      TradingService.tradingTasksBacktestRestartCreate(id, {} as any)
    );
  },
};
