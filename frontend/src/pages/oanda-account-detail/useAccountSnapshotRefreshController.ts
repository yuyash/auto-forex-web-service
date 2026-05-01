import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import {
  isAccountSnapshotRefreshActive,
  useAccountSnapshotRefreshStatus,
} from '../../hooks/useAccounts';
import { useRefreshAccountSnapshot } from '../../hooks/useAccountMutations';
import { useToast } from '../../components/common/useToast';
import { logger } from '../../utils/logger';
import type { Account } from '../../types/strategy';

interface UseAccountSnapshotRefreshControllerOptions {
  account: Account | null;
  accountId: number | null;
}

export function useAccountSnapshotRefreshController({
  account,
  accountId,
}: UseAccountSnapshotRefreshControllerOptions) {
  const { t } = useTranslation(['settings']);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const refreshSnapshot = useRefreshAccountSnapshot();
  const [snapshotRefreshTaskId, setSnapshotRefreshTaskId] = useState<
    string | null
  >(null);

  const activeAccountSnapshotTaskId = isAccountSnapshotRefreshActive(
    account?.snapshot_refresh_status
  )
    ? account?.snapshot_refresh_task_id
    : undefined;
  const trackedSnapshotRefreshTaskId =
    snapshotRefreshTaskId ?? activeAccountSnapshotTaskId ?? null;
  const snapshotRefreshStatus = useAccountSnapshotRefreshStatus(
    accountId ?? 0,
    trackedSnapshotRefreshTaskId,
    {
      enabled: accountId !== null && Boolean(trackedSnapshotRefreshTaskId),
    }
  );
  const trackedSnapshotRefreshStatus =
    snapshotRefreshStatus.data?.status ??
    (trackedSnapshotRefreshTaskId
      ? account?.snapshot_refresh_status
      : undefined);
  const isSnapshotRefreshInFlight =
    refreshSnapshot.isLoading ||
    isAccountSnapshotRefreshActive(trackedSnapshotRefreshStatus);

  useEffect(() => {
    const status = snapshotRefreshStatus.data?.status;
    if (!status || isAccountSnapshotRefreshActive(status)) return;

    queryClient.invalidateQueries({
      queryKey: ['accounts'],
      refetchType: 'active',
    });
  }, [queryClient, snapshotRefreshStatus.data?.status]);

  const handleRefreshSnapshot = useCallback(async () => {
    if (!account) return;
    try {
      const result = await refreshSnapshot.mutate(account.id);
      setSnapshotRefreshTaskId(result.task_id);
      showSuccess(
        t('settings:messages.snapshotRefreshQueued', 'Snapshot refresh queued')
      );
    } catch (error) {
      logger.error('Error queueing account snapshot refresh', {
        account_id: account.account_id,
        error: error instanceof Error ? error.message : String(error),
      });
      showError(
        t(
          'settings:messages.snapshotRefreshFailed',
          'Failed to queue snapshot refresh'
        )
      );
    }
  }, [account, refreshSnapshot, showError, showSuccess, t]);

  return {
    handleRefreshSnapshot,
    isSnapshotRefreshInFlight,
    trackedSnapshotRefreshStatus,
  };
}
