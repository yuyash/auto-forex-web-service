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

import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { apiConfig, resolveToken } from '../api/apiConfig';
import { TaskType } from '../types/common';
import { handleAuthErrorStatus } from '../utils/authEvents';

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
  refetch: () => Promise<void>;
}

const INITIAL_SUMMARY: TaskSummary = {
  timestamp: null,
  pnl: { realized: 0, unrealized: 0 },
  counts: { totalTrades: 0, openPositions: 0, closedPositions: 0 },
  execution: { currentBalance: null, ticksProcessed: 0 },
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
  celeryTaskId?: string,
  options: UseTaskSummaryOptions = {}
): UseTaskSummaryResult {
  const { polling = false, interval = 2000 } = options;

  const [data, setData] = useState<TaskSummary>(INITIAL_SUMMARY);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const timerRef = useRef<number | null>(null);

  const fetchSummary = useCallback(async () => {
    if (!taskId) {
      setIsLoading(false);
      return;
    }
    try {
      setIsLoading(true);
      setError(null);

      const prefix =
        taskType === TaskType.BACKTEST
          ? '/api/trading/tasks/backtest'
          : '/api/trading/tasks/trading';

      const url = `${apiConfig.BASE}${prefix}/${taskId}/summary/`;

      const headers: Record<string, string> = {
        Accept: 'application/json',
      };
      const token = await resolveToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const params: Record<string, string> = {};
      if (celeryTaskId) params.celery_task_id = celeryTaskId;

      const response = await axios.get(url, {
        params,
        headers,
        withCredentials: apiConfig.WITH_CREDENTIALS,
      });

      const d = response.data;
      setData({
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
      });
    } catch (err) {
      if (axios.isAxiosError(err) && err.response) {
        handleAuthErrorStatus(err.response.status, {
          source: 'http',
          status: err.response.status,
          context: 'task_summary',
        });
      }
      setError(
        new Error(
          err instanceof Error ? err.message : 'Failed to load task summary'
        )
      );
    } finally {
      setIsLoading(false);
    }
  }, [taskId, taskType, celeryTaskId]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  useEffect(() => {
    if (!polling || !taskId) return;

    timerRef.current = window.setInterval(() => {
      fetchSummary();
    }, interval);

    return () => {
      if (timerRef.current !== null) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [polling, interval, taskId, fetchSummary]);

  return {
    summary: data,
    isLoading,
    error,
    refetch: fetchSummary,
  };
}
