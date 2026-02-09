/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BacktestTask } from '../models/BacktestTask';
import type { BacktestTaskRequest } from '../models/BacktestTaskRequest';
import type { PaginatedBacktestTaskList } from '../models/PaginatedBacktestTaskList';
import type { PaginatedEquityPointList } from '../models/PaginatedEquityPointList';
import type { PaginatedStrategyConfigListList } from '../models/PaginatedStrategyConfigListList';
import type { PaginatedTaskLogList } from '../models/PaginatedTaskLogList';
import type { PaginatedTradeList } from '../models/PaginatedTradeList';
import type { PaginatedTradingEventList } from '../models/PaginatedTradingEventList';
import type { PaginatedTradingTaskList } from '../models/PaginatedTradingTaskList';
import type { PatchedBacktestTaskRequest } from '../models/PatchedBacktestTaskRequest';
import type { PatchedTradingTaskRequest } from '../models/PatchedTradingTaskRequest';
import type { StrategyConfigCreateRequest } from '../models/StrategyConfigCreateRequest';
import type { StrategyConfigDetail } from '../models/StrategyConfigDetail';
import type { StrategyList } from '../models/StrategyList';
import type { TradingTask } from '../models/TradingTask';
import type { TradingTaskRequest } from '../models/TradingTaskRequest';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class TradingService {
  /**
   * List available strategies
   * Get all available trading strategies with their configuration schemas
   * @returns StrategyList
   * @throws ApiError
   */
  public static tradingStrategiesRetrieve(): CancelablePromise<StrategyList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/strategies/',
    });
  }
  /**
   * Get strategy defaults
   * Get default configuration parameters for a specific strategy
   * @param strategyId
   * @returns any
   * @throws ApiError
   */
  public static tradingStrategiesDefaultsRetrieve(
    strategyId: string
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/strategies/{strategy_id}/defaults/',
      path: {
        strategy_id: strategyId,
      },
    });
  }
  /**
   * List strategy configurations
   * List all strategy configurations for the authenticated user
   * @param page A page number within the paginated result set.
   * @param pageSize Number of results to return per page.
   * @returns PaginatedStrategyConfigListList
   * @throws ApiError
   */
  public static tradingStrategyConfigsList(
    page?: number,
    pageSize?: number
  ): CancelablePromise<PaginatedStrategyConfigListList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/strategy-configs/',
      query: {
        page: page,
        page_size: pageSize,
      },
    });
  }
  /**
   * Create strategy configuration
   * Create a new strategy configuration
   * @param requestBody
   * @returns StrategyConfigDetail
   * @throws ApiError
   */
  public static tradingStrategyConfigsCreate(
    requestBody: StrategyConfigCreateRequest
  ): CancelablePromise<StrategyConfigDetail> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/strategy-configs/',
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Get strategy configuration
   * Retrieve a specific strategy configuration
   * @param configId
   * @returns StrategyConfigDetail
   * @throws ApiError
   */
  public static tradingStrategyConfigsRetrieve(
    configId: number
  ): CancelablePromise<StrategyConfigDetail> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/strategy-configs/{config_id}/',
      path: {
        config_id: configId,
      },
    });
  }
  /**
   * Update strategy configuration
   * Update an existing strategy configuration
   * @param configId
   * @param requestBody
   * @returns StrategyConfigDetail
   * @throws ApiError
   */
  public static tradingStrategyConfigsUpdate(
    configId: number,
    requestBody: StrategyConfigCreateRequest
  ): CancelablePromise<StrategyConfigDetail> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/trading/strategy-configs/{config_id}/',
      path: {
        config_id: configId,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Delete strategy configuration
   * Delete a strategy configuration (fails if in use by active tasks)
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
   * ViewSet for BacktestTask operations with task-centric API.
   *
   * Provides CRUD operations and task lifecycle management including:
   * - submit: Submit task for execution
   * - stop: Stop running task
   * - pause: Pause running task
   * - restart: Restart task from beginning
   * - resume: Resume paused task
   * - logs: Retrieve task logs with pagination
   * - events: Retrieve task events
   * - trades: Retrieve trade history
   * - equity: Retrieve equity curve
   * @param ordering Which field to use when ordering the results.
   * @param page A page number within the paginated result set.
   * @param search A search term.
   * @returns PaginatedBacktestTaskList
   * @throws ApiError
   */
  public static tradingTasksBacktestList(
    ordering?: string,
    page?: number,
    search?: string
  ): CancelablePromise<PaginatedBacktestTaskList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/backtest/',
      query: {
        ordering: ordering,
        page: page,
        search: search,
      },
    });
  }
  /**
   * ViewSet for BacktestTask operations with task-centric API.
   *
   * Provides CRUD operations and task lifecycle management including:
   * - submit: Submit task for execution
   * - stop: Stop running task
   * - pause: Pause running task
   * - restart: Restart task from beginning
   * - resume: Resume paused task
   * - logs: Retrieve task logs with pagination
   * - events: Retrieve task events
   * - trades: Retrieve trade history
   * - equity: Retrieve equity curve
   * @param requestBody
   * @returns BacktestTask
   * @throws ApiError
   */
  public static tradingTasksBacktestCreate(
    requestBody: BacktestTaskRequest
  ): CancelablePromise<BacktestTask> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/tasks/backtest/',
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * ViewSet for BacktestTask operations with task-centric API.
   *
   * Provides CRUD operations and task lifecycle management including:
   * - submit: Submit task for execution
   * - stop: Stop running task
   * - pause: Pause running task
   * - restart: Restart task from beginning
   * - resume: Resume paused task
   * - logs: Retrieve task logs with pagination
   * - events: Retrieve task events
   * - trades: Retrieve trade history
   * - equity: Retrieve equity curve
   * @param id
   * @returns BacktestTask
   * @throws ApiError
   */
  public static tradingTasksBacktestRetrieve(
    id: string
  ): CancelablePromise<BacktestTask> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/backtest/{id}/',
      path: {
        id: id,
      },
    });
  }
  /**
   * ViewSet for BacktestTask operations with task-centric API.
   *
   * Provides CRUD operations and task lifecycle management including:
   * - submit: Submit task for execution
   * - stop: Stop running task
   * - pause: Pause running task
   * - restart: Restart task from beginning
   * - resume: Resume paused task
   * - logs: Retrieve task logs with pagination
   * - events: Retrieve task events
   * - trades: Retrieve trade history
   * - equity: Retrieve equity curve
   * @param id
   * @param requestBody
   * @returns BacktestTask
   * @throws ApiError
   */
  public static tradingTasksBacktestUpdate(
    id: string,
    requestBody: BacktestTaskRequest
  ): CancelablePromise<BacktestTask> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/trading/tasks/backtest/{id}/',
      path: {
        id: id,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * ViewSet for BacktestTask operations with task-centric API.
   *
   * Provides CRUD operations and task lifecycle management including:
   * - submit: Submit task for execution
   * - stop: Stop running task
   * - pause: Pause running task
   * - restart: Restart task from beginning
   * - resume: Resume paused task
   * - logs: Retrieve task logs with pagination
   * - events: Retrieve task events
   * - trades: Retrieve trade history
   * - equity: Retrieve equity curve
   * @param id
   * @param requestBody
   * @returns BacktestTask
   * @throws ApiError
   */
  public static tradingTasksBacktestPartialUpdate(
    id: string,
    requestBody?: PatchedBacktestTaskRequest
  ): CancelablePromise<BacktestTask> {
    return __request(OpenAPI, {
      method: 'PATCH',
      url: '/api/trading/tasks/backtest/{id}/',
      path: {
        id: id,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * ViewSet for BacktestTask operations with task-centric API.
   *
   * Provides CRUD operations and task lifecycle management including:
   * - submit: Submit task for execution
   * - stop: Stop running task
   * - pause: Pause running task
   * - restart: Restart task from beginning
   * - resume: Resume paused task
   * - logs: Retrieve task logs with pagination
   * - events: Retrieve task events
   * - trades: Retrieve trade history
   * - equity: Retrieve equity curve
   * @param id
   * @returns void
   * @throws ApiError
   */
  public static tradingTasksBacktestDestroy(
    id: string
  ): CancelablePromise<void> {
    return __request(OpenAPI, {
      method: 'DELETE',
      url: '/api/trading/tasks/backtest/{id}/',
      path: {
        id: id,
      },
    });
  }
  /**
   * Get task equity curve
   * Retrieve equity curve data from task execution state
   * @param id
   * @param ordering Which field to use when ordering the results.
   * @param page A page number within the paginated result set.
   * @param search A search term.
   * @returns PaginatedEquityPointList
   * @throws ApiError
   */
  public static tradingTasksBacktestEquitiesList(
    id: string,
    ordering?: string,
    page?: number,
    search?: string
  ): CancelablePromise<PaginatedEquityPointList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/backtest/{id}/equities/',
      path: {
        id: id,
      },
      query: {
        ordering: ordering,
        page: page,
        search: search,
      },
    });
  }
  /**
   * Get task events
   * Retrieve task events with filtering
   * @param id
   * @param eventType Filter by event type
   * @param limit Maximum number of events to return (default: 100)
   * @param ordering Which field to use when ordering the results.
   * @param page A page number within the paginated result set.
   * @param search A search term.
   * @param severity Filter by severity (info, warning, error)
   * @returns PaginatedTradingEventList
   * @throws ApiError
   */
  public static tradingTasksBacktestEventsList(
    id: string,
    eventType?: string,
    limit?: number,
    ordering?: string,
    page?: number,
    search?: string,
    severity?: string
  ): CancelablePromise<PaginatedTradingEventList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/backtest/{id}/events/',
      path: {
        id: id,
      },
      query: {
        event_type: eventType,
        limit: limit,
        ordering: ordering,
        page: page,
        search: search,
        severity: severity,
      },
    });
  }
  /**
   * Get task logs
   * Retrieve task execution logs with pagination and filtering
   * @param id
   * @param level Filter by log level (DEBUG, INFO, WARNING, ERROR)
   * @param limit Maximum number of logs to return (default: 100)
   * @param offset Number of logs to skip (default: 0)
   * @param ordering Which field to use when ordering the results.
   * @param page A page number within the paginated result set.
   * @param search A search term.
   * @returns PaginatedTaskLogList
   * @throws ApiError
   */
  public static tradingTasksBacktestLogsList(
    id: string,
    level?: string,
    limit?: number,
    offset?: number,
    ordering?: string,
    page?: number,
    search?: string
  ): CancelablePromise<PaginatedTaskLogList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/backtest/{id}/logs/',
      path: {
        id: id,
      },
      query: {
        level: level,
        limit: limit,
        offset: offset,
        ordering: ordering,
        page: page,
        search: search,
      },
    });
  }
  /**
   * Pause running task
   * Pause a running task, preserving execution state
   * @param id
   * @param requestBody
   * @returns BacktestTask
   * @throws ApiError
   */
  public static tradingTasksBacktestPauseCreate(
    id: string,
    requestBody: BacktestTaskRequest
  ): CancelablePromise<BacktestTask> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/tasks/backtest/{id}/pause/',
      path: {
        id: id,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Restart task from beginning
   * Restart a task from the beginning, clearing all execution data
   * @param id
   * @param requestBody
   * @returns BacktestTask
   * @throws ApiError
   */
  public static tradingTasksBacktestRestartCreate(
    id: string,
    requestBody: BacktestTaskRequest
  ): CancelablePromise<BacktestTask> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/tasks/backtest/{id}/restart/',
      path: {
        id: id,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Resume paused task
   * Resume a paused task, continuing execution from where it left off
   * @param id
   * @param requestBody
   * @returns BacktestTask
   * @throws ApiError
   */
  public static tradingTasksBacktestResumeCreate(
    id: string,
    requestBody: BacktestTaskRequest
  ): CancelablePromise<BacktestTask> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/tasks/backtest/{id}/resume/',
      path: {
        id: id,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Submit task for execution
   * Submit a pending task to Celery for execution. Only tasks in CREATED status can be submitted. Use restart or resume for STOPPED tasks.
   * @param id
   * @param requestBody
   * @returns BacktestTask
   * @throws ApiError
   */
  public static tradingTasksBacktestStartCreate(
    id: string,
    requestBody: BacktestTaskRequest
  ): CancelablePromise<BacktestTask> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/tasks/backtest/{id}/start/',
      path: {
        id: id,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Stop running task
   * Stop a currently running or paused task asynchronously
   * @param id
   * @param requestBody
   * @returns any
   * @throws ApiError
   */
  public static tradingTasksBacktestStopCreate(
    id: string,
    requestBody: BacktestTaskRequest
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/tasks/backtest/{id}/stop/',
      path: {
        id: id,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Get task trades
   * Retrieve trade history from task execution state
   * @param id
   * @param direction Filter by trade direction (buy/sell)
   * @param ordering Which field to use when ordering the results.
   * @param page A page number within the paginated result set.
   * @param search A search term.
   * @returns PaginatedTradeList
   * @throws ApiError
   */
  public static tradingTasksBacktestTradesList(
    id: string,
    direction?: string,
    ordering?: string,
    page?: number,
    search?: string
  ): CancelablePromise<PaginatedTradeList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/backtest/{id}/trades/',
      path: {
        id: id,
      },
      query: {
        direction: direction,
        ordering: ordering,
        page: page,
        search: search,
      },
    });
  }
  /**
   * ViewSet for TradingTask operations with task-centric API.
   *
   * Provides CRUD operations and task lifecycle management including:
   * - submit: Submit task for execution
   * - stop: Stop running task
   * - restart: Restart task from beginning
   * - resume: Resume cancelled task
   * - logs: Retrieve task logs with pagination
   * - events: Retrieve task events
   * - trades: Retrieve trade history
   * - equity: Retrieve equity curve
   * @param ordering Which field to use when ordering the results.
   * @param page A page number within the paginated result set.
   * @param search A search term.
   * @returns PaginatedTradingTaskList
   * @throws ApiError
   */
  public static tradingTasksTradingList(
    ordering?: string,
    page?: number,
    search?: string
  ): CancelablePromise<PaginatedTradingTaskList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/trading/',
      query: {
        ordering: ordering,
        page: page,
        search: search,
      },
    });
  }
  /**
   * ViewSet for TradingTask operations with task-centric API.
   *
   * Provides CRUD operations and task lifecycle management including:
   * - submit: Submit task for execution
   * - stop: Stop running task
   * - restart: Restart task from beginning
   * - resume: Resume cancelled task
   * - logs: Retrieve task logs with pagination
   * - events: Retrieve task events
   * - trades: Retrieve trade history
   * - equity: Retrieve equity curve
   * @param requestBody
   * @returns TradingTask
   * @throws ApiError
   */
  public static tradingTasksTradingCreate(
    requestBody: TradingTaskRequest
  ): CancelablePromise<TradingTask> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/tasks/trading/',
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * ViewSet for TradingTask operations with task-centric API.
   *
   * Provides CRUD operations and task lifecycle management including:
   * - submit: Submit task for execution
   * - stop: Stop running task
   * - restart: Restart task from beginning
   * - resume: Resume cancelled task
   * - logs: Retrieve task logs with pagination
   * - events: Retrieve task events
   * - trades: Retrieve trade history
   * - equity: Retrieve equity curve
   * @param id
   * @returns TradingTask
   * @throws ApiError
   */
  public static tradingTasksTradingRetrieve(
    id: string
  ): CancelablePromise<TradingTask> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/trading/{id}/',
      path: {
        id: id,
      },
    });
  }
  /**
   * ViewSet for TradingTask operations with task-centric API.
   *
   * Provides CRUD operations and task lifecycle management including:
   * - submit: Submit task for execution
   * - stop: Stop running task
   * - restart: Restart task from beginning
   * - resume: Resume cancelled task
   * - logs: Retrieve task logs with pagination
   * - events: Retrieve task events
   * - trades: Retrieve trade history
   * - equity: Retrieve equity curve
   * @param id
   * @param requestBody
   * @returns TradingTask
   * @throws ApiError
   */
  public static tradingTasksTradingUpdate(
    id: string,
    requestBody: TradingTaskRequest
  ): CancelablePromise<TradingTask> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/trading/tasks/trading/{id}/',
      path: {
        id: id,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * ViewSet for TradingTask operations with task-centric API.
   *
   * Provides CRUD operations and task lifecycle management including:
   * - submit: Submit task for execution
   * - stop: Stop running task
   * - restart: Restart task from beginning
   * - resume: Resume cancelled task
   * - logs: Retrieve task logs with pagination
   * - events: Retrieve task events
   * - trades: Retrieve trade history
   * - equity: Retrieve equity curve
   * @param id
   * @param requestBody
   * @returns TradingTask
   * @throws ApiError
   */
  public static tradingTasksTradingPartialUpdate(
    id: string,
    requestBody?: PatchedTradingTaskRequest
  ): CancelablePromise<TradingTask> {
    return __request(OpenAPI, {
      method: 'PATCH',
      url: '/api/trading/tasks/trading/{id}/',
      path: {
        id: id,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * ViewSet for TradingTask operations with task-centric API.
   *
   * Provides CRUD operations and task lifecycle management including:
   * - submit: Submit task for execution
   * - stop: Stop running task
   * - restart: Restart task from beginning
   * - resume: Resume cancelled task
   * - logs: Retrieve task logs with pagination
   * - events: Retrieve task events
   * - trades: Retrieve trade history
   * - equity: Retrieve equity curve
   * @param id
   * @returns void
   * @throws ApiError
   */
  public static tradingTasksTradingDestroy(
    id: string
  ): CancelablePromise<void> {
    return __request(OpenAPI, {
      method: 'DELETE',
      url: '/api/trading/tasks/trading/{id}/',
      path: {
        id: id,
      },
    });
  }
  /**
   * Get task equity curve
   * Retrieve equity curve data from task execution state
   * @param id
   * @param ordering Which field to use when ordering the results.
   * @param page A page number within the paginated result set.
   * @param search A search term.
   * @returns PaginatedEquityPointList
   * @throws ApiError
   */
  public static tradingTasksTradingEquitiesList(
    id: string,
    ordering?: string,
    page?: number,
    search?: string
  ): CancelablePromise<PaginatedEquityPointList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/trading/{id}/equities/',
      path: {
        id: id,
      },
      query: {
        ordering: ordering,
        page: page,
        search: search,
      },
    });
  }
  /**
   * Get task events
   * Retrieve task events with filtering
   * @param id
   * @param eventType Filter by event type
   * @param limit Maximum number of events to return (default: 100)
   * @param ordering Which field to use when ordering the results.
   * @param page A page number within the paginated result set.
   * @param search A search term.
   * @param severity Filter by severity (info, warning, error)
   * @returns PaginatedTradingEventList
   * @throws ApiError
   */
  public static tradingTasksTradingEventsList(
    id: string,
    eventType?: string,
    limit?: number,
    ordering?: string,
    page?: number,
    search?: string,
    severity?: string
  ): CancelablePromise<PaginatedTradingEventList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/trading/{id}/events/',
      path: {
        id: id,
      },
      query: {
        event_type: eventType,
        limit: limit,
        ordering: ordering,
        page: page,
        search: search,
        severity: severity,
      },
    });
  }
  /**
   * Get task logs
   * Retrieve task execution logs with pagination and filtering
   * @param id
   * @param level Filter by log level (DEBUG, INFO, WARNING, ERROR)
   * @param limit Maximum number of logs to return (default: 100)
   * @param offset Number of logs to skip (default: 0)
   * @param ordering Which field to use when ordering the results.
   * @param page A page number within the paginated result set.
   * @param search A search term.
   * @returns PaginatedTaskLogList
   * @throws ApiError
   */
  public static tradingTasksTradingLogsList(
    id: string,
    level?: string,
    limit?: number,
    offset?: number,
    ordering?: string,
    page?: number,
    search?: string
  ): CancelablePromise<PaginatedTaskLogList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/trading/{id}/logs/',
      path: {
        id: id,
      },
      query: {
        level: level,
        limit: limit,
        offset: offset,
        ordering: ordering,
        page: page,
        search: search,
      },
    });
  }
  /**
   * Restart task from beginning
   * Restart a task from the beginning, clearing all execution data
   * @param id
   * @param requestBody
   * @returns TradingTask
   * @throws ApiError
   */
  public static tradingTasksTradingRestartCreate(
    id: string,
    requestBody: TradingTaskRequest
  ): CancelablePromise<TradingTask> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/tasks/trading/{id}/restart/',
      path: {
        id: id,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Resume cancelled task
   * Resume a cancelled task, preserving execution context
   * @param id
   * @param requestBody
   * @returns TradingTask
   * @throws ApiError
   */
  public static tradingTasksTradingResumeCreate(
    id: string,
    requestBody: TradingTaskRequest
  ): CancelablePromise<TradingTask> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/tasks/trading/{id}/resume/',
      path: {
        id: id,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Submit task for execution
   * Submit a pending task to Celery for execution. Only tasks in CREATED status can be submitted. Use restart or resume for STOPPED tasks.
   * @param id
   * @param requestBody
   * @returns TradingTask
   * @throws ApiError
   */
  public static tradingTasksTradingStartCreate(
    id: string,
    requestBody: TradingTaskRequest
  ): CancelablePromise<TradingTask> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/tasks/trading/{id}/start/',
      path: {
        id: id,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Stop running task
   * Stop a currently running task asynchronously (graceful stop for trading tasks)
   * @param id
   * @param requestBody
   * @returns any
   * @throws ApiError
   */
  public static tradingTasksTradingStopCreate(
    id: string,
    requestBody: TradingTaskRequest
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/trading/tasks/trading/{id}/stop/',
      path: {
        id: id,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * Get task trades
   * Retrieve trade history from task execution state
   * @param id
   * @param direction Filter by trade direction (buy/sell)
   * @param ordering Which field to use when ordering the results.
   * @param page A page number within the paginated result set.
   * @param search A search term.
   * @returns PaginatedTradeList
   * @throws ApiError
   */
  public static tradingTasksTradingTradesList(
    id: string,
    direction?: string,
    ordering?: string,
    page?: number,
    search?: string
  ): CancelablePromise<PaginatedTradeList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/trading/{id}/trades/',
      path: {
        id: id,
      },
      query: {
        direction: direction,
        ordering: ordering,
        page: page,
        search: search,
      },
    });
  }
}
