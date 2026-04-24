import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { backtestTasksApi, tradingTasksApi } from '../../../src/services/api';
import { useBacktestTask } from '../../../src/hooks/useBacktestTasks';
import { useTaskExecutions } from '../../../src/hooks/useTaskExecutions';
import { TaskType } from '../../../src/types/common';
import { createQueryHookWrapper } from '../../utils/queryHookTestUtils';

vi.mock('../../../src/services/api', () => ({
  backtestTasksApi: {
    get: vi.fn(),
    getExecutions: vi.fn(),
  },
  tradingTasksApi: {
    get: vi.fn(),
    getExecutions: vi.fn(),
  },
}));

vi.mock('../../../src/hooks/useDocumentVisibility', () => ({
  useDocumentVisibility: () => true,
}));

vi.mock('../../../src/hooks/useOnlineStatus', () => ({
  useOnlineStatus: () => true,
}));

async function flushAsyncWork() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
    await Promise.resolve();
  });
}

describe('task polling hooks', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(async () => {
    await act(async () => {
      vi.runOnlyPendingTimers();
    });
    vi.useRealTimers();
  });

  it('polls task detail while status is running and stops after completion', async () => {
    vi.mocked(backtestTasksApi.get)
      .mockResolvedValueOnce({
        id: 'task-1',
        name: 'Backtest Task',
        status: 'running',
      } as never)
      .mockResolvedValueOnce({
        id: 'task-1',
        name: 'Backtest Task',
        status: 'completed',
      } as never);

    const { result } = renderHook(
      () =>
        useBacktestTask('task-1', {
          enablePolling: true,
          pollingInterval: 1000,
        }),
      { wrapper: createQueryHookWrapper({ gcTime: Infinity }).wrapper }
    );

    await flushAsyncWork();
    expect(backtestTasksApi.get).toHaveBeenCalledTimes(1);
    expect(result.current.data?.status).toBe('running');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    await flushAsyncWork();
    expect(result.current.data?.status).toBe('completed');
    expect(backtestTasksApi.get).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(backtestTasksApi.get).toHaveBeenCalledTimes(2);
  });

  it('polls execution history while a run is active and stops after it settles', async () => {
    vi.mocked(tradingTasksApi.getExecutions)
      .mockResolvedValueOnce({
        count: 1,
        next: null,
        previous: null,
        results: [{ id: 'exec-1', status: 'running' }],
      } as never)
      .mockResolvedValueOnce({
        count: 1,
        next: null,
        previous: null,
        results: [{ id: 'exec-1', status: 'completed' }],
      } as never);
    vi.mocked(tradingTasksApi.getExecutions).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [{ id: 'exec-1', status: 'completed' }],
    } as never);

    const { result } = renderHook(
      () =>
        useTaskExecutions(
          'task-2',
          TaskType.TRADING,
          { page: 1, page_size: 10 },
          { enablePolling: true, pollingInterval: 1000 }
        ),
      { wrapper: createQueryHookWrapper({ gcTime: Infinity }).wrapper }
    );

    await flushAsyncWork();
    expect(tradingTasksApi.getExecutions).toHaveBeenCalledTimes(1);
    expect(result.current.data?.results[0]?.status).toBe('running');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    await flushAsyncWork();
    expect(result.current.data?.results[0]?.status).toBe('completed');
    expect(tradingTasksApi.getExecutions).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    await flushAsyncWork();

    // Polling continues regardless of execution status
    expect(tradingTasksApi.getExecutions).toHaveBeenCalledTimes(3);
  });
});
