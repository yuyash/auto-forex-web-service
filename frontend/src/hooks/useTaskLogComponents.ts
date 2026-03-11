/**
 * useTaskLogComponents Hook
 *
 * Fetches distinct logger/component names for a task's logs.
 */

import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { apiConfig, resolveToken } from '../api/apiConfig';
import { TaskType } from '../types/common';
import { handleAuthErrorStatus } from '../utils/authEvents';

interface UseTaskLogComponentsOptions {
  taskId: string;
  taskType: TaskType;
  executionRunId?: number;
}

interface UseTaskLogComponentsResult {
  components: string[];
  isLoading: boolean;
  error: Error | null;
}

export const useTaskLogComponents = ({
  taskId,
  taskType,
  executionRunId,
}: UseTaskLogComponentsOptions): UseTaskLogComponentsResult => {
  const [components, setComponents] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchComponents = useCallback(async () => {
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

      const params: Record<string, string> = {};
      if (executionRunId != null) {
        params.execution_run_id = String(executionRunId);
      }

      const token = await resolveToken();
      const headers: Record<string, string> = { Accept: 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const url = `${apiConfig.BASE}${prefix}/${taskId}/log-components/`;
      const response = await axios.get(url, {
        params,
        headers,
        withCredentials: apiConfig.WITH_CREDENTIALS,
      });

      setComponents(response.data.components || []);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response) {
        handleAuthErrorStatus(err.response.status, {
          source: 'http',
          status: err.response.status,
          context: 'task_log_components',
        });
      }
      setError(
        new Error(
          err instanceof Error ? err.message : 'Failed to load components'
        )
      );
    } finally {
      setIsLoading(false);
    }
  }, [taskId, taskType, executionRunId]);

  useEffect(() => {
    fetchComponents();
  }, [fetchComponents]);

  return { components, isLoading, error };
};
