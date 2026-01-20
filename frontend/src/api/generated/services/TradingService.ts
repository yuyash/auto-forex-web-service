/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BacktestTask } from '../models/BacktestTask';
import type { BacktestTaskCreate } from '../models/BacktestTaskCreate';
import type { BacktestTaskCreateRequest } from '../models/BacktestTaskCreateRequest';
import type { PaginatedBacktestTaskListList } from '../models/PaginatedBacktestTaskListList';
import type { PaginatedTradingTaskListList } from '../models/PaginatedTradingTaskListList';
import type { PatchedBacktestTaskCreateRequest } from '../models/PatchedBacktestTaskCreateRequest';
import type { PatchedTradingTaskCreateRequest } from '../models/PatchedTradingTaskCreateRequest';
import type { TradingTask } from '../models/TradingTask';
import type { TradingTaskCreate } from '../models/TradingTaskCreate';
import type { TradingTaskCreateRequest } from '../models/TradingTaskCreateRequest';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class TradingService {
  /**
   * List and create backtest tasks.
   * @param configId Filter by configuration ID
   * @param ordering Order results by field (prefix with - for descending)
   * @param page Page number
   * @param search Search in name or description
   * @param status Filter by task status
   * @param strategyType Filter by strategy type
   * @returns PaginatedBacktestTaskListList
   * @throws ApiError
   */
  public static tradingBacktestTasksList(
    configId?: number,
    ordering?: string,
    page?: number,
    search?: string,
    status?: string,
    strategyType?: string
  ): CancelablePromise<PaginatedBacktestTaskListList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/backtest-tasks/',
      query: {
        config_id: configId,
        ordering: ordering,
        page: page,
        search: search,
        status: status,
        strategy_type: strategyType,
      },
    });
  }
  /**
   * List and create backtest tasks.
   * @param requestBody
   * @returns BacktestTaskCreate
   * @throws ApiError
   */
  public static tradingBacktestTasksCreate(
    requestBody: BacktestTaskCreateRequest
  ): CancelablePromise<BacktestTaskCreate> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/backtest-tasks/',
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Retrieve, update, or delete a backtest task.
   * @param taskId
   * @returns BacktestTask
   * @throws ApiError
   */
  public static tradingBacktestTasksRetrieve(
    taskId: number
  ): CancelablePromise<BacktestTask> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/backtest-tasks/{task_id}/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * Retrieve, update, or delete a backtest task.
   * @param taskId
   * @param requestBody
   * @returns BacktestTaskCreate
   * @throws ApiError
   */
  public static tradingBacktestTasksUpdate(
    taskId: number,
    requestBody: BacktestTaskCreateRequest
  ): CancelablePromise<BacktestTaskCreate> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/trading/backtest-tasks/{task_id}/',
      path: {
        task_id: taskId,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Retrieve, update, or delete a backtest task.
   * @param taskId
   * @param requestBody
   * @returns BacktestTaskCreate
   * @throws ApiError
   */
  public static tradingBacktestTasksPartialUpdate(
    taskId: number,
    requestBody?: PatchedBacktestTaskCreateRequest
  ): CancelablePromise<BacktestTaskCreate> {
    return __request(OpenAPI, {
      method: 'PATCH',
      url: '/api/trading/backtest-tasks/{task_id}/',
      path: {
        task_id: taskId,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Retrieve, update, or delete a backtest task.
   * @param taskId
   * @returns void
   * @throws ApiError
   */
  public static tradingBacktestTasksDestroy(
    taskId: number
  ): CancelablePromise<void> {
    return __request(OpenAPI, {
      method: 'DELETE',
      url: '/api/trading/backtest-tasks/{task_id}/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * Copy backtest task.
   * @param taskId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingBacktestTasksCopyCreate(
    taskId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/backtest-tasks/{task_id}/copy/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * Get execution history for backtest task.
   * @param taskId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingBacktestTasksExecutionsRetrieve(
    taskId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/backtest-tasks/{task_id}/executions/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * Restart backtest task with fresh state.
   * @param taskId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingBacktestTasksRestartCreate(
    taskId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/backtest-tasks/{task_id}/restart/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * Resume backtest task execution.
   * @param taskId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingBacktestTasksResumeCreate(
    taskId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/backtest-tasks/{task_id}/resume/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * Start backtest task execution.
   * @param taskId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingBacktestTasksStartCreate(
    taskId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/backtest-tasks/{task_id}/start/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * Get current task status and execution details.
   * @param taskId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingBacktestTasksStatusRetrieve(
    taskId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/backtest-tasks/{task_id}/status/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * Stop backtest task execution.
   * @param taskId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingBacktestTasksStopCreate(
    taskId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/backtest-tasks/{task_id}/stop/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * API endpoint for listing all available trading strategies.
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingStrategiesRetrieve(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/strategies/',
    });
  }
  /**
   * API endpoint for returning default parameters for a strategy.
   * @param strategyId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingStrategiesDefaultsRetrieve(
    strategyId: string
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/strategies/{strategy_id}/defaults/',
      path: {
        strategy_id: strategyId,
      },
    });
  }
  /**
   * List and create strategy configurations.
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingStrategyConfigsRetrieve(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/strategy-configs/',
    });
  }
  /**
   * List and create strategy configurations.
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingStrategyConfigsCreate(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/strategy-configs/',
    });
  }
  /**
   * Retrieve, update, and delete a strategy configuration.
   * @param configId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingStrategyConfigsRetrieve2(
    configId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/strategy-configs/{config_id}/',
      path: {
        config_id: configId,
      },
    });
  }
  /**
   * Retrieve, update, and delete a strategy configuration.
   * @param configId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingStrategyConfigsUpdate(
    configId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/trading/strategy-configs/{config_id}/',
      path: {
        config_id: configId,
      },
    });
  }
  /**
   * Retrieve, update, and delete a strategy configuration.
   * @param configId
   * @returns void
   * @throws ApiError
   */
  public static tradingStrategyConfigsDestroy(
    configId: number
  ): CancelablePromise<void> {
    return __request(OpenAPI, {
      method: 'DELETE',
      url: '/api/trading/strategy-configs/{config_id}/',
      path: {
        config_id: configId,
      },
    });
  }
  /**
   * List and create trading tasks.
   *
   * GET: List all trading tasks for the authenticated user with filtering and pagination
   * POST: Create a new trading task
   * @param configId Filter by configuration ID
   * @param ordering Order results by field (prefix with - for descending)
   * @param page Page number
   * @param search Search in name or description
   * @param status Filter by task status
   * @param strategyType Filter by strategy type
   * @returns PaginatedTradingTaskListList
   * @throws ApiError
   */
  public static tradingTradingTasksList(
    configId?: number,
    ordering?: string,
    page?: number,
    search?: string,
    status?: string,
    strategyType?: string
  ): CancelablePromise<PaginatedTradingTaskListList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/trading-tasks/',
      query: {
        config_id: configId,
        ordering: ordering,
        page: page,
        search: search,
        status: status,
        strategy_type: strategyType,
      },
    });
  }
  /**
   * List and create trading tasks.
   *
   * GET: List all trading tasks for the authenticated user with filtering and pagination
   * POST: Create a new trading task
   * @param requestBody
   * @returns TradingTaskCreate
   * @throws ApiError
   */
  public static tradingTradingTasksCreate(
    requestBody?: TradingTaskCreateRequest
  ): CancelablePromise<TradingTaskCreate> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/trading-tasks/',
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Retrieve, update, or delete a trading task.
   *
   * GET: Retrieve trading task details
   * PUT/PATCH: Update trading task
   * DELETE: Delete trading task
   * @param taskId
   * @returns TradingTask
   * @throws ApiError
   */
  public static tradingTradingTasksRetrieve(
    taskId: number
  ): CancelablePromise<TradingTask> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/trading-tasks/{task_id}/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * Retrieve, update, or delete a trading task.
   *
   * GET: Retrieve trading task details
   * PUT/PATCH: Update trading task
   * DELETE: Delete trading task
   * @param taskId
   * @param requestBody
   * @returns TradingTaskCreate
   * @throws ApiError
   */
  public static tradingTradingTasksUpdate(
    taskId: number,
    requestBody?: TradingTaskCreateRequest
  ): CancelablePromise<TradingTaskCreate> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/trading/trading-tasks/{task_id}/',
      path: {
        task_id: taskId,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Retrieve, update, or delete a trading task.
   *
   * GET: Retrieve trading task details
   * PUT/PATCH: Update trading task
   * DELETE: Delete trading task
   * @param taskId
   * @param requestBody
   * @returns TradingTaskCreate
   * @throws ApiError
   */
  public static tradingTradingTasksPartialUpdate(
    taskId: number,
    requestBody?: PatchedTradingTaskCreateRequest
  ): CancelablePromise<TradingTaskCreate> {
    return __request(OpenAPI, {
      method: 'PATCH',
      url: '/api/trading/trading-tasks/{task_id}/',
      path: {
        task_id: taskId,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Retrieve, update, or delete a trading task.
   *
   * GET: Retrieve trading task details
   * PUT/PATCH: Update trading task
   * DELETE: Delete trading task
   * @param taskId
   * @returns void
   * @throws ApiError
   */
  public static tradingTradingTasksDestroy(
    taskId: number
  ): CancelablePromise<void> {
    return __request(OpenAPI, {
      method: 'DELETE',
      url: '/api/trading/trading-tasks/{task_id}/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * Copy trading task.
   *
   * Request body:
   * - new_name: Name for the copied task (required)
   * @param taskId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingTradingTasksCopyCreate(
    taskId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/trading-tasks/{task_id}/copy/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * Get execution history for trading task.
   *
   * Returns all executions ordered by execution number (most recent first).
   * @param taskId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingTradingTasksExecutionsRetrieve(
    taskId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/trading-tasks/{task_id}/executions/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * Restart trading task with fresh state.
   *
   * Clears strategy_state and starts a new execution. Task can be in any
   * state (stopped, failed) to be restarted, but not running or paused.
   *
   * Request body:
   * - clear_state: bool (default: True) - Clear strategy state
   * @param taskId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingTradingTasksRestartCreate(
    taskId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/trading-tasks/{task_id}/restart/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * Resume trading task execution.
   * @param taskId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingTradingTasksResumeCreate(
    taskId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/trading-tasks/{task_id}/resume/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * Start trading task execution.
   *
   * Validates task status in database AND checks celery task lock status
   * before starting. Creates a new TaskExecution and queues the trading
   * task for processing. Enforces one active task per account constraint.
   * @param taskId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingTradingTasksStartCreate(
    taskId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/trading-tasks/{task_id}/start/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * Get current task status and execution details.
   *
   * Used by frontend for polling fallback when WebSocket connection fails.
   * Returns current status, progress percentage, and latest execution details.
   * Also detects and auto-completes stale running/stopped tasks.
   * @param taskId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingTradingTasksStatusRetrieve(
    taskId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/trading-tasks/{task_id}/status/',
      path: {
        task_id: taskId,
      },
    });
  }
  /**
   * Stop trading task execution.
   *
   * Validates task status in database AND checks celery task lock status
   * before stopping. Updates task to stopped state and triggers cleanup.
   *
   * Request body (optional):
   * - mode: Stop mode ('immediate', 'graceful', 'graceful_close')
   * Default: 'graceful'
   * @param taskId
   * @returns any No response body
   * @throws ApiError
   */
  public static tradingTradingTasksStopCreate(
    taskId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/trading-tasks/{task_id}/stop/',
      path: {
        task_id: taskId,
      },
    });
  }
}
