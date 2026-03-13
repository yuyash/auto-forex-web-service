import { renderHook, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { useWindowedCandles } from '../../../src/hooks/useWindowedCandles';
import { api } from '../../../src/api/apiClient';

vi.mock('../../../src/api/apiClient', () => ({
  api: {
    get: vi.fn(),
  },
}));

const mockGet = vi.mocked(api.get);

function iso(value: string): string {
  return new Date(value).toISOString();
}

describe('useWindowedCandles', () => {
  beforeEach(() => {
    mockGet.mockReset();
  });

  it('tracks actual data ranges separately from bridged unloaded gaps', async () => {
    mockGet.mockImplementation(async (_path, query) => {
      if (query?.from_time) {
        return { candles: [] };
      }
      if (query?.before) {
        return {
          candles: [
            {
              time: iso('2026-01-09T19:00:00Z'),
              open: 1,
              high: 1,
              low: 1,
              close: 1,
            },
            {
              time: iso('2026-01-09T20:00:00Z'),
              open: 1,
              high: 1,
              low: 1,
              close: 1,
            },
            {
              time: iso('2026-01-09T21:00:00Z'),
              open: 1,
              high: 1,
              low: 1,
              close: 1,
            },
          ],
        };
      }
      if (query?.after) {
        return {
          candles: [
            {
              time: iso('2026-01-14T12:00:00Z'),
              open: 1,
              high: 1,
              low: 1,
              close: 1,
            },
            {
              time: iso('2026-01-14T13:00:00Z'),
              open: 1,
              high: 1,
              low: 1,
              close: 1,
            },
          ],
        };
      }
      return { candles: [] };
    });

    const { result } = renderHook(() =>
      useWindowedCandles({
        instrument: 'EUR_USD',
        granularity: 'H1',
        startTime: '2026-01-10T00:00:00Z',
        endTime: '2026-01-20T00:00:00Z',
        initialCount: 10,
        edgeCount: 10,
      })
    );

    await waitFor(() => expect(result.current.isInitialLoading).toBe(false));

    expect(result.current.candles).toHaveLength(5);
    expect(result.current.dataRanges).toEqual([
      {
        from: Math.floor(new Date('2026-01-09T19:00:00Z').getTime() / 1000),
        to: Math.floor(new Date('2026-01-09T21:00:00Z').getTime() / 1000),
      },
      {
        from: Math.floor(new Date('2026-01-14T12:00:00Z').getTime() / 1000),
        to: Math.floor(new Date('2026-01-14T13:00:00Z').getTime() / 1000),
      },
    ]);
  });
});
