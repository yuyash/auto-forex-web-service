import { useCallback, useMemo, useState } from 'react';
import { useDocumentVisibility } from './useDocumentVisibility';
import { useOnlineStatus } from './useOnlineStatus';

interface UsePollingPolicyOptions {
  enabled: boolean;
  baseIntervalMs: number;
  requireVisible?: boolean;
  requireOnline?: boolean;
  backoffMultiplier?: number;
  maxIntervalMs?: number;
}

interface PollingPolicyState {
  isActive: boolean;
  intervalMs: number;
  consecutiveFailures: number;
  registerFailure: () => void;
  resetFailures: () => void;
}

export function usePollingPolicy({
  enabled,
  baseIntervalMs,
  requireVisible = true,
  requireOnline = true,
  backoffMultiplier = 2,
  maxIntervalMs = 60_000,
}: UsePollingPolicyOptions): PollingPolicyState {
  const isVisible = useDocumentVisibility();
  const isOnline = useOnlineStatus();
  const [consecutiveFailures, setConsecutiveFailures] = useState(0);

  const registerFailure = useCallback(() => {
    setConsecutiveFailures((current) => current + 1);
  }, []);

  const resetFailures = useCallback(() => {
    setConsecutiveFailures((current) => (current === 0 ? current : 0));
  }, []);

  const intervalMs = useMemo(() => {
    const nextInterval =
      baseIntervalMs * backoffMultiplier ** Math.max(0, consecutiveFailures);
    return Math.min(nextInterval, maxIntervalMs);
  }, [backoffMultiplier, baseIntervalMs, consecutiveFailures, maxIntervalMs]);

  return {
    isActive:
      enabled && (!requireVisible || isVisible) && (!requireOnline || isOnline),
    intervalMs,
    consecutiveFailures,
    registerFailure,
    resetFailures,
  };
}
