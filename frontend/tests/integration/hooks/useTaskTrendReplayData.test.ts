import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, expect, it, beforeEach, vi } from 'vitest';

import { TaskType } from '../../../src/types/common';
import { useTaskTrendReplayData } from '../../../src/components/tasks/detail/taskTrendPanel/useTaskTrendReplayData';

const { mockFetchLatestTradesPage, mockFetchTradesSince } = vi.hoisted(() => ({
  mockFetchLatestTradesPage: vi.fn(),
  mockFetchTradesSince: vi.fn(),
}));

vi.mock('../../../src/utils/replayTradeFetchers', () => ({
  fetchLatestTradesPage: mockFetchLatestTradesPage,
  fetchTradesInRange: vi.fn(),
  fetchTradesSince: mockFetchTradesSince,
}));

describe('useTaskTrendReplayData', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('surfaces refresh errors while keeping the latest loaded trades', async () => {
    mockFetchLatestTradesPage.mockResolvedValue([
      {
        id: 'trade-1',
        timestamp: '2026-03-20T00:00:00Z',
        updated_at: '2026-03-20T00:00:01Z',
        direction: 'buy',
        units: '1000',
        price: '150.10',
      },
    ]);
    mockFetchTradesSince
      .mockResolvedValueOnce([])
      .mockRejectedValueOnce(new Error('incremental refresh failed'));
    const refreshTailCandles = vi.fn().mockResolvedValue(0);

    const { result } = renderHook(() =>
      useTaskTrendReplayData({
        taskId: 'task-1',
        taskType: TaskType.BACKTEST,
        executionRunId: 'run-1',
        instrument: 'USD_JPY',
        latestExecution: { total_trades: 1 },
        enableRealTimeUpdates: false,
        pollingIntervalMs: 1000,
        refreshTailCandles,
      })
    );

    await waitFor(() => {
      expect(result.current.trades).toHaveLength(1);
    });
    await waitFor(() => {
      expect(result.current.errorMessage).toBeNull();
    });

    await act(async () => {
      await result.current.fetchReplayData();
    });

    await act(async () => {
      await result.current.fetchReplayData();
    });

    expect(result.current.trades).toHaveLength(1);
    expect(result.current.errorMessage).toBe('incremental refresh failed');
  });
});
