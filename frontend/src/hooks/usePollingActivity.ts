import { usePollingPolicy } from './usePollingPolicy';

interface UsePollingActivityOptions {
  requireVisible?: boolean;
  requireOnline?: boolean;
}

export function usePollingActivity(
  enabled: boolean,
  options: UsePollingActivityOptions = {}
): boolean {
  const { requireVisible = true, requireOnline = true } = options;
  return usePollingPolicy({
    enabled,
    baseIntervalMs: 10_000,
    requireVisible,
    requireOnline,
  }).isActive;
}
