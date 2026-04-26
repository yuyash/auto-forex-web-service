import { beforeEach, describe, expect, it } from 'vitest';
import { queryClient, queryKeys } from '../../../src/config/reactQuery';
import {
  patchTaskDerivedCaches,
  patchTaskStatusCache,
  removeTaskCaches,
  upsertTaskCaches,
} from '../../../src/hooks/taskMutationCache';
import { TaskStatus, TaskType } from '../../../src/types/common';
import type {
  PaginatedResponse,
  TaskExecution,
  TradingTask,
} from '../../../src/types';
import type { StrategyCyclesResponse } from '../../../src/types/strategyVisualization';

function buildTradingTask(overrides?: Partial<TradingTask>): TradingTask {
  return {
    id: 'task-1',
    user_id: 1,
    config_id: 'config-1',
    config_name: 'Config',
    strategy_type: 'snowball',
    instrument: 'USD_JPY',
    account_id: 'account-1',
    account_name: 'Practice',
    account_type: 'practice',
    name: 'Task',
    description: 'desc',
    status: TaskStatus.RUNNING,
    sell_on_stop: false,
    dry_run: false,
    hedging_enabled: false,
    created_at: '2026-03-22T00:00:00Z',
    updated_at: '2026-03-22T00:00:00Z',
    ...overrides,
  };
}

function buildTradingPage(
  results: TradingTask[],
  count = results.length
): PaginatedResponse<TradingTask> {
  return {
    count,
    next: null,
    previous: null,
    results,
  };
}

function buildExecutionPage(
  results: TaskExecution[],
  count = results.length
): PaginatedResponse<TaskExecution> {
  return {
    count,
    next: null,
    previous: null,
    results,
  };
}

describe('taskMutationCache', () => {
  beforeEach(() => {
    queryClient.clear();
  });

  it('patches strategy event execution context without dropping the cached view model', () => {
    const queryKey = queryKeys.taskResources.strategyEvents(
      TaskType.TRADING,
      'task-1'
    );
    const summaryKey = queryKeys.taskResources.summary(
      TaskType.TRADING,
      'task-1'
    );
    const logComponentsKey = queryKeys.taskResources.logComponents(
      TaskType.TRADING,
      'task-1'
    );
    const executionsKey = queryKeys.tradingTasks.executions('task-1');
    queryClient.setQueryData<StrategyCyclesResponse>(queryKey, {
      execution_id: 'run-old',
      cycles: [],
      summary: {
        cycle_count: 0,
        active_count: 0,
        pending_count: 0,
        completed_count: 0,
        total_trades: 0,
      },
    });
    queryClient.setQueryData(summaryKey, {
      task: { status: TaskStatus.CREATED },
    });
    queryClient.setQueryData(logComponentsKey, ['engine', 'orders']);
    queryClient.setQueryData(executionsKey, buildExecutionPage([]));

    patchTaskDerivedCaches('trading', {
      ...buildTradingTask(),
      latest_execution: {
        id: 'run-new',
        execution_number: 2,
        status: TaskStatus.RUNNING,
        progress: 10,
        started_at: '2026-03-22T00:00:00Z',
      },
    });

    expect(
      queryClient.getQueryData<StrategyCyclesResponse>(queryKey)
    ).toMatchObject({
      execution_id: 'run-new',
    });
    expect(queryClient.getQueryData(summaryKey)).toMatchObject({
      task: { status: TaskStatus.RUNNING },
    });
    expect(queryClient.getQueryData(logComponentsKey)).toEqual([]);
    expect(
      queryClient.getQueryData<PaginatedResponse<TaskExecution>>(executionsKey)
        ?.results?.[0]
    ).toMatchObject({
      id: 'run-new',
      status: TaskStatus.RUNNING,
    });
  });

  it('clears strategy visualization data when a task returns to created', () => {
    const queryKey = queryKeys.taskResources.strategyEvents(
      TaskType.BACKTEST,
      'task-2'
    );
    queryClient.setQueryData<StrategyCyclesResponse>(queryKey, {
      execution_id: 'run-old',
      cycles: [
        {
          cycle_id: 'c-1',
          direction: 'buy',
          status: 'active',
          started_at: null,
          ended_at: null,
          trade_count: 0,
          open_count: 0,
          close_count: 0,
          trades: [],
        },
      ],
      summary: {
        cycle_count: 1,
        active_count: 1,
        completed_count: 0,
        total_trades: 0,
      },
    });

    patchTaskDerivedCaches('backtest', {
      id: 'task-2',
      user_id: 1,
      config_id: 'config-1',
      config_name: 'Config',
      strategy_type: 'snowball',
      name: 'Task',
      description: 'desc',
      data_source: 'oanda',
      start_time: '2026-03-22T00:00:00Z',
      end_time: '2026-03-22T01:00:00Z',
      initial_balance: '10000',
      commission_per_trade: '0',
      instrument: 'USD_JPY',
      status: TaskStatus.CREATED,
      sell_at_completion: false,
      hedging_enabled: false,
      created_at: '2026-03-22T00:00:00Z',
      updated_at: '2026-03-22T00:00:00Z',
    });

    expect(
      queryClient.getQueryData<StrategyCyclesResponse>(queryKey)
    ).toMatchObject({
      execution_id: null,
      cycles: [],
      summary: {
        cycle_count: 0,
        active_count: 0,
        pending_count: 0,
        completed_count: 0,
        total_trades: 0,
      },
    });
  });

  it('re-sorts cached task lists when an updated task changes ordering', () => {
    const listKey = queryKeys.tradingTasks.list({ ordering: 'name' });
    const detailKey = queryKeys.tradingTasks.detail('task-1');
    queryClient.setQueryData<PaginatedResponse<TradingTask>>(
      listKey,
      buildTradingPage([
        buildTradingTask({ id: 'task-2', name: 'Zulu' }),
        buildTradingTask({ id: 'task-1', name: 'Task' }),
      ])
    );
    queryClient.setQueryData<TradingTask | null>(
      detailKey,
      buildTradingTask({ id: 'task-1', name: 'Task' })
    );

    upsertTaskCaches(
      'trading',
      buildTradingTask({ id: 'task-1', name: 'Alpha' })
    );

    expect(
      queryClient
        .getQueryData<PaginatedResponse<TradingTask>>(listKey)
        ?.results.map((task) => task.name)
    ).toEqual(['Alpha', 'Zulu']);
    expect(queryClient.getQueryData<TradingTask>(detailKey)).toEqual(
      expect.objectContaining({ name: 'Alpha' })
    );
  });

  it('removes cached tasks that stop matching a filtered status list', () => {
    const listKey = queryKeys.tradingTasks.list({ status: TaskStatus.RUNNING });
    const detailKey = queryKeys.tradingTasks.detail('task-1');
    queryClient.setQueryData<PaginatedResponse<TradingTask>>(
      listKey,
      buildTradingPage([
        buildTradingTask({ id: 'task-1', status: TaskStatus.RUNNING }),
      ])
    );
    queryClient.setQueryData<TradingTask | null>(
      detailKey,
      buildTradingTask({ id: 'task-1', status: TaskStatus.RUNNING })
    );

    patchTaskStatusCache('trading', 'task-1', TaskStatus.STOPPED);

    expect(
      queryClient.getQueryData<PaginatedResponse<TradingTask>>(listKey)
    ).toEqual(buildTradingPage([], 0));
    expect(queryClient.getQueryData<TradingTask>(detailKey)).toEqual(
      expect.objectContaining({ status: TaskStatus.STOPPED })
    );
  });

  it('re-inserts matching tasks into first-page filtered caches', () => {
    const listKey = queryKeys.tradingTasks.list({
      status: TaskStatus.RUNNING,
      ordering: 'name',
    });
    queryClient.setQueryData<PaginatedResponse<TradingTask>>(
      listKey,
      buildTradingPage([buildTradingTask({ id: 'task-2', name: 'Zulu' })], 1)
    );

    upsertTaskCaches(
      'trading',
      buildTradingTask({
        id: 'task-1',
        name: 'Alpha',
        status: TaskStatus.RUNNING,
      })
    );

    expect(
      queryClient
        .getQueryData<PaginatedResponse<TradingTask>>(listKey)
        ?.results.map((task) => task.name)
    ).toEqual(['Alpha', 'Zulu']);
  });

  it('removes detail and derived caches when a task is removed', async () => {
    const detailKey = queryKeys.tradingTasks.detail('task-1');
    const summaryKey = queryKeys.taskResources.summary(
      TaskType.TRADING,
      'task-1'
    );
    queryClient.setQueryData<TradingTask | null>(detailKey, buildTradingTask());
    queryClient.setQueryData(summaryKey, { status: TaskStatus.RUNNING });

    await removeTaskCaches('trading', 'task-1');

    expect(queryClient.getQueryData(detailKey)).toBeUndefined();
    expect(queryClient.getQueryData(summaryKey)).toBeUndefined();
  });
});
