// useTaskPolling - React hook for HTTP polling of task updates

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  TaskPollingService,
  type TaskType,
  type TaskStatusResponse,
  type TaskDetailsResponse,
  type PollingOptions,
} from '../services/polling/TaskPollingService';

export interface UseTaskPollingOptions extends PollingOptions {
  enabled?: boolean; // Whether to start polling immediately
  pollStatus?: boolean; // Poll for status updates (default: true)
  pollDetails?: boolean; // Poll for details updates (default: false)
  pollLogs?: boolean; // Poll for logs updates (default: false)
}

// Local type for logs response (not exported from TaskPollingService)
interface TaskLogsResponse {
  logs: Array<{ timestamp: string; level: string; message: string }>;
}

export interface UseTaskPollingResult {
  status: TaskStatusResponse | null;
  details: TaskDetailsResponse | null;
  logs: TaskLogsResponse | null;
  isLoading: boolean;
  error: Error | null;
  isPolling: boolean;
  startPolling: () => void;
  stopPolling: () => void;
  refetch: () => void;
}

/**
 * useTaskPolling - Custom hook for polling task updates
 *
 * @param taskId - The ID of the task to poll
 * @param taskType - The type of task ('backtest' or 'trading')
 * @param options - Polling configuration options
 *
 * @returns Object containing status, details, logs, and control functions
 *
 * @example
 * ```tsx
 * const { status, details, isLoading, error } = useTaskPolling(
 *   taskId,
 *   'backtest',
 *   { interval: 3000, enabled: true }
 * );
 * ```
 */
export function useTaskPolling(
  taskId: string | undefined,
  taskType: TaskType,
  options: UseTaskPollingOptions = {}
): UseTaskPollingResult {
  const {
    enabled = true,
    pollStatus = true,
    pollDetails = false,
    pollLogs = false,
    interval = 3000,
    maxRetries = 5,
    backoffMultiplier = 2,
    maxBackoff = 30000,
  } = options;

  const [status, setStatus] = useState<TaskStatusResponse | null>(null);
  const [details, setDetails] = useState<TaskDetailsResponse | null>(null);
  const [logs, setLogs] = useState<TaskLogsResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(enabled && !!taskId);
  const [error, setError] = useState<Error | null>(null);

  const [isPolling, setIsPolling] = useState<boolean>(false);

  const pollingServiceRef = useRef<TaskPollingService | null>(null);

  /**
   * Initialize polling service
   */
  const initializeService = useCallback(() => {
    if (!taskId) {
      return null;
    }

    const callbacks = {
      ...(pollStatus && {
        onStatusUpdate: (statusUpdate: TaskStatusResponse) => {
          setStatus(statusUpdate);
          setIsLoading(false);
        },
      }),
      ...(pollDetails && {
        onDetailsUpdate: (detailsUpdate: TaskDetailsResponse) => {
          setDetails(detailsUpdate);
        },
      }),
      ...(pollLogs && {
        onLogsUpdate: (logsUpdate: TaskLogsResponse) => {
          setLogs(logsUpdate);
        },
      }),
      onError: (err: Error) => {
        setError(err);
        setIsLoading(false);
      },
    };

    const pollingOptions = {
      interval,
      maxRetries,
      backoffMultiplier,
      maxBackoff,
    };

    return new TaskPollingService(taskId, taskType, callbacks, pollingOptions);
  }, [
    taskId,
    taskType,
    pollStatus,
    pollDetails,
    pollLogs,
    interval,
    maxRetries,
    backoffMultiplier,
    maxBackoff,
  ]);

  /**
   * Start polling
   */
  const startPolling = useCallback(() => {
    console.log(
      `[useTaskPolling:START] Starting polling - taskId=${taskId}, taskType=${taskType}`
    );
    if (!pollingServiceRef.current) {
      pollingServiceRef.current = initializeService();
    }

    if (pollingServiceRef.current) {
      pollingServiceRef.current.startPolling();
      setIsPolling(true);
      setError(null);
    }
  }, [initializeService, taskId, taskType]);

  /**
   * Stop polling
   */
  const stopPolling = useCallback(() => {
    console.log(
      `[useTaskPolling:STOP] Stopping polling - taskId=${taskId}, taskType=${taskType}`
    );
    if (pollingServiceRef.current) {
      pollingServiceRef.current.stopPolling();
      setIsPolling(false);
    }
  }, [taskId, taskType]);

  /**
   * Manually trigger a refetch
   */
  const refetch = useCallback(() => {
    console.log(
      `[useTaskPolling:REFETCH] Manual refetch - taskId=${taskId}, taskType=${taskType}`
    );
    if (pollingServiceRef.current) {
      // Stop and restart to trigger immediate fetch
      pollingServiceRef.current.stopPolling();
      pollingServiceRef.current.startPolling();
      setIsPolling(true);
    }
  }, [taskId, taskType]);

  /**
   * Effect: Initialize and start polling when enabled
   */
  useEffect(() => {
    if (!taskId || !enabled) {
      return;
    }

    // Initialize service
    const service = initializeService();
    pollingServiceRef.current = service;

    if (service) {
      service.startPolling();
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsPolling(true);
    }

    // Cleanup on unmount
    return () => {
      if (pollingServiceRef.current) {
        pollingServiceRef.current.cleanup();
        pollingServiceRef.current = null;
      }
      setIsPolling(false);
    };
  }, [taskId, enabled, initializeService]);

  /**
   * Effect: Update callbacks when options change
   */
  useEffect(() => {
    if (!pollingServiceRef.current) {
      return;
    }

    const callbacks = {
      ...(pollStatus && {
        onStatusUpdate: (statusUpdate: TaskStatusResponse) => {
          setStatus(statusUpdate);
          setIsLoading(false);
        },
      }),
      ...(pollDetails && {
        onDetailsUpdate: (detailsUpdate: TaskDetailsResponse) => {
          setDetails(detailsUpdate);
        },
      }),
      ...(pollLogs && {
        onLogsUpdate: (logsUpdate: TaskLogsResponse) => {
          setLogs(logsUpdate);
        },
      }),
      onError: (err: Error) => {
        setError(err);
        setIsLoading(false);
      },
    };

    pollingServiceRef.current.updateCallbacks(callbacks);
  }, [pollStatus, pollDetails, pollLogs]);

  /**
   * Effect: Update polling options when they change
   */
  useEffect(() => {
    if (!pollingServiceRef.current) {
      return;
    }

    pollingServiceRef.current.updateOptions({
      interval,
      maxRetries,
      backoffMultiplier,
      maxBackoff,
    });
  }, [interval, maxRetries, backoffMultiplier, maxBackoff]);

  return {
    status,
    details,
    logs,
    isLoading,
    error,
    isPolling,
    startPolling,
    stopPolling,
    refetch,
  };
}
