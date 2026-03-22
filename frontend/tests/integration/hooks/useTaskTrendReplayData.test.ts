import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, expect, it, beforeEach, vi } from 'vitest';

import { TaskType } from '../../../src/types/common';
import { useTaskTrendReplayData } from '../../../src/components/tasks/detail/taskTrendPanel/useTaskTrendReplayData';

const { mockFetchTaskTrendReplay } = vi.hoisted(() => ({
  mockFetchTaskTrendReplay: vi.fn(),
}));

vi.mock('../../../src/services/api/taskResources', () => ({
  fetchTaskTrendReplay: mockFetchTaskTrendReplay,
}));

describe('useTaskTrendReplayData', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('surfaces refresh errors while keeping the latest loaded trades', async () => {
    mockFetchTaskTrendReplay
      .mockResolvedValueOnce({
        trades: [
          {
            id: 'trade-1',
            timestamp: '2026-03-20T00:00:00Z',
            updated_at: '2026-03-20T00:00:01Z',
            direction: 'buy',
            units: '1000',
            price: '150.10',
            instrument: 'USD_JPY',
          },
        ],
        positions: [],
        trade_markers: [
          {
            trade_id: 'trade-1',
            timestamp: '2026-03-20T00:00:00Z',
            direction: 'long',
            action: 'open',
            lots: 1,
            label: 'OPEN LONG 1L',
          },
        ],
        meta: {
          mode: 'latest',
          page: 1,
          page_size: 1000,
          total_trades: 1,
          returned_trades: 1,
          has_more_trades: false,
          latest_trade_updated_at: '2026-03-20T00:00:01Z',
          range_from: null,
          range_to: null,
        },
      })
      .mockResolvedValueOnce({
        trades: [],
        positions: [],
        trade_markers: [],
        meta: {
          mode: 'latest',
          page: 1,
          page_size: 1000,
          total_trades: 1,
          returned_trades: 0,
          has_more_trades: false,
          latest_trade_updated_at: '2026-03-20T00:00:01Z',
          range_from: null,
          range_to: null,
        },
      })
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
