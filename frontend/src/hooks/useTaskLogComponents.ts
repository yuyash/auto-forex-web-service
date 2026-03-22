/**
 * useTaskLogComponents Hook
 *
 * Fetches distinct logger/component names for a task's logs.
 */

import { TaskType } from '../types/common';
import { createTaskLogComponentsQuery } from './taskLogComponentQueries';
import { mapQueryStateFields, useSimpleQueryState } from './useTaskCollections';

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
  const query = useSimpleQueryState(
    createTaskLogComponentsQuery(taskId, taskType, executionRunId)
  );

  return mapQueryStateFields(query, (data) => ({
    components: data ?? [],
  }));
};
