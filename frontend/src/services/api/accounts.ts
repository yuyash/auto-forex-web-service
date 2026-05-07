import { api } from '../../api/apiClient';
import { withRetry } from '../../api/client';
import type {
  BackendAccount,
  BackendAccountSnapshotRefreshResponse,
} from './contracts';
import type { PaginatedResponse } from '../../types/common';
import type {
  Account,
  AccountSnapshotRefreshStatus,
  AccountUpsertData,
} from '../../types/strategy';

export type AccountSnapshotState = 'failed' | 'stale' | 'healthy';

export interface AccountListParams {
  page?: number;
  page_size?: number;
  search?: string;
  ordering?: string;
  created_from?: string;
  created_to?: string;
  snapshot_refresh_status?: AccountSnapshotRefreshStatus;
  snapshot_state?: AccountSnapshotState;
}

interface PaginatedAccounts {
  count: number;
  next: string | null;
  previous: string | null;
  results: BackendAccount[];
}

function toAccount(account: BackendAccount): Account {
  return {
    ...account,
    id: account.id ?? 0,
    account_id: account.account_id,
    api_type: account.api_type ?? 'practice',
    currency: account.currency ?? 'USD',
    balance: account.balance ?? '0',
    margin_used: account.margin_used ?? '0',
    margin_available: account.margin_available ?? '0',
    unrealized_pnl: account.unrealized_pnl ?? '0',
    live_max_exposure_guard_enabled:
      account.live_max_exposure_guard_enabled ?? false,
    live_max_estimated_exposure_units:
      account.live_max_estimated_exposure_units ?? 200000,
    live_max_initial_order_guard_enabled:
      account.live_max_initial_order_guard_enabled ?? true,
    live_max_initial_order_units: account.live_max_initial_order_units ?? 10000,
    live_max_order_guard_enabled: account.live_max_order_guard_enabled ?? false,
    live_max_order_units: account.live_max_order_units ?? 10000,
    live_tick_latency_metric_interval_seconds:
      account.live_tick_latency_metric_interval_seconds ?? 60,
    is_active: account.is_active ?? false,
  };
}

export const accountsApi = {
  listPage: async (
    params?: AccountListParams
  ): Promise<PaginatedResponse<Account>> => {
    const response = await withRetry(() =>
      api.get<BackendAccount[] | PaginatedAccounts>(
        '/api/market/accounts/',
        params as Record<string, unknown>
      )
    );
    if (Array.isArray(response)) {
      return {
        count: response.length,
        next: null,
        previous: null,
        results: response.map(toAccount),
      };
    }
    return {
      count: response.count,
      next: response.next,
      previous: response.previous,
      results: response.results.map(toAccount),
    };
  },

  list: async (params?: AccountListParams) => {
    return (await accountsApi.listPage(params)).results;
  },

  get: async (id: number) => {
    return toAccount(
      await withRetry(() =>
        api.get<BackendAccount>(`/api/market/accounts/${id}/`)
      )
    );
  },

  refreshSnapshot: async (
    id: number
  ): Promise<BackendAccountSnapshotRefreshResponse> => {
    return withRetry(() =>
      api.post<BackendAccountSnapshotRefreshResponse>(
        `/api/market/accounts/${id}/refresh/`,
        {}
      )
    );
  },

  getSnapshotRefreshStatus: async (
    id: number,
    taskId: string
  ): Promise<BackendAccountSnapshotRefreshResponse> => {
    return withRetry(() =>
      api.get<BackendAccountSnapshotRefreshResponse>(
        `/api/market/accounts/${id}/refresh/${taskId}/`
      )
    );
  },

  create: async (data: AccountUpsertData) => {
    return toAccount(
      await withRetry(() =>
        api.post<BackendAccount>('/api/market/accounts/', data)
      )
    );
  },

  update: async (id: number, data: AccountUpsertData) => {
    return toAccount(
      await withRetry(() =>
        api.put<BackendAccount>(`/api/market/accounts/${id}/`, data)
      )
    );
  },

  delete: async (id: number) => {
    return withRetry(() => api.delete(`/api/market/accounts/${id}/`));
  },
};
