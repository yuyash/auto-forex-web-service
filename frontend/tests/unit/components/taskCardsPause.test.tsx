import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TradingTaskCard from '../../../src/components/trading/TradingTaskCard';
import BacktestTaskCard from '../../../src/components/backtest/BacktestTaskCard';
import { TaskStatus } from '../../../src/types/common';

const {
  mockNavigate,
  mockTradingPause,
  mockBacktestPause,
  mockShowSuccess,
  mockShowError,
} = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockTradingPause: vi.fn(),
  mockBacktestPause: vi.fn(),
  mockShowSuccess: vi.fn(),
  mockShowError: vi.fn(),
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) => {
      if (key.endsWith('actions.pause')) return 'Pause';
      if (key.endsWith('toast.pausedSuccessfully'))
        return 'Paused successfully';
      return (options?.defaultValue as string | undefined) ?? key;
    },
  }),
}));

vi.mock('../../../src/hooks/useTaskPolling', () => ({
  useTaskPolling: () => ({ status: null }),
}));

vi.mock('../../../src/hooks/useStrategies', () => ({
  useStrategies: () => ({ strategies: [] }),
  getStrategyDisplayName: () => 'Strategy',
}));

vi.mock('../../../src/hooks/useTaskSummary', () => ({
  useTaskSummary: () => ({
    summary: {
      task: { progress: 42 },
    },
  }),
}));

vi.mock('../../../src/hooks/useBacktestTasks', () => ({
  invalidateBacktestTasksCache: vi.fn(),
}));

vi.mock('../../../src/hooks/useTradingTasks', () => ({
  invalidateTradingTasksCache: vi.fn(),
}));

vi.mock('../../../src/components/tasks/display/StatusBadge', () => ({
  StatusBadge: ({ status }: { status: string }) => <span>{status}</span>,
}));

vi.mock('../../../src/components/tasks/display/StatCard', () => ({
  StatCard: ({ title, value }: { title: string; value: string }) => (
    <div>
      {title}: {value}
    </div>
  ),
}));

vi.mock('../../../src/components/tasks/TaskProgress', () => ({
  TaskProgress: ({ progress }: { progress: number }) => (
    <div>Progress {progress}</div>
  ),
}));

vi.mock('../../../src/components/trading/TradingTaskActions', () => ({
  default: () => null,
}));

vi.mock('../../../src/components/backtest/BacktestTaskActions', () => ({
  default: () => null,
}));

vi.mock('../../../src/components/tasks/actions/DeleteTaskDialog', () => ({
  DeleteTaskDialog: () => null,
}));

vi.mock('../../../src/components/tasks/actions/BacktestStopDialog', () => ({
  BacktestStopDialog: () => null,
}));

vi.mock('../../../src/components/common', async () => {
  const actual = await vi.importActual('../../../src/components/common/index');
  return {
    ...actual,
    useToast: () => ({
      showSuccess: mockShowSuccess,
      showError: mockShowError,
      showWarning: vi.fn(),
      showInfo: vi.fn(),
    }),
  };
});

vi.mock('../../../src/services/api', () => ({
  tradingTasksApi: {
    start: vi.fn(),
    stop: vi.fn(),
    pause: mockTradingPause,
    resume: vi.fn(),
    restart: vi.fn(),
    delete: vi.fn(),
  },
  backtestTasksApi: {
    start: vi.fn(),
    stop: vi.fn(),
    pause: mockBacktestPause,
    resume: vi.fn(),
    restart: vi.fn(),
    delete: vi.fn(),
  },
}));

const tradingTask = {
  id: 'trading-1',
  user_id: 1,
  config_id: '1',
  config_name: 'Config',
  strategy_type: 'floor',
  instrument: 'EUR_USD',
  account_id: '2',
  account_name: 'Practice',
  account_type: 'practice' as const,
  name: 'Trading Task',
  description: 'Desc',
  status: TaskStatus.RUNNING,
  sell_on_stop: false,
  dry_run: false,
  hedging_enabled: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const backtestTask = {
  id: 'backtest-1',
  user_id: 1,
  config_id: '1',
  config_name: 'Config',
  strategy_type: 'floor',
  name: 'Backtest Task',
  description: 'Desc',
  data_source: 'oanda' as const,
  start_time: '2026-01-01T00:00:00Z',
  end_time: '2026-01-02T00:00:00Z',
  initial_balance: '10000',
  commission_per_trade: '0',
  instrument: 'EUR_USD',
  status: TaskStatus.RUNNING,
  sell_at_completion: false,
  hedging_enabled: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

describe('Task card pause actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockTradingPause.mockResolvedValue({});
    mockBacktestPause.mockResolvedValue({});
  });

  it('trading task card wires the pause button to the pause API', async () => {
    const user = userEvent.setup();

    render(<TradingTaskCard task={tradingTask} />);

    await user.click(screen.getByRole('button', { name: 'Pause' }));

    expect(mockTradingPause).toHaveBeenCalledWith('trading-1');
    expect(mockShowSuccess).toHaveBeenCalledWith('Paused successfully');
  });

  it('backtest task card wires the pause button to the pause API', async () => {
    const user = userEvent.setup();

    render(<BacktestTaskCard task={backtestTask} />);

    await user.click(screen.getByRole('button', { name: 'Pause' }));

    expect(mockBacktestPause).toHaveBeenCalledWith('backtest-1');
    expect(mockShowSuccess).toHaveBeenCalledWith('Paused successfully');
  });
});
