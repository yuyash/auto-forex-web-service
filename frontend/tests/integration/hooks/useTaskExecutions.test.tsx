import { renderHook, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { useTaskExecution } from '../../../src/hooks/useTaskExecutions';
import { TaskType } from '../../../src/types/common';
import { backtestTasksApi, tradingTasksApi } from '../../../src/services/api';
import { createQueryHookWrapper } from '../../utils/queryHookTestUtils';

vi.mock('../../../src/services/api', () => ({
  backtestTasksApi: {
    getExecution: vi.fn(),
  },
  tradingTasksApi: {
    getExecution: vi.fn(),
  },
}));

describe('useTaskExecution', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches a single backtest execution from the dedicated endpoint', async () => {
    vi.mocked(backtestTasksApi.getExecution).mockResolvedValueOnce({
      id: 'exec-1',
      task_type: 'backtest',
      task_id: 'task-1',
      execution_number: 'exec-1',
      status: 'completed',
      progress: 100,
      started_at: '2026-01-01T00:00:00Z',
      completed_at: '2026-01-01T00:05:00Z',
      error_message: null,
      error_code: null,
      duration: 300,
      created_at: '2026-01-01T00:00:00Z',
    });

    const { result } = renderHook(
      () => useTaskExecution('task-1', 'exec-1', TaskType.BACKTEST),
      { wrapper: createQueryHookWrapper().wrapper }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(backtestTasksApi.getExecution).toHaveBeenCalledWith(
      'task-1',
      'exec-1'
    );
    expect(result.current.data?.id).toBe('exec-1');
  });

  it('fetches a single trading execution from the dedicated endpoint', async () => {
    vi.mocked(tradingTasksApi.getExecution).mockResolvedValueOnce({
      id: 'exec-2',
      task_type: 'trading',
      task_id: 'task-2',
      execution_number: 'exec-2',
      status: 'running',
      progress: 12,
      started_at: '2026-01-01T00:00:00Z',
      completed_at: null,
      error_message: null,
      error_code: null,
      duration: null,
      created_at: '2026-01-01T00:00:00Z',
    });

    const { result } = renderHook(
      () => useTaskExecution('task-2', 'exec-2', TaskType.TRADING),
      { wrapper: createQueryHookWrapper().wrapper }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(tradingTasksApi.getExecution).toHaveBeenCalledWith(
      'task-2',
      'exec-2'
    );
    expect(result.current.data?.status).toBe('running');
  });
});
