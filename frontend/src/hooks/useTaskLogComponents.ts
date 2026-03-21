/**
 * useTaskLogComponents Hook
 *
 * Fetches distinct logger/component names for a task's logs.
 */

import { useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
import { TaskType } from '../types/common';
import { handleAuthErrorStatus } from '../utils/authEvents';
import {
  fetchTaskResourceObject,
  isApiErrorWithStatus,
} from '../services/api/taskResources';

interface UseTaskLogComponentsOptions {
  taskId: string;
  taskType: TaskType;
  executionRunId?: string;
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
  const fetchComponents = useCallback(async () => {
    if (!taskId) {
      return [];
    }
    try {
      const response = await fetchTaskResourceObject<{
        components?: string[];
      }>(
        taskType,
        taskId,
        'log-components',
        executionRunId != null
          ? { execution_id: String(executionRunId) }
          : undefined
      );
      return response.components ?? [];
    } catch (err) {
      if (isApiErrorWithStatus(err)) {
        handleAuthErrorStatus(err.status, {
          source: 'http',
          status: err.status,
          context: 'task_log_components',
        });
      }
      throw new Error(
        err instanceof Error ? err.message : 'Failed to load components'
      );
    }
  }, [taskId, taskType, executionRunId]);

  const query = useQuery({
    queryKey: queryKeys.taskResources.logComponents(
      taskType,
      taskId,
      executionRunId
    ),
    queryFn: fetchComponents,
    enabled: Boolean(taskId),
  });

  return {
    components: query.data ?? [],
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
  };
};
