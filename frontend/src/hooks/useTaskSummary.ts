/**
 * Hook for fetching task summary from the backend API.
 *
 * Returns comprehensive task summary including PnL, trade/position counts,
 * execution state, tick info, and task status information.
 * Supports optional polling for real-time updates.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { apiConfig, resolveToken } from '../api/apiConfig';
import { TaskType } from '../types/common';
import { handleAuthErrorStatus } from '../utils/authEvents';

export interface TaskSummary {
  // PnL
  realizedPnl: number;
  unrealizedPnl: number;
  // Counts
  totalTrades: number;
  openPositionCount: number;
  closedPositionCount: number;
  // Execution state
  currentBalance: number | null;
  ticksProcessed: number;
  lastTickTime: string | null;
  lastTickPrice: number | null;
  // Task info
  status: string;
  startedAt: string | null;
  completedAt: string | null;
  errorMessage: string | null;
  // Progress (backtest: 0-100, trading: always 0)
  progress: number;
}

export interface UseTaskSummaryOptions {
  /** Enable periodic polling (default: false) */
  polling?: boolean;
  /** Polling interval in ms (default: 2000) */
  interval?: number;
}

export interface UseTaskSummaryResult extends TaskSummary {
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  /** Convenience accessor matching the old currentTick shape */
  currentTick: { timestamp: string; price: string | null } | null;
}

const INITIAL_SUMMARY: TaskSummary = {
  realizedPnl: 0,
  unrealizedPnl: 0,
  totalTrades: 0,
  openPositionCount: 0,
  closedPositionCount: 0,
  currentBalance: null,
  ticksProcessed: 0,
  lastTickTime: null,
  lastTickPrice: null,
  status: '',
  startedAt: null,
  completedAt: null,
  errorMessage: null,
  progress: 0,
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
        realizedPnl: parseFloat(d.realized_pnl) || 0,
        unrealizedPnl: parseFloat(d.unrealized_pnl) || 0,
        totalTrades: d.total_trades ?? 0,
        openPositionCount: d.open_position_count ?? 0,
        closedPositionCount: d.closed_position_count ?? 0,
        currentBalance:
          d.current_balance != null ? parseFloat(d.current_balance) : null,
        ticksProcessed: d.ticks_processed ?? 0,
        lastTickTime: d.last_tick_time ?? null,
        lastTickPrice:
          d.last_tick_price != null ? parseFloat(d.last_tick_price) : null,
        status: d.status ?? '',
        startedAt: d.started_at ?? null,
        completedAt: d.completed_at ?? null,
        errorMessage: d.error_message ?? null,
        progress: d.progress ?? 0,
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

  // Initial fetch
  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  // Polling
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

  // Derive currentTick from summary data
  const currentTick =
    data.lastTickTime != null
      ? {
          timestamp: data.lastTickTime,
          price: data.lastTickPrice != null ? String(data.lastTickPrice) : null,
        }
      : null;

  return {
    ...data,
    isLoading,
    error,
    refetch: fetchSummary,
    currentTick,
  };
}
