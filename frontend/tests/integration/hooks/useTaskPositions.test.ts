import { renderHook, act } from '@testing-library/react';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';
import { useTaskPositions } from '../../../src/hooks/useTaskPositions';
import { TaskType } from '../../../src/types/common';

vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    isAxiosError: vi.fn(() => false),
  },
}));

vi.mock('../../../src/api/apiConfig', () => ({
  apiConfig: {
    BASE: 'http://localhost:5173',
    WITH_CREDENTIALS: true,
  },
  resolveToken: vi.fn().mockResolvedValue(null),
}));

describe('useTaskPositions', () => {
  const mockGet = vi.mocked(axios.get);

  beforeEach(() => {
    vi.useFakeTimers();
    mockGet.mockReset();
    mockGet.mockResolvedValue({
      data: {
        count: 50,
        next: 'next',
        previous: 'previous',
        results: [
          {
            id: 'pos-1',
            instrument: 'EUR_USD',
            direction: 'long',
            units: 1000,
            entry_price: '1.1000',
            entry_time: '2026-03-13T18:44:00Z',
            is_open: true,
            updated_at: '2026-03-13T18:44:14.276828Z',
          },
        ],
      },
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('falls back to full polling for pages after the first', async () => {
    const { result } = renderHook(() =>
      useTaskPositions({
        taskId: 'task-1',
        taskType: TaskType.BACKTEST,
        executionRunId: 'exec-1',
        page: 2,
        pageSize: 25,
        enableRealTimeUpdates: true,
        refreshInterval: 1000,
      })
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.isLoading).toBe(false);

    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(mockGet.mock.calls[0]?.[1]?.params).toEqual({
      execution_id: 'exec-1',
      page: '2',
      page_size: '25',
    });

    await act(async () => {
      vi.advanceTimersByTime(1000);
      await Promise.resolve();
    });

    expect(mockGet.mock.calls[1]?.[1]?.params).toEqual({
      execution_id: 'exec-1',
      page: '2',
      page_size: '25',
    });
    expect(mockGet.mock.calls[1]?.[1]?.params).not.toHaveProperty('since');
  });
});
