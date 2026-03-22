/**
 * Hook for fetching task summary from the backend API.
 *
 * Returns comprehensive task summary grouped into logical sections:
 * - pnl: realized/unrealized PnL
 * - counts: trade/position counts
 * - execution: balance, ticks processed
 * - tick: last tick prices (bid, ask, mid) with timestamp
 * - task: status, timing, progress
 *
 * Supports optional polling for real-time updates.
 */

import { useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { queryClient, queryKeys } from '../config/reactQuery';
import { useSequentialPolling } from './useSequentialPolling';
import { TaskType } from '../types/common';
import { handleAuthErrorStatus } from '../utils/authEvents';
import {
  fetchTaskResourceObject,
  isApiErrorWithStatus,
} from '../services/api/taskResources';

export interface TickInfo {
  timestamp: string | null;
  bid: number | null;
  ask: number | null;
  mid: number | null;
}

export interface PnlInfo {
  realized: number;
  unrealized: number;
}

export interface CountsInfo {
  totalTrades: number;
  openPositions: number;
  closedPositions: number;
}

export interface ExecutionInfo {
  currentBalance: number | null;
  ticksProcessed: number;
  accountCurrency: string | null;
  currentBalanceDisplay: number | null;
  displayCurrency: string | null;
}

export interface TaskInfo {
  status: string;
  startedAt: string | null;
  completedAt: string | null;
  errorMessage: string | null;
  progress: number;
}

export interface TaskSummary {
  timestamp: string | null;
  pnl: PnlInfo;
  counts: CountsInfo;
  execution: ExecutionInfo;
  tick: TickInfo;
  task: TaskInfo;
}

export interface UseTaskSummaryOptions {
  polling?: boolean;
  interval?: number;
}

export interface UseTaskSummaryResult {
  summary: TaskSummary;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

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
  };
  execution?: {
    current_balance?: string | number | null;
    ticks_processed?: number;
    account_currency?: string | null;
    current_balance_display?: string | number | null;
    display_currency?: string | null;
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
    progress?: number;
  };
}

const INITIAL_SUMMARY: TaskSummary = {
  timestamp: null,
  pnl: { realized: 0, unrealized: 0 },
  counts: { totalTrades: 0, openPositions: 0, closedPositions: 0 },
  execution: {
    currentBalance: null,
    ticksProcessed: 0,
    accountCurrency: null,
    currentBalanceDisplay: null,
    displayCurrency: null,
  },
  tick: { timestamp: null, bid: null, ask: null, mid: null },
  task: {
    status: '',
    startedAt: null,
    completedAt: null,
    errorMessage: null,
    progress: 0,
  },
};

export function useTaskSummary(
  taskId: string,
  taskType: TaskType,
  executionRunId?: string,
  options: UseTaskSummaryOptions = {}
): UseTaskSummaryResult {
  const { polling = false, interval = 10_000 } = options;

  const fetchSummary = useCallback(async () => {
    if (!taskId) {
      return INITIAL_SUMMARY;
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
          realized: parseFloat(d.pnl?.realized) || 0,
          unrealized: parseFloat(d.pnl?.unrealized) || 0,
        },
        counts: {
          totalTrades: d.counts?.total_trades ?? 0,
          openPositions: d.counts?.open_positions ?? 0,
          closedPositions: d.counts?.closed_positions ?? 0,
        },
        execution: {
          currentBalance:
            d.execution?.current_balance != null
              ? parseFloat(d.execution.current_balance)
              : null,
          ticksProcessed: d.execution?.ticks_processed ?? 0,
          accountCurrency: d.execution?.account_currency ?? null,
          currentBalanceDisplay:
            d.execution?.current_balance_display != null
              ? parseFloat(d.execution.current_balance_display)
              : null,
          displayCurrency: d.execution?.display_currency ?? null,
        },
        tick: {
          timestamp: d.tick?.timestamp ?? null,
          bid: d.tick?.bid != null ? parseFloat(d.tick.bid) : null,
          ask: d.tick?.ask != null ? parseFloat(d.tick.ask) : null,
          mid: d.tick?.mid != null ? parseFloat(d.tick.mid) : null,
        },
        task: {
          status: d.task?.status ?? '',
          startedAt: d.task?.started_at ?? null,
          completedAt: d.task?.completed_at ?? null,
          errorMessage: d.task?.error_message ?? null,
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
  }, [taskId, taskType, executionRunId]);

  const query = useQuery({
    queryKey: queryKeys.taskResources.summary(taskType, taskId, executionRunId),
    queryFn: fetchSummary,
    enabled: Boolean(taskId),
  });

  useSequentialPolling(
    () => {
      if (!query.isFetching) {
        return queryClient.invalidateQueries({
          queryKey: queryKeys.taskResources.summary(
            taskType,
            taskId,
            executionRunId
          ),
        });
      }
      return Promise.resolve();
    },
    {
      enabled: polling && Boolean(taskId),
      intervalMs: interval,
    }
  );

  return {
    summary: query.data ?? INITIAL_SUMMARY,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refetch: () =>
      queryClient.invalidateQueries({
        queryKey: queryKeys.taskResources.summary(
          taskType,
          taskId,
          executionRunId
        ),
      }),
  };
}
