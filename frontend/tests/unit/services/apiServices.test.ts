import { beforeEach, describe, expect, it, vi } from 'vitest';

const { mockApi, mockWithRetry } = vi.hoisted(() => ({
  mockApi: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
  mockWithRetry: vi.fn(async <T>(fn: () => Promise<T>): Promise<T> => fn()),
}));

vi.mock('../../../src/api/apiClient', () => ({
  api: mockApi,
}));

vi.mock('../../../src/api/client', () => ({
  withRetry: mockWithRetry,
}));

import { backtestTasksApi } from '../../../src/services/api/backtestTasks';
import { configurationsApi } from '../../../src/services/api/configurations';
import { tradingTasksApi } from '../../../src/services/api/tradingTasks';

describe('API service contracts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads configuration usage from the dedicated config tasks endpoint', async () => {
    mockApi.get.mockResolvedValue({
      results: [
        { id: 'task-1', task_type: 'backtest', name: 'BT', status: 'RUNNING' },
      ],
    });

    await expect(configurationsApi.getTasks('cfg-1')).resolves.toEqual([
      { id: 'task-1', task_type: 'backtest', name: 'BT', status: 'RUNNING' },
    ]);

    expect(mockApi.get).toHaveBeenCalledWith(
      '/api/trading/strategy-configs/cfg-1/tasks/'
    );
  });

  it('sends stop mode for trading task stop requests', async () => {
    mockApi.post.mockResolvedValue({
      message: 'Task stop requested',
      task_id: 'task-1',
      mode: 'immediate',
      status: 'STOPPING',
    });

    await expect(
      tradingTasksApi.stop('task-1', 'immediate')
    ).resolves.toMatchObject({
      mode: 'immediate',
    });

    expect(mockApi.post).toHaveBeenCalledWith(
      '/api/trading/tasks/trading/task-1/stop/',
      { mode: 'immediate' }
    );
  });

  it('maps raw trading action responses to frontend task shape', async () => {
    mockApi.post.mockResolvedValue({
      id: 'trade-1',
      user_id: 1,
      config_id: 'cfg-1',
      config_name: 'Config',
      strategy_type: 'grid',
      instrument: 'EUR_USD',
      account_id: 12,
      account_name: 'Primary',
      account_type: 'practice',
      name: 'Live task',
      description: '',
      sell_on_stop: false,
      dry_run: true,
      hedging_enabled: false,
      pip_size: '0.0001',
      status: 'RUNNING',
      execution_id: 'exec-1',
      started_at: '2026-03-21T10:00:00Z',
      completed_at: null,
      error_message: null,
      has_strategy_state: true,
      can_resume: true,
      created_at: '2026-03-21T09:00:00Z',
      updated_at: '2026-03-21T10:00:00Z',
    });

    await expect(tradingTasksApi.start('trade-1')).resolves.toMatchObject({
      id: 'trade-1',
      account_id: '12',
      status: 'RUNNING',
      has_strategy_state: true,
      can_resume: true,
      execution_id: 'exec-1',
    });

    expect(mockApi.post).toHaveBeenCalledWith(
      '/api/trading/tasks/trading/trade-1/start/',
      {}
    );
  });

  it('maps raw backtest action responses without a results envelope', async () => {
    mockApi.post.mockResolvedValue({
      id: 'bt-1',
      user_id: 1,
      config_id: 'cfg-1',
      config_name: 'Config',
      strategy_type: 'grid',
      name: 'Backtest',
      description: '',
      data_source: 'historical',
      start_time: '2026-01-01T00:00:00Z',
      end_time: '2026-01-31T00:00:00Z',
      initial_balance: '10000.00',
      commission_per_trade: '0.00',
      pip_size: '0.0001',
      instrument: 'EUR_USD',
      hedging_enabled: true,
      status: 'RUNNING',
      execution_id: 'exec-2',
      started_at: '2026-03-21T10:00:00Z',
      completed_at: null,
      error_message: null,
      created_at: '2026-03-21T09:00:00Z',
      updated_at: '2026-03-21T10:00:00Z',
    });

    await expect(backtestTasksApi.start('bt-1')).resolves.toMatchObject({
      id: 'bt-1',
      status: 'RUNNING',
      execution_id: 'exec-2',
    });

    expect(mockApi.post).toHaveBeenCalledWith(
      '/api/trading/tasks/backtest/bt-1/start/',
      {}
    );
  });
});
