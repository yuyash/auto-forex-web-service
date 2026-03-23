import { renderHook, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { queryKeys } from '../../../src/config/reactQuery';
import { useOandaHealthStatus } from '../../../src/hooks/useOandaHealthStatus';
import { healthApi } from '../../../src/services/api';
import { createQueryHookWrapper } from '../../utils/queryHookTestUtils';

vi.mock('../../../src/services/api', () => ({
  healthApi: {
    getOandaStatus: vi.fn(),
    checkOandaStatus: vi.fn(),
  },
}));

describe('useOandaHealthStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('maps the shared query-state fields for oanda status', async () => {
    vi.mocked(healthApi.getOandaStatus).mockResolvedValueOnce({
      account: { id: 1, account_id: '001', api_type: 'practice' },
      status: {
        is_available: true,
        checked_at: '2026-01-01T00:00:00Z',
      },
    });

    const { result } = renderHook(
      () =>
        useOandaHealthStatus({
          enabled: true,
          refreshIntervalMs: 30_000,
          activeCheck: false,
        }),
      { wrapper: createQueryHookWrapper().wrapper }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.isAvailable).toBe(true);
    expect(result.current.checkedAt).toBe('2026-01-01T00:00:00Z');
    expect(result.current.status).toEqual({
      is_available: true,
      checked_at: '2026-01-01T00:00:00Z',
    });
  });

  it('runs the active check when cached status is stale', async () => {
    vi.mocked(healthApi.getOandaStatus).mockResolvedValueOnce({
      account: { id: 1, account_id: '001', api_type: 'practice' },
      status: {
        is_available: false,
        checked_at: '2025-12-31T23:00:00Z',
      },
    });
    vi.mocked(healthApi.checkOandaStatus).mockResolvedValue({
      account: { id: 1, account_id: '001', api_type: 'practice' },
      status: {
        is_available: true,
        checked_at: '2026-01-01T00:00:00Z',
      },
    });

    const { result } = renderHook(
      () =>
        useOandaHealthStatus({
          enabled: true,
          refreshIntervalMs: 1_000,
          activeCheck: true,
        }),
      { wrapper: createQueryHookWrapper().wrapper }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await waitFor(() => expect(healthApi.checkOandaStatus).toHaveBeenCalled());
    await waitFor(() => expect(result.current.isAvailable).toBe(true));
    expect(result.current.checkedAt).toBe('2026-01-01T00:00:00Z');
  });

  it('does not re-check when the cached status is still fresh', async () => {
    const checkedAt = new Date().toISOString();
    const { queryClient, wrapper } = createQueryHookWrapper();
    queryClient.setQueryData(queryKeys.health.oanda(), {
      account: { id: 1, account_id: '001', api_type: 'practice' },
      status: {
        is_available: true,
        checked_at: checkedAt,
      },
    });
    vi.mocked(healthApi.getOandaStatus).mockResolvedValueOnce({
      account: { id: 1, account_id: '001', api_type: 'practice' },
      status: {
        is_available: true,
        checked_at: checkedAt,
      },
    });

    const { result } = renderHook(
      () =>
        useOandaHealthStatus({
          enabled: true,
          refreshIntervalMs: 1_000,
          activeCheck: true,
        }),
      { wrapper }
    );

    await waitFor(() => expect(result.current.isAvailable).toBe(true));
    await new Promise((resolve) => window.setTimeout(resolve, 25));

    expect(healthApi.checkOandaStatus).not.toHaveBeenCalled();
  });
});
