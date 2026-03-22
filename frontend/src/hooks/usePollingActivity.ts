import { useDocumentVisibility } from './useDocumentVisibility';
import { useOnlineStatus } from './useOnlineStatus';

interface UsePollingActivityOptions {
  requireVisible?: boolean;
  requireOnline?: boolean;
}

export function usePollingActivity(
  enabled: boolean,
  options: UsePollingActivityOptions = {}
): boolean {
  const { requireVisible = true, requireOnline = true } = options;
  const isVisible = useDocumentVisibility();
  const isOnline = useOnlineStatus();

  return (
    enabled && (!requireVisible || isVisible) && (!requireOnline || isOnline)
  );
}
