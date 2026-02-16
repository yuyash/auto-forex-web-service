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
    page_size?: number;
    search?: string;
    status?: string;
    config_id?: string;
    strategy_type?: string;
    account_id?: string;
  }) => {
    return withRetry(() =>
      TradingService.tradingTasksTradingList(
        params?.status,
        params?.config_id,
        params?.strategy_type,
        params?.account_id,
        params?.ordering,
        params?.page,
        params?.page_size,
        params?.search
      )
    );
  },

  /**
   * Get a single trading task by ID
   */
  get: (id: string) => {
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
  update: (id: string, data: TradingTaskRequest) => {
    return withRetry(() => TradingService.tradingTasksTradingUpdate(id, data));
  },

  /**
   * Partially update an existing trading task
   */
  partialUpdate: (id: string, data: PatchedTradingTaskRequest) => {
    return withRetry(() =>
      TradingService.tradingTasksTradingPartialUpdate(id, data)
    );
  },

  /**
   * Delete a trading task
   */
  delete: (id: string) => {
    return withRetry(() => TradingService.tradingTasksTradingDestroy(id));
  },

  /**
   * Submit a trading task for execution (new task-based API)
   */
  start: (id: string) => {
    return withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingTasksTradingSubmitCreate(id, {} as any)
    );
  },

  /**
   * Stop a running trading task (new task-based API)
   */
  stop: (
    id: string,
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
    _id: string
  ) => {
    // Note: Pause endpoint doesn't exist yet
    throw new Error('Pause is not implemented for trading tasks');
  },

  /**
   * Resume a cancelled trading task (new task-based API)
   */
  resume: (id: string) => {
    return withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingTasksTradingResumeCreate(id, {} as any)
    );
  },

  /**
   * Restart a trading task with fresh state (new task-based API)
   */
  restart: (id: string) => {
    return withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingTasksTradingRestartCreate(id, {} as any)
    );
  },
};
