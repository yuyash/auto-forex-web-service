import type { UseQueryOptions } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
import { TaskType } from '../types/common';
import { handleAuthErrorStatus } from '../utils/authEvents';
import {
  fetchTaskResourceObject,
  isApiErrorWithStatus,
} from '../services/api/taskResources';

export function createTaskLogComponentsQuery(
  taskId: string,
  taskType: TaskType,
  executionRunId?: string
): UseQueryOptions<string[]> {
  return {
    queryKey: queryKeys.taskResources.logComponents(
      taskType,
      taskId,
      executionRunId
    ),
    enabled: Boolean(taskId),
    queryFn: async () => {
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
    },
  };
}
