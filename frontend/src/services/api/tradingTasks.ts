/**
 * Trading Task API service using generated OpenAPI client
 *
 * This module provides a wrapper around the generated TradingService
 * for trading task operations with consistent error handling.
 */

import { TradingService } from '../../api/generated/services/TradingService';
import { withRetry } from '../../api/client';
import type {
  TradingTaskRequest,
  PatchedTradingTaskRequest,
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
      TradingService.tradingTasksTradingList(
        params?.ordering,
        params?.page,
        params?.search
      )
    );
  },

  /**
   * Get a single trading task by ID
   */
  get: (id: number) => {
    return withRetry(() => TradingService.tradingTasksTradingRetrieve(id));
  },

  /**
   * Create a new trading task
   */
  create: (data: TradingTaskRequest) => {
    return withRetry(() => TradingService.tradingTasksTradingCreate(data));
  },

  /**
   * Update an existing trading task
   */
  update: (id: number, data: TradingTaskRequest) => {
    return withRetry(() => TradingService.tradingTasksTradingUpdate(id, data));
  },

  /**
   * Partially update an existing trading task
   */
  partialUpdate: (id: number, data: PatchedTradingTaskRequest) => {
    return withRetry(() =>
      TradingService.tradingTasksTradingPartialUpdate(id, data)
    );
  },

  /**
   * Delete a trading task
   */
  delete: (id: number) => {
    return withRetry(() => TradingService.tradingTasksTradingDestroy(id));
  },

  /**
   * Submit a trading task for execution (new task-based API)
   */
  start: (id: number) => {
    return withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingTasksTradingSubmitCreate(id, {} as any)
    );
  },

  /**
   * Stop a running trading task (new task-based API)
   */
  stop: (
    id: number,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _mode?: 'immediate' | 'graceful' | 'graceful_close'
  ) => {
    return withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingTasksTradingStopCreate(id, {} as any)
    );
  },

  /**
   * Pause a trading task (not implemented yet)
   */
  pause: (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _id: number
  ) => {
    // Note: Pause endpoint doesn't exist yet
    throw new Error('Pause is not implemented for trading tasks');
  },

  /**
   * Resume a cancelled trading task (new task-based API)
   */
  resume: (id: number) => {
    return withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingTasksTradingResumeCreate(id, {} as any)
    );
  },

  /**
   * Restart a trading task with fresh state (new task-based API)
   */
  restart: (id: number) => {
    return withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingTasksTradingRestartCreate(id, {} as any)
    );
  },
};
