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
import type {
  TradingTask,
  TradingTaskListParams,
  PaginatedResponse,
} from '../../types';
import type {
  ExecutionMetricsCheckpoint,
  EquityPoint,
  Trade,
  BacktestStrategyEvent,
} from '../../types/execution';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const toLocal = (task: any): TradingTask => task as TradingTask;

export const tradingTasksApi = {
  /**
   * List all trading tasks for the current user
   */
  list: async (
    params?: TradingTaskListParams
  ): Promise<PaginatedResponse<TradingTask>> => {
    const result = await withRetry(() =>
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
    return {
      count: result.count,
      next: result.next ?? null,
      previous: result.previous ?? null,
      results: result.results.map(toLocal),
    };
  },

  /**
   * Get a single trading task by ID
   */
  get: async (id: number | string): Promise<TradingTask> => {
    const result = await withRetry(() =>
      TradingService.tradingTasksTradingRetrieve(String(id))
    );
    return toLocal(result);
  },

  /**
   * Create a new trading task
   */
  create: async (data: TradingTaskRequest): Promise<TradingTask> => {
    const result = await withRetry(() =>
      TradingService.tradingTasksTradingCreate(data)
    );
    return toLocal(result);
  },

  /**
   * Update an existing trading task
   */
  update: async (
    id: number | string,
    data: TradingTaskRequest
  ): Promise<TradingTask> => {
    const result = await withRetry(() =>
      TradingService.tradingTasksTradingUpdate(String(id), data)
    );
    return toLocal(result);
  },

  /**
   * Partially update an existing trading task
   */
  partialUpdate: async (
    id: number | string,
    data: PatchedTradingTaskRequest
  ): Promise<TradingTask> => {
    const result = await withRetry(() =>
      TradingService.tradingTasksTradingPartialUpdate(String(id), data)
    );
    return toLocal(result);
  },

  /**
   * Delete a trading task
   */
  delete: async (id: number | string): Promise<void> => {
    return withRetry(() =>
      TradingService.tradingTasksTradingDestroy(String(id))
    );
  },

  /**
   * Submit a trading task for execution
   */
  start: async (id: number | string): Promise<TradingTask> => {
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingTasksTradingStartCreate(String(id), {} as any)
    );
    return toLocal(result);
  },

  /**
   * Stop a running trading task
   */
  stop: async (
    id: number | string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _mode?: 'immediate' | 'graceful' | 'graceful_close'
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ): Promise<Record<string, any>> => {
    return withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingTasksTradingStopCreate(String(id), {} as any)
    );
  },

  /**
   * Pause a trading task (not implemented yet)
   */
  pause: (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _id: number | string
  ): Promise<TradingTask> => {
    throw new Error('Pause is not implemented for trading tasks');
  },

  /**
   * Resume a cancelled trading task
   */
  resume: async (id: number | string): Promise<TradingTask> => {
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingTasksTradingResumeCreate(String(id), {} as any)
    );
    return toLocal(result);
  },

  /**
   * Restart a trading task with fresh state
   */
  restart: async (
    id: number | string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _clearState?: boolean
  ): Promise<TradingTask> => {
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingTasksTradingRestartCreate(String(id), {} as any)
    );
    return toLocal(result);
  },

  /**
   * Get executions for a trading task
   */
  getExecutions: async (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _id: number | string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _params?: { page?: number; page_size?: number; include_metrics?: boolean }
  ): Promise<PaginatedResponse<import('../../types').TaskExecution>> => {
    // Executions are not yet supported in the generated API
    return { count: 0, next: null, previous: null, results: [] };
  },

  /**
   * Copy a trading task
   */
  copy: async (
    id: number | string,

    _data: { new_name: string }
  ): Promise<TradingTask> => {
    // Copy is implemented as create with same config
    const original = await withRetry(() =>
      TradingService.tradingTasksTradingRetrieve(String(id))
    );
    const result = await withRetry(() =>
      TradingService.tradingTasksTradingCreate({
        name: _data.new_name,
        config: original.config,
        oanda_account: original.oanda_account,
        description: original.description,
        sell_on_stop: original.sell_on_stop,
        instrument: original.instrument,
        trading_mode: original.trading_mode,
      })
    );
    return toLocal(result);
  },

  /**
   * Get metrics checkpoint for a trading task
   */
  getMetricsCheckpoint: async (
    id: number | string
  ): Promise<{ checkpoint: ExecutionMetricsCheckpoint | null }> => {
    // Stub: metrics checkpoint not yet available in generated API
    const task = await withRetry(() =>
      TradingService.tradingTasksTradingRetrieve(String(id))
    );
    const execution = (task as unknown as TradingTask).latest_execution;
    return {
      checkpoint: execution
        ? ({
            total_return: execution.total_return,
            total_pnl: execution.total_pnl,
            total_trades: execution.total_trades,
            winning_trades: execution.winning_trades,
            losing_trades: execution.losing_trades,
            win_rate: execution.win_rate,
          } as ExecutionMetricsCheckpoint)
        : null,
    };
  },

  /**
   * Get equity curve for a trading task
   */
  getEquityCurve: async (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _id: number | string
  ): Promise<{ equity_curve: EquityPoint[] }> => {
    // Stub: equity curve endpoint not yet available
    return { equity_curve: [] };
  },

  /**
   * Get trade logs for a trading task
   */
  getTradeLogs: async (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _id: number | string
  ): Promise<{ trade_logs: Trade[] }> => {
    // Stub: trade logs endpoint not yet available
    return { trade_logs: [] };
  },

  /**
   * Get strategy events for a trading task
   */
  getStrategyEvents: async (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _id: number | string
  ): Promise<{ strategy_events: BacktestStrategyEvent[] }> => {
    // Stub: strategy events endpoint not yet available
    return { strategy_events: [] };
  },
};
