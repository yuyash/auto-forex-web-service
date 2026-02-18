/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BacktestTask } from '../models/BacktestTask';
import type { BacktestTaskCreate } from '../models/BacktestTaskCreate';
import type { BacktestTaskCreateRequest } from '../models/BacktestTaskCreateRequest';
import type { BacktestTaskRequest } from '../models/BacktestTaskRequest';
import type { PaginatedBacktestTaskList } from '../models/PaginatedBacktestTaskList';
import type { PaginatedStrategyConfigListList } from '../models/PaginatedStrategyConfigListList';
import type { PaginatedTaskLogList } from '../models/PaginatedTaskLogList';
import type { PaginatedTradeList } from '../models/PaginatedTradeList';
import type { PaginatedTradingEventList } from '../models/PaginatedTradingEventList';
import type { PaginatedTradingTaskList } from '../models/PaginatedTradingTaskList';
import type { PatchedBacktestTaskCreateRequest } from '../models/PatchedBacktestTaskCreateRequest';
import type { PatchedTradingTaskCreateRequest } from '../models/PatchedTradingTaskCreateRequest';
import type { StrategyConfigCreateRequest } from '../models/StrategyConfigCreateRequest';
import type { StrategyConfigDetail } from '../models/StrategyConfigDetail';
import type { StrategyList } from '../models/StrategyList';
import type { TradingTask } from '../models/TradingTask';
import type { TradingTaskCreate } from '../models/TradingTaskCreate';
import type { TradingTaskCreateRequest } from '../models/TradingTaskCreateRequest';
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
   * @param configId Strategy configuration UUID
   * @returns StrategyConfigDetail
   * @throws ApiError
   */
  public static tradingStrategyConfigsRetrieve(
    configId: string
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
   * @param configId Strategy configuration UUID
   * @param requestBody
   * @returns StrategyConfigDetail
   * @throws ApiError
   */
  public static tradingStrategyConfigsUpdate(
    configId: string,
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
   * @param configId Strategy configuration UUID
   * @returns void
   * @throws ApiError
   */
  public static tradingStrategyConfigsDestroy(
    configId: string
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
   * @param configId Filter by configuration ID
   * @param ordering Ordering field (e.g. -created_at)
   * @param page Page number
   * @param pageSize Number of results per page
   * @param search Search in name or description
   * @param status Filter by task status
   * @returns PaginatedBacktestTaskList
   * @throws ApiError
   */
  public static tradingTasksBacktestList(
    configId?: string,
    ordering?: string,
    page?: number,
    pageSize?: number,
    search?: string,
    status?: string
  ): CancelablePromise<PaginatedBacktestTaskList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/backtest/',
      query: {
        config_id: configId,
        ordering: ordering,
        page: page,
        page_size: pageSize,
        search: search,
        status: status,
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
   * @param requestBody
   * @returns BacktestTaskCreate
   * @throws ApiError
   */
  public static tradingTasksBacktestCreate(
    requestBody: BacktestTaskCreateRequest
  ): CancelablePromise<BacktestTaskCreate> {
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
   * @param id
   * @param requestBody
   * @returns BacktestTaskCreate
   * @throws ApiError
   */
  public static tradingTasksBacktestUpdate(
    id: string,
    requestBody: BacktestTaskCreateRequest
  ): CancelablePromise<BacktestTaskCreate> {
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
   * @param id
   * @param requestBody
   * @returns BacktestTaskCreate
   * @throws ApiError
   */
  public static tradingTasksBacktestPartialUpdate(
    id: string,
    requestBody?: PatchedBacktestTaskCreateRequest
  ): CancelablePromise<BacktestTaskCreate> {
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
   * Get task events
   * Get task events with pagination and filtering.
   * @param id
   * @param celeryTaskId Filter by celery task ID
   * @param eventType Filter by event type
   * @param ordering Which field to use when ordering the results.
   * @param page Page number
   * @param pageSize Number of results per page (default: 100, max: 1000)
   * @param search A search term.
   * @param severity Filter by severity
   * @returns PaginatedTradingEventList
   * @throws ApiError
   */
  public static tradingTasksBacktestEventsList(
    id: string,
    celeryTaskId?: string,
    eventType?: string,
    ordering?: string,
    page?: number,
    pageSize?: number,
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
        celery_task_id: celeryTaskId,
        event_type: eventType,
        ordering: ordering,
        page: page,
        page_size: pageSize,
        search: search,
        severity: severity,
      },
    });
  }
  /**
   * Get task logs
   * Get task logs with pagination and filtering.
   * @param id
   * @param celeryTaskId Filter by celery task ID
   * @param level Filter by log level
   * @param ordering Which field to use when ordering the results.
   * @param page Page number
   * @param pageSize Number of results per page (default: 100, max: 1000)
   * @param search A search term.
   * @returns PaginatedTaskLogList
   * @throws ApiError
   */
  public static tradingTasksBacktestLogsList(
    id: string,
    celeryTaskId?: string,
    level?: string,
    ordering?: string,
    page?: number,
    pageSize?: number,
    search?: string
  ): CancelablePromise<PaginatedTaskLogList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/backtest/{id}/logs/',
      path: {
        id: id,
      },
      query: {
        celery_task_id: celeryTaskId,
        level: level,
        ordering: ordering,
        page: page,
        page_size: pageSize,
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
   * Get task trades with pagination.
   * @param id
   * @param celeryTaskId Filter by celery task ID
   * @param direction Filter by direction (buy/sell)
   * @param ordering Which field to use when ordering the results.
   * @param page Page number
   * @param pageSize Number of results per page (default: 100, max: 1000)
   * @param search A search term.
   * @returns PaginatedTradeList
   * @throws ApiError
   */
  public static tradingTasksBacktestTradesList(
    id: string,
    celeryTaskId?: string,
    direction?: string,
    ordering?: string,
    page?: number,
    pageSize?: number,
    search?: string
  ): CancelablePromise<PaginatedTradeList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/backtest/{id}/trades/',
      path: {
        id: id,
      },
      query: {
        celery_task_id: celeryTaskId,
        direction: direction,
        ordering: ordering,
        page: page,
        page_size: pageSize,
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
   * @param accountId Filter by OANDA account ID
   * @param configId Filter by configuration ID
   * @param ordering Ordering field (e.g. -created_at)
   * @param page Page number
   * @param pageSize Number of results per page
   * @param search Search in name or description
   * @param status Filter by task status
   * @returns PaginatedTradingTaskList
   * @throws ApiError
   */
  public static tradingTasksTradingList(
    accountId?: number,
    configId?: string,
    ordering?: string,
    page?: number,
    pageSize?: number,
    search?: string,
    status?: string
  ): CancelablePromise<PaginatedTradingTaskList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/trading/',
      query: {
        account_id: accountId,
        config_id: configId,
        ordering: ordering,
        page: page,
        page_size: pageSize,
        search: search,
        status: status,
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
   * @param requestBody
   * @returns TradingTaskCreate
   * @throws ApiError
   */
  public static tradingTasksTradingCreate(
    requestBody?: TradingTaskCreateRequest
  ): CancelablePromise<TradingTaskCreate> {
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
   * @param id
   * @param requestBody
   * @returns TradingTaskCreate
   * @throws ApiError
   */
  public static tradingTasksTradingUpdate(
    id: string,
    requestBody?: TradingTaskCreateRequest
  ): CancelablePromise<TradingTaskCreate> {
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
   * @param id
   * @param requestBody
   * @returns TradingTaskCreate
   * @throws ApiError
   */
  public static tradingTasksTradingPartialUpdate(
    id: string,
    requestBody?: PatchedTradingTaskCreateRequest
  ): CancelablePromise<TradingTaskCreate> {
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
   * Get task events
   * Get task events with pagination and filtering.
   * @param id
   * @param celeryTaskId Filter by celery task ID
   * @param eventType Filter by event type
   * @param ordering Which field to use when ordering the results.
   * @param page Page number
   * @param pageSize Number of results per page (default: 100, max: 1000)
   * @param search A search term.
   * @param severity Filter by severity
   * @returns PaginatedTradingEventList
   * @throws ApiError
   */
  public static tradingTasksTradingEventsList(
    id: string,
    celeryTaskId?: string,
    eventType?: string,
    ordering?: string,
    page?: number,
    pageSize?: number,
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
        celery_task_id: celeryTaskId,
        event_type: eventType,
        ordering: ordering,
        page: page,
        page_size: pageSize,
        search: search,
        severity: severity,
      },
    });
  }
  /**
   * Get task logs
   * Get task logs with pagination and filtering.
   * @param id
   * @param celeryTaskId Filter by celery task ID
   * @param level Filter by log level
   * @param ordering Which field to use when ordering the results.
   * @param page Page number
   * @param pageSize Number of results per page (default: 100, max: 1000)
   * @param search A search term.
   * @returns PaginatedTaskLogList
   * @throws ApiError
   */
  public static tradingTasksTradingLogsList(
    id: string,
    celeryTaskId?: string,
    level?: string,
    ordering?: string,
    page?: number,
    pageSize?: number,
    search?: string
  ): CancelablePromise<PaginatedTaskLogList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/trading/{id}/logs/',
      path: {
        id: id,
      },
      query: {
        celery_task_id: celeryTaskId,
        level: level,
        ordering: ordering,
        page: page,
        page_size: pageSize,
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
   * Get task trades with pagination.
   * @param id
   * @param celeryTaskId Filter by celery task ID
   * @param direction Filter by direction (buy/sell)
   * @param ordering Which field to use when ordering the results.
   * @param page Page number
   * @param pageSize Number of results per page (default: 100, max: 1000)
   * @param search A search term.
   * @returns PaginatedTradeList
   * @throws ApiError
   */
  public static tradingTasksTradingTradesList(
    id: string,
    celeryTaskId?: string,
    direction?: string,
    ordering?: string,
    page?: number,
    pageSize?: number,
    search?: string
  ): CancelablePromise<PaginatedTradeList> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/tasks/trading/{id}/trades/',
      path: {
        id: id,
      },
      query: {
        celery_task_id: celeryTaskId,
        direction: direction,
        ordering: ordering,
        page: page,
        page_size: pageSize,
        search: search,
      },
    });
  }
}
