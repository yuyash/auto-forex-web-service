/**
 * useTaskLogs Hook
 *
 * Fetches logs from task-based API endpoints with DRF pagination.
 * Supports incremental fetching via the `since` parameter — during polling
 * cycles only new records are fetched and merged into the local cache.
 */

import type { TaskType } from '../types/common';
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

export type TaskLogMessageMatchMode = 'partial' | 'exact' | 'regex';

interface UseTaskLogsOptions {
  taskId: string;
  taskType: TaskType;
  /** Filter by execution run ID. When omitted, uses the latest execution run. */
  executionRunId?: string;
  level?: string[];
  component?: string[];
  message?: string;
  messageMatchMode?: TaskLogMessageMatchMode;
  /** Filter logs by position ID (supports prefix match for truncated UUIDs). */
  positionId?: string;
  timestampFrom?: string;
  timestampTo?: string;
  ordering?: string;
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

function getSortValue(log: TaskLog, field: string): string | number {
  if (field === 'timestamp') {
    const parsed = Date.parse(log.timestamp);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  const value = (log as unknown as Record<string, unknown>)[field];
  if (typeof value === 'number') return value;
  return String(value ?? '');
}

function mergeLogsByOrdering(
  currentItems: TaskLog[],
  incoming: TaskLog[],
  ordering: string
): TaskLog[] {
  const field = ordering.startsWith('-') ? ordering.slice(1) : ordering;
  const direction = ordering.startsWith('-') ? 'desc' : 'asc';
  const merged = new Map(currentItems.map((log) => [log.id, log]));
  for (const log of incoming) {
    merged.set(log.id, log);
  }
  return Array.from(merged.values()).sort((a, b) => {
    const aValue = getSortValue(a, field || 'timestamp');
    const bValue = getSortValue(b, field || 'timestamp');
    if (aValue < bValue) return direction === 'desc' ? 1 : -1;
    if (aValue > bValue) return direction === 'desc' ? -1 : 1;
    return a.id.localeCompare(b.id);
  });
}

export const useTaskLogs = ({
  taskId,
  taskType,
  executionRunId,
  level,
  component,
  message,
  messageMatchMode = 'partial',
  positionId,
  timestampFrom,
  timestampTo,
  ordering = '-timestamp',
  page = 1,
  pageSize = 100,
  enableRealTimeUpdates = false,
  refreshInterval = 5_000,
}: UseTaskLogsOptions): UseTaskLogsResult => {
  const paramsKey = `${taskId}-${taskType}-${executionRunId ?? ''}-${(level || []).join(',')}-${(component || []).join(',')}-${message ?? ''}-${message ? messageMatchMode : ''}-${positionId ?? ''}-${timestampFrom ?? ''}-${timestampTo ?? ''}-${ordering}-${page}-${pageSize}`;
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
      if (message) {
        params.message = message;
        params.message_match = messageMatchMode;
      }
      if (positionId) params.position_id = positionId;
      if (timestampFrom) params.timestamp_from = timestampFrom;
      if (timestampTo) params.timestamp_to = timestampTo;
      if (ordering) params.ordering = ordering;
      return params;
    },
    getLatestCursor: getLatestTimestamp,
    getItemId: (log) => log.id,
    mergeIncremental: ({ currentItems, incoming }) =>
      mergeLogsByOrdering(currentItems, incoming, ordering),
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
