/**
 * Backtest Task API service using generated OpenAPI client
 *
 * This module provides a wrapper around the generated TradingService
 * for backtest task operations with consistent error handling.
 */

import { TradingService } from '../../api/generated/services/TradingService';
import { withRetry } from '../../api/client';
import type {
  BacktestTaskCreateRequest,
  PatchedBacktestTaskCreateRequest,
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
      TradingService.tradingBacktestTasksList(
        params?.config_id,
        params?.ordering,
        params?.page,
        params?.search,
        params?.status,
        params?.strategy_type
      )
    );
  },

  /**
   * Get a single backtest task by ID
   */
  get: (id: number) => {
    return withRetry(() => TradingService.tradingBacktestTasksRetrieve(id));
  },

  /**
   * Create a new backtest task
   */
  create: (data: BacktestTaskCreateRequest) => {
    return withRetry(() => TradingService.tradingBacktestTasksCreate(data));
  },

  /**
   * Update an existing backtest task
   */
  update: (id: number, data: BacktestTaskCreateRequest) => {
    return withRetry(() => TradingService.tradingBacktestTasksUpdate(id, data));
  },

  /**
   * Partially update an existing backtest task
   */
  partialUpdate: (id: number, data: PatchedBacktestTaskCreateRequest) => {
    return withRetry(() =>
      TradingService.tradingBacktestTasksPartialUpdate(id, data)
    );
  },

  /**
   * Delete a backtest task
   */
  delete: (id: number) => {
    return withRetry(() => TradingService.tradingBacktestTasksDestroy(id));
  },

  /**
   * Copy a backtest task with a new name
   */
  copy: (id: number) => {
    return withRetry(() => TradingService.tradingBacktestTasksCopyCreate(id));
  },

  /**
   * Start a backtest task execution
   * Returns execution_id in the response
   */
  start: (id: number) => {
    return withRetry(() => TradingService.tradingBacktestTasksStartCreate(id));
  },

  /**
   * Stop a running backtest task
   */
  stop: (id: number) => {
    return withRetry(() => TradingService.tradingBacktestTasksStopCreate(id));
  },

  /**
   * Resume a paused backtest task
   * Returns execution_id in the response
   */
  resume: (id: number) => {
    return withRetry(() => TradingService.tradingBacktestTasksResumeCreate(id));
  },

  /**
   * Restart a backtest task with fresh state
   * Returns execution_id in the response
   */
  restart: (id: number) => {
    return withRetry(() =>
      TradingService.tradingBacktestTasksRestartCreate(id)
    );
  },

  /**
   * Get current task status and execution details
   * Includes execution_id when status is "running"
   */
  getStatus: (id: number) => {
    return withRetry(() =>
      TradingService.tradingBacktestTasksStatusRetrieve(id)
    );
  },

  /**
   * Get execution history for a backtest task
   */
  getExecutions: (id: number) => {
    return withRetry(() =>
      TradingService.tradingBacktestTasksExecutionsRetrieve(id)
    );
  },
};
