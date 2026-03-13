import { useCallback, useEffect, useRef, useState } from 'react';
import { TaskStatus } from '../types/common';

const DEFAULT_STATUS_POLL_MS = 10_000;
const FAST_STATUS_POLL_MS = 1_000;
const FAST_STATUS_POLL_WINDOW_MS = 15_000;

interface OptimisticStatusState {
  status: TaskStatus;
  settleOn: TaskStatus[];
}

interface UseOptimisticTaskStatusResult {
  optimisticStatus: OptimisticStatusState | null;
  statusPollingIntervalMs: number;
  applyOptimisticStatus: (status: TaskStatus, settleOn: TaskStatus[]) => void;
  clearOptimisticStatus: () => void;
}

export function useOptimisticTaskStatus(): UseOptimisticTaskStatusResult {
  const [statusPollingIntervalMs, setStatusPollingIntervalMs] = useState(
    DEFAULT_STATUS_POLL_MS
  );
  const [optimisticStatus, setOptimisticStatus] =
    useState<OptimisticStatusState | null>(null);
  const fastPollingResetRef = useRef<number | null>(null);
  const optimisticStatusResetRef = useRef<number | null>(null);

  const accelerateStatusPolling = useCallback(() => {
    setStatusPollingIntervalMs(FAST_STATUS_POLL_MS);

    if (fastPollingResetRef.current !== null) {
      window.clearTimeout(fastPollingResetRef.current);
    }

    fastPollingResetRef.current = window.setTimeout(() => {
      setStatusPollingIntervalMs(DEFAULT_STATUS_POLL_MS);
      fastPollingResetRef.current = null;
    }, FAST_STATUS_POLL_WINDOW_MS);
  }, []);

  const applyOptimisticStatus = useCallback(
    (status: TaskStatus, settleOn: TaskStatus[]) => {
      setOptimisticStatus({ status, settleOn });
      accelerateStatusPolling();

      if (optimisticStatusResetRef.current !== null) {
        window.clearTimeout(optimisticStatusResetRef.current);
      }

      optimisticStatusResetRef.current = window.setTimeout(() => {
        setOptimisticStatus(null);
        optimisticStatusResetRef.current = null;
      }, FAST_STATUS_POLL_WINDOW_MS);
    },
    [accelerateStatusPolling]
  );

  const clearOptimisticStatus = useCallback(() => {
    setOptimisticStatus(null);
  }, []);

  useEffect(() => {
    return () => {
      if (fastPollingResetRef.current !== null) {
        window.clearTimeout(fastPollingResetRef.current);
      }
      if (optimisticStatusResetRef.current !== null) {
        window.clearTimeout(optimisticStatusResetRef.current);
      }
    };
  }, []);

  return {
    optimisticStatus,
    statusPollingIntervalMs,
    applyOptimisticStatus,
    clearOptimisticStatus,
  };
}
