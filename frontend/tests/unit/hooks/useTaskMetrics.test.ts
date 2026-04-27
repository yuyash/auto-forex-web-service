import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useTaskMetrics } from '../../../src/hooks/useTaskMetrics';
import { TaskType } from '../../../src/types/common';
import {
  fetchLatestMetrics,
  fetchPaginatedMetrics,
} from '../../../src/utils/fetchMetrics';

vi.mock('../../../src/utils/fetchMetrics', () => ({
  fetchLatestMetrics: vi.fn(),
  fetchPaginatedMetrics: vi.fn(),
}));

const mockFetchLatestMetrics = vi.mocked(fetchLatestMetrics);
const mockFetchPaginatedMetrics = vi.mocked(fetchPaginatedMetrics);

describe('useTaskMetrics', () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('loads and refreshes the full metric series', async () => {
    mockFetchPaginatedMetrics
      .mockResolvedValueOnce({
        count: 1,
        next: null,
        previous: null,
        data_source: 'aggregate',
        resume_cursor_timestamp: null,
        consistency_warnings: [],
        results: [{ t: 1, metrics: { current_balance: 100 } }],
      })
      .mockResolvedValueOnce({
        count: 1,
        next: null,
        previous: null,
        data_source: 'aggregate',
        resume_cursor_timestamp: '2026-01-01T00:01:00Z',
        consistency_warnings: [{ type: 'gap' }],
        results: [{ t: 2, metrics: { current_balance: 101 } }],
      });

    const { result } = renderHook(() =>
      useTaskMetrics({
        taskId: '42',
        taskType: TaskType.BACKTEST,
        interval: 5,
      })
    );

    await waitFor(() => expect(result.current.data).toHaveLength(1));
    expect(result.current.latest?.t).toBe(1);
    expect(mockFetchPaginatedMetrics).toHaveBeenCalledWith(
      expect.objectContaining({
        taskId: '42',
        taskType: TaskType.BACKTEST,
        interval: 5,
        pageSize: 500,
        maxPages: 20,
      })
    );

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.latest?.t).toBe(2);
    expect(result.current.resumeCursorTimestamp).toBe('2026-01-01T00:01:00Z');
    expect(result.current.consistencyWarnings).toEqual([{ type: 'gap' }]);
  });

  it('loads only the latest snapshot when series fetching is disabled', async () => {
    mockFetchLatestMetrics.mockResolvedValueOnce({
      data_source: 'latest',
      resume_cursor_timestamp: null,
      consistency_warnings: [],
      result: { t: 10, metrics: { total_pnl: 12.5 } },
    });

    const { result } = renderHook(() =>
      useTaskMetrics({
        taskId: '42',
        taskType: TaskType.TRADING,
        fetchSeries: false,
      })
    );

    await waitFor(() => expect(result.current.latest?.t).toBe(10));
    expect(result.current.data).toEqual([]);
    expect(mockFetchLatestMetrics).toHaveBeenCalledWith({
      taskId: '42',
      taskType: TaskType.TRADING,
      executionRunId: undefined,
    });
    expect(mockFetchPaginatedMetrics).not.toHaveBeenCalled();
  });

  it('polls incrementally from the latest loaded timestamp', async () => {
    mockFetchPaginatedMetrics
      .mockResolvedValueOnce({
        count: 1,
        next: null,
        previous: null,
        data_source: 'aggregate',
        resume_cursor_timestamp: null,
        consistency_warnings: [],
        results: [{ t: 100, metrics: { current_balance: 100 } }],
      })
      .mockResolvedValueOnce({
        count: 2,
        next: null,
        previous: null,
        data_source: 'aggregate',
        resume_cursor_timestamp: null,
        consistency_warnings: [],
        results: [
          { t: 100, metrics: { current_balance: 100 } },
          { t: 160, metrics: { current_balance: 101 } },
        ],
      });

    const { result } = renderHook(() =>
      useTaskMetrics({
        taskId: '42',
        taskType: TaskType.BACKTEST,
        pollingInterval: 10,
      })
    );

    await waitFor(() => expect(mockFetchPaginatedMetrics).toHaveBeenCalled());
    await waitFor(() => expect(result.current.latest?.t).toBe(160));

    expect(mockFetchPaginatedMetrics.mock.calls[1]?.[0]).toEqual(
      expect.objectContaining({
        since: '1970-01-01T00:01:40.000Z',
        maxPages: 2,
        existingResults: [{ t: 100, metrics: { current_balance: 100 } }],
      })
    );
  });
});
