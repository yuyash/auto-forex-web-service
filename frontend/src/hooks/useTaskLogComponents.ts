/**
 * useTaskLogComponents Hook
 *
 * Fetches distinct logger/component names for a task's logs.
 */

import { useQuery } from '@tanstack/react-query';
import { TaskType } from '../types/common';
import { createTaskLogComponentsQuery } from './taskLogComponentQueries';

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
  const query = useQuery(
    createTaskLogComponentsQuery(taskId, taskType, executionRunId)
  );

  return {
    components: query.data ?? [],
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
  };
};
