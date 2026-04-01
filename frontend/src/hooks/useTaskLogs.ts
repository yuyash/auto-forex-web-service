/**
 * useTaskLogs Hook
 *
 * Fetches logs from task-based API endpoints with DRF pagination.
 * Supports incremental fetching via the `since` parameter — during polling
 * cycles only new records are fetched and merged into the local cache.
 */

import { TaskType } from '../types/common';
import { toIncrementalCollectionState } from './useTaskCollections';
import { useIncrementalTaskResource } from './useIncrementalTaskResource';

export interface TaskLog {
  id: string;
  timestamp: string;
  level: string;
  component: string;
  message: string;
  details?: Record<string, unknown>;
}

interface UseTaskLogsOptions {
  taskId: string;
  taskType: TaskType;
  /** Filter by execution run ID. When omitted, uses the latest execution run. */
  executionRunId?: string;
  level?: string[];
  component?: string[];
  /** Filter logs by position ID (supports prefix match for truncated UUIDs). */
  positionId?: string;
  timestampFrom?: string;
  timestampTo?: string;
  page?: number;
  pageSize?: number;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskLogsResult {
  logs: TaskLog[];
  totalCount: number;
  hasNext: boolean;
  hasPrevious: boolean;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
}

function getLatestTimestamp(logs: TaskLog[]): string | null {
  let latest: string | null = null;
  for (const l of logs) {
    if (l.timestamp && (!latest || l.timestamp > latest)) {
      latest = l.timestamp;
    }
  }
  return latest;
}

export const useTaskLogs = ({
  taskId,
  taskType,
  executionRunId,
  level,
  component,
  positionId,
  timestampFrom,
  timestampTo,
  page = 1,
  pageSize = 100,
  enableRealTimeUpdates = false,
  refreshInterval = 5_000,
}: UseTaskLogsOptions): UseTaskLogsResult => {
  const paramsKey = `${taskId}-${taskType}-${executionRunId ?? ''}-${(level || []).join(',')}-${(component || []).join(',')}-${positionId ?? ''}-${timestampFrom ?? ''}-${timestampTo ?? ''}-${page}-${pageSize}`;
  const {
    items: logs,
    totalCount,
    hasNext,
    hasPrevious,
    isLoading,
    error,
    refresh,
  } = useIncrementalTaskResource<TaskLog>({
    taskId,
    taskType,
    endpoint: 'logs',
    paramsKey,
    page,
    pageSize,
    enableRealTimeUpdates,
    refreshInterval,
    errorContext: 'task_logs',
    fallbackErrorMessage: 'Failed to load logs',
    buildParams: () => {
      const params: Record<string, string> = {};
      if (executionRunId != null) {
        params.execution_id = String(executionRunId);
      }
      if (level && level.length > 0) params.level = level.join(',');
      if (component && component.length > 0) {
        params.component = component.join(',');
      }
      if (positionId) params.position_id = positionId;
      if (timestampFrom) params.timestamp_from = timestampFrom;
      if (timestampTo) params.timestamp_to = timestampTo;
      return params;
    },
    getLatestCursor: getLatestTimestamp,
    getItemId: (log) => log.id,
  });

  return {
    ...toIncrementalCollectionState({
      items: logs,
      totalCount,
      hasNext,
      hasPrevious,
      isLoading,
      error,
      refresh,
    }),
    logs,
  };
};
