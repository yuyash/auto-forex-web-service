import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { apiConfig, resolveToken } from '../api/apiConfig';
import { TaskType } from '../types/common';
import type { StrategyVisualizationResponse } from '../types/strategyVisualization';
import { handleAuthErrorStatus } from '../utils/authEvents';

interface UseTaskStrategyEventsOptions {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskStrategyEventsResult {
  data: StrategyVisualizationResponse | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const token = await resolveToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

export function useTaskStrategyEvents({
  taskId,
  taskType,
  executionRunId,
  enableRealTimeUpdates = false,
  refreshInterval = 10_000,
}: UseTaskStrategyEventsOptions): UseTaskStrategyEventsResult {
  const [data, setData] = useState<StrategyVisualizationResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const latestRequestRef = useRef(0);

  const fetchData = useCallback(async () => {
    if (!taskId) {
      setIsLoading(false);
      return;
    }

    const requestId = ++latestRequestRef.current;
    try {
      setIsLoading(true);
      setError(null);

      const prefix =
        taskType === TaskType.BACKTEST
          ? '/api/trading/tasks/backtest'
          : '/api/trading/tasks/trading';
      const params: Record<string, string> = {};
      if (executionRunId) {
        params.execution_id = executionRunId;
      }
      const headers = await getAuthHeaders();
      const response = await axios.get<StrategyVisualizationResponse>(
        `${apiConfig.BASE}${prefix}/${taskId}/strategy-events/`,
        {
          params,
          headers,
          withCredentials: apiConfig.WITH_CREDENTIALS,
        }
      );
      if (requestId !== latestRequestRef.current) return;
      setData(response.data);
    } catch (err) {
      if (requestId !== latestRequestRef.current) return;
      if (axios.isAxiosError(err) && err.response) {
        handleAuthErrorStatus(err.response.status, {
          source: 'http',
          status: err.response.status,
          context: 'task_strategy_events',
        });
      }
      setError(
        new Error(
          err instanceof Error
            ? err.message
            : 'Failed to load strategy visualization'
        )
      );
    } finally {
      if (requestId === latestRequestRef.current) {
        setIsLoading(false);
      }
    }
  }, [executionRunId, taskId, taskType]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const id = window.setInterval(() => {
      fetchData();
    }, refreshInterval);
    return () => window.clearInterval(id);
  }, [enableRealTimeUpdates, fetchData, refreshInterval]);

  return { data, isLoading, error, refetch: fetchData };
}
