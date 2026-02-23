// useCurrentTickPolling - React hook for polling the lightweight current-tick endpoint

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  TickPollingService,
  type CurrentTickResponse,
  type TickPollingOptions,
} from '../services/polling/TickPollingService';
import type { TaskType } from '../services/polling/TaskPollingService';

export interface UseCurrentTickPollingOptions extends TickPollingOptions {
  /** Start polling immediately (default: true) */
  enabled?: boolean;
}

export interface UseCurrentTickPollingResult {
  /** Latest tick data from the server */
  data: CurrentTickResponse | null;
  /** Convenience accessor: { timestamp, price } or null */
  currentTick: { timestamp: string; price: string | null } | null;
  /** Number of ticks processed by the task */
  ticksProcessed: number;
  isLoading: boolean;
  error: Error | null;
  isPolling: boolean;
  startPolling: () => void;
  stopPolling: () => void;
}

export function useCurrentTickPolling(
  taskId: string | undefined,
  taskType: TaskType,
  options: UseCurrentTickPollingOptions = {}
): UseCurrentTickPollingResult {
  const {
    enabled = true,
    interval = 2000,
    maxRetries = 5,
    backoffMultiplier = 2,
    maxBackoff = 30000,
  } = options;

  const [data, setData] = useState<CurrentTickResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(enabled && !!taskId);
  const [error, setError] = useState<Error | null>(null);
  const [isPolling, setIsPolling] = useState<boolean>(false);

  const serviceRef = useRef<TickPollingService | null>(null);

  const initService = useCallback(() => {
    if (!taskId) return null;

    return new TickPollingService(
      taskId,
      taskType,
      {
        onTick: (tick: CurrentTickResponse) => {
          setData(tick);
          setIsLoading(false);
          setError(null);
        },
        onError: (err: Error) => {
          setError(err);
          setIsLoading(false);
        },
      },
      { interval, maxRetries, backoffMultiplier, maxBackoff }
    );
  }, [taskId, taskType, interval, maxRetries, backoffMultiplier, maxBackoff]);

  const startPolling = useCallback(() => {
    if (!serviceRef.current) {
      serviceRef.current = initService();
    }
    if (serviceRef.current) {
      serviceRef.current.startPolling();
      setIsPolling(true);
      setError(null);
    }
  }, [initService]);

  const stopPolling = useCallback(() => {
    if (serviceRef.current) {
      serviceRef.current.stopPolling();
      setIsPolling(false);
    }
  }, []);

  // Auto-start / cleanup
  useEffect(() => {
    if (!taskId || !enabled) return;

    const svc = initService();
    serviceRef.current = svc;
    if (svc) {
      svc.startPolling();
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsPolling(true);
    }

    return () => {
      if (serviceRef.current) {
        serviceRef.current.cleanup();
        serviceRef.current = null;
      }
      setIsPolling(false);
    };
  }, [taskId, enabled, initService]);

  // Update options on the fly
  useEffect(() => {
    serviceRef.current?.updateOptions({
      interval,
      maxRetries,
      backoffMultiplier,
      maxBackoff,
    });
  }, [interval, maxRetries, backoffMultiplier, maxBackoff]);

  return {
    data,
    currentTick: data?.current_tick ?? null,
    ticksProcessed: data?.ticks_processed ?? 0,
    isLoading,
    error,
    isPolling,
    startPolling,
    stopPolling,
  };
}
