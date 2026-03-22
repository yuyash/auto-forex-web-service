/**
 * useTaskEvents Hook
 *
 * Fetches events from task-based API endpoints with DRF pagination.
 * Supports incremental fetching via the `since` parameter — during polling
 * cycles only new records are fetched and merged into the local cache.
 */

import { TaskType } from '../types/common';
import { toIncrementalCollectionState } from './useTaskCollections';
import { useIncrementalTaskResource } from './useIncrementalTaskResource';

export interface TaskEvent {
  id: string;
  event_type: string;
  event_type_display?: string;
  event_scope?: 'task' | 'trading' | 'strategy';
  severity: string;
  description: string;
  details?: Record<string, unknown>;
  created_at: string;
}

export type TaskEventSource = 'trading' | 'task' | 'strategy';

interface UseTaskEventsOptions {
  taskId: string | number;
  taskType: TaskType;
  /** Filter by execution run ID. When omitted, uses the latest execution run. */
  executionRunId?: string;
  source?: TaskEventSource;
  eventType?: string;
  severity?: string;
  page?: number;
  pageSize?: number;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskEventsResult {
  events: TaskEvent[];
  totalCount: number;
  hasNext: boolean;
  hasPrevious: boolean;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
}

function getLatestCreatedAt(events: TaskEvent[]): string | null {
  let latest: string | null = null;
  for (const e of events) {
    if (e.created_at && (!latest || e.created_at > latest)) {
      latest = e.created_at;
    }
  }
  return latest;
}

export const useTaskEvents = ({
  taskId,
  taskType,
  executionRunId,
  source = 'trading',
  eventType,
  severity,
  page = 1,
  pageSize = 100,
  enableRealTimeUpdates = false,
  refreshInterval = 10_000,
}: UseTaskEventsOptions): UseTaskEventsResult => {
  const paramsKey = `${taskId}-${taskType}-${executionRunId ?? ''}-${source}-${eventType}-${severity}-${page}-${pageSize}`;
  const endpoint = source === 'strategy' ? 'strategy-events' : 'events';
  const {
    items: events,
    totalCount,
    hasNext,
    hasPrevious,
    isLoading,
    error,
    refresh,
  } = useIncrementalTaskResource<TaskEvent>({
    taskId,
    taskType,
    endpoint,
    paramsKey,
    page,
    pageSize,
    enableRealTimeUpdates,
    refreshInterval,
    errorContext: 'task_events',
    fallbackErrorMessage: 'Failed to load events',
    buildParams: () => {
      const params: Record<string, string> = {};
      if (executionRunId != null) {
        params.execution_id = String(executionRunId);
      }
      if (eventType) params.event_type = eventType;
      if (severity) params.severity = severity;
      if (source !== 'strategy') {
        params.scope = source;
      }
      return params;
    },
    getLatestCursor: getLatestCreatedAt,
    getItemId: (event) => event.id,
  });

  return {
    ...toIncrementalCollectionState({
      items: events,
      totalCount,
      hasNext,
      hasPrevious,
      isLoading,
      error,
      refresh,
    }),
    events,
  };
};
