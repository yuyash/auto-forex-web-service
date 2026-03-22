import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { vi } from 'vitest';
import {
  useSupportedGranularities,
  useSupportedInstruments,
} from '../../../src/hooks/useMarketConfig';
import { marketApi } from '../../../src/services/api/market';

vi.mock('../../../src/services/api/market', () => ({
  marketApi: {
    getSupportedInstruments: vi.fn(),
    getSupportedGranularities: vi.fn(),
  },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useMarketConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns fallback instruments when the endpoint fails', async () => {
    vi.mocked(marketApi.getSupportedInstruments).mockRejectedValueOnce(
      new Error('boom')
    );

    const { result } = renderHook(() => useSupportedInstruments(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.usingFallback).toBe(true);
    expect(result.current.instruments.length).toBeGreaterThan(0);
  });

  it('filters second-based granularities and does not mark successful responses as fallback', async () => {
    vi.mocked(marketApi.getSupportedGranularities).mockResolvedValueOnce({
      granularities: [
        { value: 'S5', label: '5 Seconds' },
        { value: 'M1', label: '1 Minute' },
      ],
    });

    const { result } = renderHook(() => useSupportedGranularities(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.usingFallback).toBe(false);
    expect(result.current.granularities).toEqual([
      { value: 'M1', label: '1 Minute' },
    ]);
  });
});
