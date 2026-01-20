/**
 * Trading Task API service using generated OpenAPI client
 *
 * This module provides a wrapper around the generated TradingService
 * for trading task operations with consistent error handling.
 */

import { TradingService } from '../../api/generated/services/TradingService';
import { withRetry } from '../../api/client';
import type {
  TradingTaskCreateRequest,
  PatchedTradingTaskCreateRequest,
} from '../../api/generated';

export const tradingTasksApi = {
  /**
   * List all trading tasks for the current user
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
      TradingService.tradingTradingTasksList(
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
   * Get a single trading task by ID
   */
  get: (id: number) => {
    return withRetry(() => TradingService.tradingTradingTasksRetrieve(id));
  },

  /**
   * Create a new trading task
   */
  create: (data: TradingTaskCreateRequest) => {
    return withRetry(() => TradingService.tradingTradingTasksCreate(data));
  },

  /**
   * Update an existing trading task
   */
  update: (id: number, data: TradingTaskCreateRequest) => {
    return withRetry(() => TradingService.tradingTradingTasksUpdate(id, data));
  },

  /**
   * Partially update an existing trading task
   */
  partialUpdate: (id: number, data: PatchedTradingTaskCreateRequest) => {
    return withRetry(() =>
      TradingService.tradingTradingTasksPartialUpdate(id, data)
    );
  },

  /**
   * Delete a trading task
   */
  delete: (id: number) => {
    return withRetry(() => TradingService.tradingTradingTasksDestroy(id));
  },

  /**
   * Copy a trading task with a new name
   */
  copy: (id: number) => {
    return withRetry(() => TradingService.tradingTradingTasksCopyCreate(id));
  },

  /**
   * Start a trading task execution
   * Returns execution_id in the response
   */
  start: (id: number) => {
    return withRetry(() => TradingService.tradingTradingTasksStartCreate(id));
  },

  /**
   * Stop a running trading task
   * @param id - Task ID
   * @param mode - Stop mode: 'immediate', 'graceful', or 'graceful_close'
   */
  stop: (id: number) => {
    return withRetry(() => TradingService.tradingTradingTasksStopCreate(id));
  },

  /**
   * Resume a paused trading task
   * Returns execution_id in the response
   */
  resume: (id: number) => {
    return withRetry(() => TradingService.tradingTradingTasksResumeCreate(id));
  },

  /**
   * Restart a trading task with fresh state
   * Returns execution_id in the response
   */
  restart: (id: number) => {
    return withRetry(() => TradingService.tradingTradingTasksRestartCreate(id));
  },

  /**
   * Get current task status and execution details
   * Includes execution_id when status is "running"
   */
  getStatus: (id: number) => {
    return withRetry(() =>
      TradingService.tradingTradingTasksStatusRetrieve(id)
    );
  },

  /**
   * Get execution history for a trading task
   */
  getExecutions: (id: number) => {
    return withRetry(() =>
      TradingService.tradingTradingTasksExecutionsRetrieve(id)
    );
  },
};
