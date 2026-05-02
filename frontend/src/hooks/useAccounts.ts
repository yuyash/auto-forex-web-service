// React Query hooks for accounts
import { type AccountListParams } from '../services/api/accounts';
import {
  createAccountSnapshotRefreshStatusQuery,
  createAccountQuery,
  createAccountsPageQuery,
  createAccountsQuery,
} from './accountQueries';
import { usePollingPolicy } from './usePollingPolicy';
import { useTaskDetail, useTaskList } from './useTaskCollections';
import type { AccountSnapshotRefreshStatus } from '../types/strategy';

export function isAccountSnapshotRefreshActive(
  status: AccountSnapshotRefreshStatus | null | undefined
): status is Extract<AccountSnapshotRefreshStatus, 'queued' | 'running'> {
  return status === 'queued' || status === 'running';
}

// List accounts
export function useAccounts(
  params?: AccountListParams,
  options?: { enabled?: boolean }
) {
  return useTaskList(createAccountsQuery(params, options));
}

export function useAccountPage(
  params?: AccountListParams,
  options?: { enabled?: boolean }
) {
  return useTaskList(createAccountsPageQuery(params, options));
}

// Get single account
export function useAccount(id: number, options?: { enabled?: boolean }) {
  return useTaskDetail(createAccountQuery(id, options));
}

export function useAccountSnapshotRefreshStatus(
  id: number,
  taskId: string | null | undefined,
  options?: {
    enabled?: boolean;
    pollingInterval?: number;
  }
) {
  const queryTaskId = taskId ?? '';
  const pollingPolicy = usePollingPolicy({
    enabled: options?.enabled !== false && queryTaskId.length > 0,
    baseIntervalMs: options?.pollingInterval ?? 2_000,
  });
  return useTaskDetail(
    createAccountSnapshotRefreshStatusQuery(id, queryTaskId, options),
    undefined,
    {
      policy: pollingPolicy,
      shouldPoll: (data) => isAccountSnapshotRefreshActive(data?.status),
    }
  );
}
