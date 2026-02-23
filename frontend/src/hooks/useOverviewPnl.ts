/**
 * Hook for fetching PnL summary from the backend API.
 *
 * Realized PnL and trade count are computed server-side via DB aggregation,
 * eliminating the need to fetch all positions/trades on the client.
 *
 * Unrealized PnL is currently not stored in the Position model (it depends
 * on live market prices from OANDA), so the backend returns 0 for now.
 */

import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { OpenAPI } from '../api/generated/core/OpenAPI';
import { TaskType } from '../types/common';
import { handleAuthErrorStatus } from '../utils/authEvents';

interface PnlSummary {
  realizedPnl: number;
  unrealizedPnl: number;
  totalTrades: number;
  openPositionCount: number;
}

interface UseOverviewPnlResult extends PnlSummary {
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useOverviewPnl(
  taskId: string,
  taskType: TaskType,
  celeryTaskId?: string
): UseOverviewPnlResult {
  const [data, setData] = useState<PnlSummary>({
    realizedPnl: 0,
    unrealizedPnl: 0,
    totalTrades: 0,
    openPositionCount: 0,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchPnl = useCallback(async () => {
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

      const url = `${OpenAPI.BASE}${prefix}/${taskId}/pnl-summary/`;

      const headers: Record<string, string> = {
        Accept: 'application/json',
      };
      if (OpenAPI.TOKEN) {
        const token =
          typeof OpenAPI.TOKEN === 'function'
            ? await (OpenAPI.TOKEN as (options: unknown) => Promise<string>)({})
            : OpenAPI.TOKEN;
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
      }

      const params: Record<string, string> = {};
      if (celeryTaskId) params.celery_task_id = celeryTaskId;

      const response = await axios.get(url, {
        params,
        headers,
        withCredentials: OpenAPI.WITH_CREDENTIALS,
      });

      const d = response.data;
      setData({
        realizedPnl: parseFloat(d.realized_pnl) || 0,
        unrealizedPnl: parseFloat(d.unrealized_pnl) || 0,
        totalTrades: d.total_trades ?? 0,
        openPositionCount: d.open_position_count ?? 0,
      });
    } catch (err) {
      if (axios.isAxiosError(err) && err.response) {
        handleAuthErrorStatus(err.response.status, {
          source: 'http',
          status: err.response.status,
          context: 'pnl_summary',
        });
      }
      setError(
        new Error(
          err instanceof Error ? err.message : 'Failed to load PnL summary'
        )
      );
    } finally {
      setIsLoading(false);
    }
  }, [taskId, taskType, celeryTaskId]);

  useEffect(() => {
    fetchPnl();
  }, [fetchPnl]);

  return {
    ...data,
    isLoading,
    error,
    refetch: fetchPnl,
  };
}
