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
      if (
        query?.from_time === '2026-01-12T01:00:00.000Z' &&
        query?.to_time === '2026-01-12T11:00:00.000Z'
      ) {
        return { candles: [] };
      }
      if (
        query?.from_time === '2026-01-11T15:00:00.000Z' &&
        query?.to_time === '2026-01-12T01:00:00.000Z'
      ) {
        return {
          candles: [
            {
              time: iso('2026-01-11T19:00:00Z'),
              open: 1,
              high: 1,
              low: 1,
              close: 1,
            },
            {
              time: iso('2026-01-11T20:00:00Z'),
              open: 1,
              high: 1,
              low: 1,
              close: 1,
            },
            {
              time: iso('2026-01-11T21:00:00Z'),
              open: 1,
              high: 1,
              low: 1,
              close: 1,
            },
          ],
        };
      }
      if (
        query?.from_time === '2026-01-12T11:00:00.000Z' &&
        query?.to_time === '2026-01-12T21:00:00.000Z'
      ) {
        return {
          candles: [
            {
              time: iso('2026-01-12T12:00:00Z'),
              open: 1,
              high: 1,
              low: 1,
              close: 1,
            },
            {
              time: iso('2026-01-12T13:00:00Z'),
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
        initialFocusTime: '2026-01-12T08:00:00Z',
        initialCount: 10,
        edgeCount: 10,
      })
    );

    await waitFor(() => expect(result.current.isInitialLoading).toBe(false));

    expect(result.current.candles).toHaveLength(5);
    expect(result.current.dataRanges).toEqual([
      {
        from: Math.floor(new Date('2026-01-11T19:00:00Z').getTime() / 1000),
        to: Math.floor(new Date('2026-01-11T21:00:00Z').getTime() / 1000),
      },
      {
        from: Math.floor(new Date('2026-01-12T12:00:00Z').getTime() / 1000),
        to: Math.floor(new Date('2026-01-12T13:00:00Z').getTime() / 1000),
      },
    ]);
  });

  it('does not request candles with a future to_time', async () => {
    const now = new Date();
    const start = new Date(now.getTime() - 4 * 60 * 60 * 1000);
    start.setUTCMinutes(0, 0, 0);

    mockGet.mockResolvedValue({
      candles: [],
    });

    renderHook(() =>
      useWindowedCandles({
        instrument: 'USD_JPY',
        granularity: 'H1',
        startTime: start.toISOString(),
        endTime: '2099-03-23T06:00:00.000Z',
        initialCount: 10,
        edgeCount: 10,
      })
    );

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalled();
    });

    const candleRequest = mockGet.mock.calls.find(
      ([path, query]) => path === '/api/market/candles/' && query?.from_time
    );

    expect(candleRequest?.[1]).toMatchObject({
      from_time: start.toISOString(),
    });
    const requestedTo = new Date(String(candleRequest?.[1]?.to_time));
    const flooredNow = new Date(now);
    flooredNow.setUTCMinutes(0, 0, 0);
    expect(requestedTo.getTime()).toBeLessThanOrEqual(flooredNow.getTime());
  });

  it('does not clear existing candles when only initialFocusTime changes', async () => {
    mockGet.mockResolvedValue({
      candles: [
        {
          time: iso('2026-03-23T00:00:00Z'),
          open: 1,
          high: 1,
          low: 1,
          close: 1,
        },
        {
          time: iso('2026-03-23T01:00:00Z'),
          open: 2,
          high: 2,
          low: 2,
          close: 2,
        },
      ],
    });

    const { result, rerender } = renderHook(
      ({ initialFocusTime }: { initialFocusTime?: string }) =>
        useWindowedCandles({
          instrument: 'USD_JPY',
          granularity: 'H1',
          initialFocusTime,
          initialCount: 10,
          edgeCount: 10,
        }),
      {
        initialProps: {
          initialFocusTime: '2026-03-23T01:00:00Z',
        },
      }
    );

    await waitFor(() => expect(result.current.isInitialLoading).toBe(false));
    expect(result.current.candles).toHaveLength(2);

    rerender({
      initialFocusTime: '2026-03-23T02:00:00Z',
    });

    expect(result.current.isInitialLoading).toBe(false);
    expect(result.current.candles).toHaveLength(2);
    expect(mockGet).toHaveBeenCalledTimes(1);
  });
});
