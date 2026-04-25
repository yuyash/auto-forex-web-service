import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { apiConfig } from '../api/apiConfig';
import { queryKeys } from '../config/reactQuery';
import { TaskType } from '../types/common';
import { logger } from '../utils/logger';

interface TaskSnapshot {
  id: string;
  task_type: TaskType;
  status?: string;
  progress?: number | null;
  execution_id?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
  updated_at?: string | null;
}

const STREAM_RETRY_DELAY_MS = 5000;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function taskDetailKey(taskType: TaskType, taskId: string) {
  return taskType === TaskType.BACKTEST
    ? queryKeys.backtestTasks.detail(taskId)
    : queryKeys.tradingTasks.detail(taskId);
}

function taskListKey(taskType: TaskType) {
  return taskType === TaskType.BACKTEST
    ? queryKeys.backtestTasks.lists()
    : queryKeys.tradingTasks.lists();
}

function parseSseEvent(raw: string): { event: string; data: string } | null {
  const lines = raw.split('\n');
  const eventLine = lines.find((line) => line.startsWith('event:'));
  const dataLines = lines.filter((line) => line.startsWith('data:'));
  if (!eventLine || dataLines.length === 0) {
    return null;
  }
  return {
    event: eventLine.slice('event:'.length).trim(),
    data: dataLines.map((line) => line.slice('data:'.length).trim()).join('\n'),
  };
}

function applySnapshot<TTask>(
  current: TTask | undefined,
  snapshot: TaskSnapshot
) {
  if (!current || typeof current !== 'object') {
    return current;
  }
  return {
    ...current,
    status: snapshot.status ?? (current as { status?: string }).status,
    progress: snapshot.progress ?? (current as { progress?: number }).progress,
    execution_id:
      snapshot.execution_id ??
      (current as { execution_id?: string | null }).execution_id,
    started_at:
      snapshot.started_at ??
      (current as { started_at?: string | null }).started_at,
    completed_at:
      snapshot.completed_at ??
      (current as { completed_at?: string | null }).completed_at,
    error_message:
      snapshot.error_message ??
      (current as { error_message?: string | null }).error_message,
    updated_at:
      snapshot.updated_at ??
      (current as { updated_at?: string | null }).updated_at,
  } satisfies TTask;
}

export function useTaskEventStream<TTask>({
  taskType,
  taskId,
  enabled,
}: {
  taskType: TaskType;
  taskId?: string;
  enabled: boolean;
}): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (
      !enabled ||
      !taskId ||
      !UUID_PATTERN.test(taskId) ||
      typeof ReadableStream === 'undefined'
    ) {
      return;
    }

    const abortController = new AbortController();
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const connect = async () => {
      try {
        const response = await fetch(
          `${apiConfig.BASE}/api/trading/tasks/${taskType}/${taskId}/stream/`,
          {
            method: 'GET',
            credentials: apiConfig.WITH_CREDENTIALS ? 'include' : 'same-origin',
            headers: { Accept: 'text/event-stream' },
            signal: abortController.signal,
          }
        );

        if (!response.ok || !response.body) {
          throw new Error(`Task stream failed with status ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (!closed) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const chunks = buffer.split('\n\n');
          buffer = chunks.pop() ?? '';

          for (const chunk of chunks) {
            const parsed = parseSseEvent(chunk);
            if (!parsed || parsed.event !== 'snapshot') {
              continue;
            }

            const snapshot = JSON.parse(parsed.data) as TaskSnapshot;
            queryClient.setQueryData<TTask>(
              taskDetailKey(taskType, taskId),
              (current) => applySnapshot(current, snapshot)
            );
            void queryClient.invalidateQueries({
              queryKey: taskListKey(taskType),
            });
          }
        }
      } catch (error) {
        if (closed || abortController.signal.aborted) {
          return;
        }
        logger.warn('Task event stream disconnected', {
          taskType,
          taskId,
          error: error instanceof Error ? error.message : String(error),
        });
        retryTimer = setTimeout(connect, STREAM_RETRY_DELAY_MS);
      }
    };

    void connect();

    return () => {
      closed = true;
      abortController.abort();
      if (retryTimer) {
        clearTimeout(retryTimer);
      }
    };
  }, [enabled, queryClient, taskId, taskType]);
}
