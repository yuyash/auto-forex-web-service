import type { UseQueryOptions } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
import { backtestTasksApi, tradingTasksApi } from '../services/api';
import {
  fetchTaskResourceObject,
  isApiErrorWithStatus,
} from '../services/api/taskResources';
import type {
  BacktestTask,
  BacktestTaskListParams,
  PaginatedResponse,
  TaskExecution,
  TradingTask,
  TradingTaskListParams,
} from '../types';
import { TaskType } from '../types/common';
import type { StrategyCyclesResponse } from '../types/strategyVisualization';
import { handleAuthErrorStatus } from '../utils/authEvents';
import type { TaskSummary } from './useTaskSummary';

interface TaskSummaryResponse {
  timestamp?: string | null;
  pnl?: {
    realized?: string | number | null;
    unrealized?: string | number | null;
  };
  counts?: {
    total_trades?: number;
    open_positions?: number;
    closed_positions?: number;
    open_long_units?: number;
    open_short_units?: number;
    winning_trades?: number;
    losing_trades?: number;
  };
  execution?: {
    current_balance?: string | number | null;
    ticks_processed?: number;
    account_currency?: string | null;
    current_balance_display?: string | number | null;
    display_currency?: string | null;
    margin_ratio?: string | number | null;
    current_atr?: string | number | null;
  };
  tick?: {
    timestamp?: string | null;
    bid?: string | number | null;
    ask?: string | number | null;
    mid?: string | number | null;
  };
  task?: {
    status?: string;
    started_at?: string | null;
    completed_at?: string | null;
    error_message?: string | null;
    stop_reason?: string | null;
    progress?: number;
  };
}

type TaskListParams = BacktestTaskListParams | TradingTaskListParams;
type TaskEntity = BacktestTask | TradingTask;

export function shouldPollTaskStatus(status: string | undefined): boolean {
  return (
    status === 'starting' ||
    status === 'running' ||
    status === 'paused' ||
    status === 'idle' ||
    status === 'draining' ||
    status === 'stopping'
  );
}

export function shouldEnableRealtimeTaskUpdates(
  status: string | undefined
): boolean {
  return (
    status === 'starting' ||
    status === 'running' ||
    status === 'paused' ||
    status === 'idle' ||
    status === 'draining' ||
    status === 'stopping'
  );
}

export function createTaskListQuery<TTask extends TaskEntity>(
  taskType: TaskType,
  params?: TaskListParams
): UseQueryOptions<PaginatedResponse<TTask>> {
  return {
    queryKey:
      taskType === TaskType.BACKTEST
        ? queryKeys.backtestTasks.list(params as Record<string, unknown>)
        : queryKeys.tradingTasks.list(params as Record<string, unknown>),
    queryFn: () =>
      taskType === TaskType.BACKTEST
        ? (backtestTasksApi.list(params as BacktestTaskListParams) as Promise<
            PaginatedResponse<TTask>
          >)
        : (tradingTasksApi.list(params as TradingTaskListParams) as Promise<
            PaginatedResponse<TTask>
          >),
    enabled: params !== undefined,
  };
}

export function createTaskDetailQuery<TTask extends TaskEntity>(
  taskType: TaskType,
  id: string | undefined,
  options?: {
    enabled?: boolean;
    enablePolling?: boolean;
    pollingInterval?: number;
  }
): UseQueryOptions<TTask> {
  return {
    queryKey:
      taskType === TaskType.BACKTEST
        ? id
          ? queryKeys.backtestTasks.detail(id)
          : ['backtest-task', 'empty']
        : id
          ? queryKeys.tradingTasks.detail(id)
          : ['trading-task', 'empty'],
    queryFn: () =>
      taskType === TaskType.BACKTEST
        ? (backtestTasksApi.get(id!) as Promise<TTask>)
        : (tradingTasksApi.get(id!) as Promise<TTask>),
    enabled: Boolean(id) && options?.enabled !== false,
  };
}

export function createTaskSummaryQuery(
  taskId: string,
  taskType: TaskType,
  executionRunId: string | undefined,
  fallback: TaskSummary
): UseQueryOptions<TaskSummary> {
  return {
    queryKey: queryKeys.taskResources.summary(taskType, taskId, executionRunId),
    enabled: Boolean(taskId),
    queryFn: async () => {
      if (!taskId) {
        return fallback;
      }

      try {
        const d = await fetchTaskResourceObject<TaskSummaryResponse>(
          taskType,
          taskId,
          'summary',
          executionRunId != null
            ? { execution_id: String(executionRunId) }
            : undefined
        );

        return {
          timestamp: d.timestamp ?? null,
          pnl: {
            realized: parseFloat(String(d.pnl?.realized ?? 0)) || 0,
            unrealized: parseFloat(String(d.pnl?.unrealized ?? 0)) || 0,
          },
          counts: {
            totalTrades: d.counts?.total_trades ?? 0,
            openPositions: d.counts?.open_positions ?? 0,
            closedPositions: d.counts?.closed_positions ?? 0,
            openLongUnits: d.counts?.open_long_units ?? 0,
            openShortUnits: d.counts?.open_short_units ?? 0,
            winningTrades: d.counts?.winning_trades ?? 0,
            losingTrades: d.counts?.losing_trades ?? 0,
          },
          execution: {
            currentBalance:
              d.execution?.current_balance != null
                ? parseFloat(String(d.execution.current_balance))
                : null,
            ticksProcessed: d.execution?.ticks_processed ?? 0,
            accountCurrency: d.execution?.account_currency ?? null,
            currentBalanceDisplay:
              d.execution?.current_balance_display != null
                ? parseFloat(String(d.execution.current_balance_display))
                : null,
            displayCurrency: d.execution?.display_currency ?? null,
            marginRatio:
              d.execution?.margin_ratio != null
                ? parseFloat(String(d.execution.margin_ratio))
                : null,
            currentAtr:
              d.execution?.current_atr != null
                ? parseFloat(String(d.execution.current_atr))
                : null,
          },
          tick: {
            timestamp: d.tick?.timestamp ?? null,
            bid: d.tick?.bid != null ? parseFloat(String(d.tick.bid)) : null,
            ask: d.tick?.ask != null ? parseFloat(String(d.tick.ask)) : null,
            mid: d.tick?.mid != null ? parseFloat(String(d.tick.mid)) : null,
          },
          task: {
            status: d.task?.status ?? '',
            startedAt: d.task?.started_at ?? null,
            completedAt: d.task?.completed_at ?? null,
            errorMessage: d.task?.error_message ?? null,
            stopReason: d.task?.stop_reason ?? null,
            progress: d.task?.progress ?? 0,
          },
        } satisfies TaskSummary;
      } catch (err) {
        if (isApiErrorWithStatus(err)) {
          handleAuthErrorStatus(err.status, {
            source: 'http',
            status: err.status,
            context: 'task_summary',
          });
        }
        throw new Error(
          err instanceof Error ? err.message : 'Failed to load task summary'
        );
      }
    },
  };
}

export function createTaskExecutionsQuery(
  taskId: string,
  taskType: TaskType,
  params?: { page?: number; page_size?: number; include_metrics?: boolean }
): UseQueryOptions<PaginatedResponse<TaskExecution>> {
  return {
    queryKey:
      taskType === TaskType.BACKTEST
        ? queryKeys.backtestTasks.executions(taskId, params)
        : queryKeys.tradingTasks.executions(taskId, params),
    queryFn: async () => {
      const fetchParams =
        params?.page || params?.page_size
          ? {
              page: params.page,
              page_size: params.page_size,
              include_metrics: params.include_metrics,
            }
          : undefined;
      return taskType === TaskType.BACKTEST
        ? backtestTasksApi.getExecutions(taskId, fetchParams)
        : tradingTasksApi.getExecutions(taskId, fetchParams);
    },
    staleTime: 2000,
    refetchOnWindowFocus: true,
  };
}

export function createTaskExecutionQuery(
  taskId: string,
  executionId: string,
  taskType: TaskType
): UseQueryOptions<TaskExecution> {
  return {
    queryKey:
      taskType === TaskType.BACKTEST
        ? queryKeys.backtestTasks.execution(taskId, executionId)
        : queryKeys.tradingTasks.execution(taskId, executionId),
    queryFn: () =>
      taskType === TaskType.BACKTEST
        ? backtestTasksApi.getExecution(taskId, executionId)
        : tradingTasksApi.getExecution(taskId, executionId),
    staleTime: 10000,
  };
}

export function createTaskStrategyEventsQuery(
  taskId: string | number,
  taskType: TaskType,
  executionRunId?: string,
  cycleId?: string,
  options?: { enabled?: boolean }
): UseQueryOptions<StrategyCyclesResponse | null> {
  return {
    queryKey: queryKeys.taskResources.strategyEvents(
      taskType,
      String(taskId),
      executionRunId,
      cycleId
    ),
    enabled: Boolean(taskId) && options?.enabled !== false,
    staleTime: 0,
    refetchOnMount: 'always',
    queryFn: async () => {
      if (!taskId) {
        return null;
      }
      try {
        return await fetchTaskResourceObject<StrategyCyclesResponse>(
          taskType,
          taskId,
          'strategy-events',
          {
            ...(executionRunId ? { execution_id: executionRunId } : {}),
            ...(cycleId ? { cycle_id: cycleId } : {}),
          }
        );
      } catch (err) {
        if (isApiErrorWithStatus(err)) {
          handleAuthErrorStatus(err.status, {
            source: 'http',
            status: err.status,
            context: 'task_strategy_events',
          });
        }
        throw new Error(
          err instanceof Error ? err.message : 'Failed to load strategy cycles'
        );
      }
    },
  };
}
