import { renderHook, act } from '@testing-library/react';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';
import { useTaskPositions } from '../../../src/hooks/useTaskPositions';
import { TaskType } from '../../../src/types/common';

vi.mock('axios', () => ({
  default: {
    request: vi.fn(),
    isAxiosError: vi.fn(() => false),
  },
}));

vi.mock('../../../src/api/apiConfig', () => ({
  apiConfig: {
    BASE: 'http://localhost:5173',
    WITH_CREDENTIALS: true,
  },
  getAuthHeaders: vi.fn().mockResolvedValue({}),
  getRequestHeaders: vi.fn().mockResolvedValue({}),
}));

describe('useTaskPositions', () => {
  const mockRequest = vi.mocked(axios.request);

  beforeEach(() => {
    vi.useFakeTimers();
    mockRequest.mockReset();
    mockRequest.mockResolvedValue({
      status: 200,
      statusText: 'OK',
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

    expect(mockRequest).toHaveBeenCalledTimes(1);
    expect(mockRequest.mock.calls[0]?.[0]?.params).toEqual(
      expect.objectContaining({
        execution_id: 'exec-1',
        page: '2',
        page_size: '25',
      })
    );

    await act(async () => {
      vi.advanceTimersByTime(1000);
      await Promise.resolve();
    });

    expect(mockRequest.mock.calls[1]?.[0]?.params).toEqual(
      expect.objectContaining({
        execution_id: 'exec-1',
        page: '2',
        page_size: '25',
      })
    );
    expect(mockRequest.mock.calls[1]?.[0]?.params).not.toHaveProperty('since');
  });
});
