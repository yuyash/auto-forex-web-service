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
import { accountsApi } from '../../../src/services/api/accounts';
import {
  fetchPaginatedTaskResource,
  fetchTaskResourceObject,
  fetchTaskResourcePage,
} from '../../../src/services/api/taskResources';
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

  it('forwards account list params to the accounts endpoint', async () => {
    mockApi.get.mockResolvedValue([
      {
        id: 1,
        account_id: '001-011-1234567-001',
        api_type: 'practice',
        currency: 'USD',
        balance: '1000.00',
        margin_used: '0.00',
        margin_available: '1000.00',
        unrealized_pnl: '0.00',
        is_active: true,
      },
    ]);

    await expect(
      accountsApi.list({ page: 2, page_size: 50, search: 'practice' })
    ).resolves.toMatchObject([
      {
        id: 1,
        account_id: '001-011-1234567-001',
      },
    ]);

    expect(mockApi.get).toHaveBeenCalledWith('/api/market/accounts/', {
      page: 2,
      page_size: 50,
      search: 'practice',
    });
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

  it('loads task resource pages through the shared task resource service', async () => {
    mockApi.get.mockResolvedValueOnce({
      count: 1,
      next: null,
      previous: null,
      results: [{ id: 'log-1', message: 'hello' }],
    });

    await expect(
      fetchTaskResourcePage('backtest', 'task-1', 'logs', { page: '1' })
    ).resolves.toEqual({
      count: 1,
      next: null,
      previous: null,
      results: [{ id: 'log-1', message: 'hello' }],
    });

    expect(mockApi.get).toHaveBeenCalledWith(
      '/api/trading/tasks/backtest/task-1/logs/',
      { page: '1' }
    );
  });

  it('follows pagination links when loading all task resource pages', async () => {
    mockApi.get
      .mockResolvedValueOnce({
        count: 2,
        next: 'http://localhost/api/trading/tasks/backtest/task-1/trades/?page=2',
        previous: null,
        results: [{ id: 'trade-1' }],
      })
      .mockResolvedValueOnce({
        count: 2,
        next: null,
        previous:
          'http://localhost/api/trading/tasks/backtest/task-1/trades/?page=1',
        results: [{ id: 'trade-2' }],
      });

    await expect(
      fetchPaginatedTaskResource('backtest', 'task-1', 'trades', {
        page: 1,
      })
    ).resolves.toEqual([{ id: 'trade-1' }, { id: 'trade-2' }]);

    expect(mockApi.get).toHaveBeenNthCalledWith(
      2,
      '/api/trading/tasks/backtest/task-1/trades/',
      { page: '2' }
    );
  });

  it('loads task resource objects through the shared task resource service', async () => {
    mockApi.get.mockResolvedValue({
      components: ['engine', 'strategy'],
    });

    await expect(
      fetchTaskResourceObject('trading', 'task-9', 'log-components')
    ).resolves.toEqual({
      components: ['engine', 'strategy'],
    });

    expect(mockApi.get).toHaveBeenCalledWith(
      '/api/trading/tasks/trading/task-9/log-components/',
      undefined
    );
  });
});
