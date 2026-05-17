import { render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TaskStrategyTab } from '../../../src/components/tasks/detail/strategy/TaskStrategyTab';
import { TaskType } from '../../../src/types/common';
import type { StrategyCyclesResponse } from '../../../src/types/strategyVisualization';

const strategyEventsMock = vi.hoisted(() => vi.fn());
const taskTradesMock = vi.hoisted(() => vi.fn());

vi.mock('../../../src/hooks/useTaskStrategyEvents', () => ({
  useTaskStrategyEvents: strategyEventsMock,
}));

vi.mock('../../../src/hooks/useTaskTrades', () => ({
  useTaskTrades: taskTradesMock,
}));

vi.mock('../../../src/hooks/useAppSettings', () => ({
  readAppSettings: () => ({
    dateFormat: 'YYYY-MM-DD',
    decimalSeparator: '.',
    thousandsSeparator: ',',
  }),
  useAppSettings: () => ({
    settings: { dateFormat: 'YYYY-MM-DD' },
  }),
}));

vi.mock(
  '../../../src/components/tasks/detail/strategy/StrategyGroupChart',
  () => ({
    StrategyGroupChart: () => <div data-testid="strategy-group-chart" />,
  })
);

vi.mock(
  '../../../src/components/tasks/detail/strategy/StrategyGridIndicator',
  () => ({
    StrategyGridIndicator: () => <div data-testid="strategy-grid" />,
  })
);

vi.mock('../../../src/components/tasks/detail/PositionLifecycleDialog', () => ({
  PositionLifecycleDialog: () => null,
  default: () => null,
}));

const strategyCyclesResponse: StrategyCyclesResponse = {
  execution_id: 'exec-1',
  strategy_type: 'snowball',
  visualization: {
    kind: 'cycle_grid',
    cycle_statuses: true,
    grid: true,
  },
  cycles: [
    {
      cycle_id: '11111111-1111-1111-1111-111111111111',
      direction: 'long',
      status: 'active',
      started_at: '2026-01-01T00:00:00Z',
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
    pending_count: 0,
    completed_count: 0,
    total_trades: 0,
  },
  pagination: {
    page: 1,
    page_size: 50,
    total_count: 1,
    total_pages: 1,
  },
  last_tick_timestamp: '2026-01-01T00:00:00Z',
};

describe('TaskStrategyTab', () => {
  beforeEach(() => {
    strategyEventsMock.mockReset();
    strategyEventsMock.mockImplementation(
      ({ cycleId }: { cycleId?: string }) => ({
        data: cycleId ? null : strategyCyclesResponse,
        isLoading: false,
        error: null,
        refresh: vi.fn(),
      })
    );
    taskTradesMock.mockReset();
    taskTradesMock.mockReturnValue({
      trades: [],
      totalCount: 0,
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
  });

  it('requests Snowball cycles newest-first by default', () => {
    render(
      <TaskStrategyTab
        taskId="task-1"
        taskType={TaskType.BACKTEST}
        strategyType="snowball"
      />
    );

    const listCall = strategyEventsMock.mock.calls.find(
      ([options]) => !options.cycleId
    )?.[0];

    expect(listCall?.params?.cycle_sort).toBe('desc');
  });
});
