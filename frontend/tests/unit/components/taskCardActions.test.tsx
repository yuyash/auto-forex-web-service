import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TradingTaskCard from '../../../src/components/trading/TradingTaskCard';
import BacktestTaskCard from '../../../src/components/backtest/BacktestTaskCard';
import { TaskStatus } from '../../../src/types/common';

const {
  mockNavigate,
  mockTradingStart,
  mockTradingStop,
  mockTradingPause,
  mockTradingResume,
  mockTradingRestart,
  mockBacktestStart,
  mockBacktestStop,
  mockBacktestPause,
  mockBacktestResume,
  mockBacktestRestart,
  mockShowSuccess,
  mockShowError,
} = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockTradingStart: vi.fn(),
  mockTradingStop: vi.fn(),
  mockTradingPause: vi.fn(),
  mockTradingResume: vi.fn(),
  mockTradingRestart: vi.fn(),
  mockBacktestStart: vi.fn(),
  mockBacktestStop: vi.fn(),
  mockBacktestPause: vi.fn(),
  mockBacktestResume: vi.fn(),
  mockBacktestRestart: vi.fn(),
  mockShowSuccess: vi.fn(),
  mockShowError: vi.fn(),
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) => {
      const map: Record<string, string> = {
        'actions.start': 'Start',
        'actions.stop': 'Stop',
        'actions.pause': 'Pause',
        'actions.resume': 'Resume',
        'actions.restart': 'Restart',
        'common:actions.viewDetails': 'View Details',
        'trading:toast.startedSuccessfully': 'Trading started successfully',
        'trading:toast.stoppedSuccessfully': 'Trading stopped successfully',
        'trading:toast.pausedSuccessfully': 'Trading paused successfully',
        'trading:toast.resumedSuccessfully': 'Trading resumed successfully',
        'trading:toast.restartedSuccessfully': 'Trading restarted successfully',
        'backtest:toast.startedSuccessfully': 'Backtest started successfully',
        'backtest:toast.stoppedSuccessfully': 'Backtest stopped successfully',
        'backtest:toast.pausedSuccessfully': 'Backtest paused successfully',
        'backtest:toast.resumedSuccessfully': 'Backtest resumed successfully',
        'backtest:toast.restartedSuccessfully':
          'Backtest restarted successfully',
        'common:actions.cancel': 'Cancel',
        'common:taskActionDialog.start.title': 'Start Task',
        'common:taskActionDialog.start.confirm': 'Start',
        'common:taskActionDialog.start.loading': 'Starting...',
        'common:taskActionDialog.stop.title': 'Stop Task',
        'common:taskActionDialog.stop.confirm': 'Stop',
        'common:taskActionDialog.stop.loading': 'Stopping...',
        'common:taskActionDialog.pause.title': 'Pause Task',
        'common:taskActionDialog.pause.confirm': 'Pause',
        'common:taskActionDialog.pause.loading': 'Pausing...',
        'common:taskActionDialog.resume.title': 'Resume Task',
        'common:taskActionDialog.resume.confirm': 'Resume',
        'common:taskActionDialog.resume.loading': 'Resuming...',
        'common:taskActionDialog.restart.title': 'Restart Task',
        'common:taskActionDialog.restart.confirm': 'Restart',
        'common:taskActionDialog.restart.loading': 'Restarting...',
        'taskActionDialog.start.title': 'Start Task',
        'taskActionDialog.start.confirm': 'Start',
        'taskActionDialog.start.loading': 'Starting...',
        'taskActionDialog.stop.title': 'Stop Task',
        'taskActionDialog.stop.confirm': 'Stop',
        'taskActionDialog.stop.loading': 'Stopping...',
        'taskActionDialog.stop.message': 'Are you sure you want to stop?',
        'taskActionDialog.pause.title': 'Pause Task',
        'taskActionDialog.pause.confirm': 'Pause',
        'taskActionDialog.pause.loading': 'Pausing...',
        'taskActionDialog.resume.title': 'Resume Task',
        'taskActionDialog.resume.confirm': 'Resume',
        'taskActionDialog.resume.loading': 'Resuming...',
        'taskActionDialog.restart.title': 'Restart Task',
        'taskActionDialog.restart.confirm': 'Restart',
        'taskActionDialog.restart.loading': 'Restarting...',
        'taskActionDialog.start.message': 'Are you sure you want to start?',
        'taskActionDialog.pause.message': 'Are you sure you want to pause?',
        'taskActionDialog.resume.message': 'Are you sure you want to resume?',
        'taskActionDialog.restart.message': 'Are you sure you want to restart?',
        'actions.cancel': 'Cancel',
      };
      return map[key] ?? ((options?.defaultValue as string | undefined) || key);
    },
  }),
}));

vi.mock('../../../src/hooks/useStrategies', () => ({
  useStrategies: () => ({ strategies: [] }),
  getStrategyDisplayName: () => 'Strategy',
}));

vi.mock('../../../src/hooks/useTaskSummary', () => ({
  useTaskSummary: () => ({
    summary: {
      pnl: {
        realized: 0,
        unrealized: 0,
      },
      counts: {
        openPositions: 0,
        closedPositions: 0,
      },
      execution: {
        marginRatio: null,
      },
      task: { progress: 42 },
    },
  }),
}));

vi.mock('../../../src/hooks/useBacktestTasks', () => ({
  useBacktestTask: () => ({ data: null }),
}));

vi.mock('../../../src/hooks/useTradingTasks', () => ({
  useTradingTask: () => ({ data: null }),
}));

vi.mock('../../../src/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: {
      timezone: 'UTC',
      language: 'en',
    },
  }),
}));

vi.mock('../../../src/hooks/useTradingTaskMutations', () => ({
  useStartTradingTask: () => ({ mutate: mockTradingStart, isLoading: false }),
  useStopTradingTask: () => ({ mutate: mockTradingStop, isLoading: false }),
  usePauseTradingTask: () => ({ mutate: mockTradingPause, isLoading: false }),
  useResumeTradingTask: () => ({
    mutate: mockTradingResume,
    isLoading: false,
  }),
  useRestartTradingTask: () => ({
    mutate: mockTradingRestart,
    isLoading: false,
  }),
  useDeleteTradingTask: () => ({ mutate: vi.fn(), isLoading: false }),
}));

vi.mock('../../../src/hooks/useBacktestTaskMutations', () => ({
  useStartBacktestTask: () => ({
    mutate: mockBacktestStart,
    isLoading: false,
  }),
  useStopBacktestTask: () => ({ mutate: mockBacktestStop, isLoading: false }),
  usePauseBacktestTask: () => ({
    mutate: mockBacktestPause,
    isLoading: false,
  }),
  useResumeBacktestTask: () => ({
    mutate: mockBacktestResume,
    isLoading: false,
  }),
  useRerunBacktestTask: () => ({
    mutate: mockBacktestRestart,
    isLoading: false,
  }),
  useDeleteBacktestTask: () => ({ mutate: vi.fn(), isLoading: false }),
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

vi.mock('../../../src/components/tasks/actions/StopOptionsDialog', () => ({
  StopOptionsDialog: ({
    open,
    onConfirm,
  }: {
    open: boolean;
    onConfirm: (option: 'graceful' | 'graceful_close' | 'drain') => void;
  }) =>
    open ? (
      <button type="button" onClick={() => onConfirm('graceful')}>
        Confirm Stop
      </button>
    ) : null,
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

const tradingTaskBase = {
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
  sell_on_stop: false,
  dry_run: false,
  hedging_enabled: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const backtestTaskBase = {
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
  sell_at_completion: false,
  hedging_enabled: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

describe('Task card control actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockTradingStart.mockResolvedValue({});
    mockTradingStop.mockResolvedValue({});
    mockTradingPause.mockResolvedValue({});
    mockTradingResume.mockResolvedValue({});
    mockTradingRestart.mockResolvedValue({});
    mockBacktestStart.mockResolvedValue({});
    mockBacktestStop.mockResolvedValue({});
    mockBacktestPause.mockResolvedValue({});
    mockBacktestResume.mockResolvedValue({});
    mockBacktestRestart.mockResolvedValue({});
  });

  it('trading task card starts created tasks', async () => {
    const user = userEvent.setup();

    render(
      <TradingTaskCard
        task={{ ...tradingTaskBase, status: TaskStatus.CREATED }}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Start' }));
    const confirmButtons = screen.getAllByRole('button', { name: 'Start' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    expect(mockTradingStart).toHaveBeenCalledWith('trading-1');
    expect(mockShowSuccess).toHaveBeenCalledWith(
      'Trading started successfully'
    );
  });

  it('trading task card stops running tasks', async () => {
    const user = userEvent.setup();

    render(
      <TradingTaskCard
        task={{ ...tradingTaskBase, status: TaskStatus.RUNNING }}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Stop' }));
    const confirmButtons = screen.getAllByRole('button', { name: 'Stop' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    expect(mockTradingStop).toHaveBeenCalledWith({ id: 'trading-1' });
    expect(mockShowSuccess).toHaveBeenCalledWith(
      'Trading stopped successfully'
    );
  });

  it('trading task card resumes stopped tasks', async () => {
    const user = userEvent.setup();

    render(
      <TradingTaskCard
        task={{ ...tradingTaskBase, status: TaskStatus.STOPPED }}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Resume' }));
    const confirmButtons = screen.getAllByRole('button', { name: 'Resume' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    expect(mockTradingResume).toHaveBeenCalledWith('trading-1');
    expect(mockShowSuccess).toHaveBeenCalledWith(
      'Trading resumed successfully'
    );
  });

  it('trading task card restarts stopped tasks', async () => {
    const user = userEvent.setup();

    render(
      <TradingTaskCard
        task={{ ...tradingTaskBase, status: TaskStatus.STOPPED }}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Restart' }));
    const confirmButtons = screen.getAllByRole('button', { name: 'Restart' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    expect(mockTradingRestart).toHaveBeenCalledWith('trading-1');
    expect(mockShowSuccess).toHaveBeenCalledWith(
      'Trading restarted successfully'
    );
  });

  it('backtest task card starts created tasks', async () => {
    const user = userEvent.setup();

    render(
      <BacktestTaskCard
        task={{ ...backtestTaskBase, status: TaskStatus.CREATED }}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Start' }));
    const confirmButtons = screen.getAllByRole('button', { name: 'Start' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    expect(mockBacktestStart).toHaveBeenCalledWith('backtest-1');
    expect(mockShowSuccess).toHaveBeenCalledWith(
      'Backtest started successfully'
    );
  });

  it('backtest task card stops running tasks through the confirm dialog', async () => {
    const user = userEvent.setup();

    render(
      <BacktestTaskCard
        task={{ ...backtestTaskBase, status: TaskStatus.RUNNING }}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Stop' }));
    await user.click(screen.getByRole('button', { name: 'Confirm Stop' }));

    expect(mockBacktestStop).toHaveBeenCalledWith({
      id: 'backtest-1',
      mode: 'graceful',
    });
    expect(mockShowSuccess).toHaveBeenCalledWith(
      'Backtest stopped successfully'
    );
  });

  it('backtest task card pauses running tasks', async () => {
    const user = userEvent.setup();

    render(
      <BacktestTaskCard
        task={{ ...backtestTaskBase, status: TaskStatus.RUNNING }}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Pause' }));
    const confirmButtons = screen.getAllByRole('button', { name: 'Pause' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    expect(mockBacktestPause).toHaveBeenCalledWith('backtest-1');
    expect(mockShowSuccess).toHaveBeenCalledWith(
      'Backtest paused successfully'
    );
  });

  it('backtest task card resumes paused tasks', async () => {
    const user = userEvent.setup();

    render(
      <BacktestTaskCard
        task={{ ...backtestTaskBase, status: TaskStatus.PAUSED }}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Resume' }));
    const confirmButtons = screen.getAllByRole('button', { name: 'Resume' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    expect(mockBacktestResume).toHaveBeenCalledWith('backtest-1');
    expect(mockShowSuccess).toHaveBeenCalledWith(
      'Backtest resumed successfully'
    );
  });

  it('backtest task card restarts stopped tasks', async () => {
    const user = userEvent.setup();

    render(
      <BacktestTaskCard
        task={{ ...backtestTaskBase, status: TaskStatus.STOPPED }}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Restart' }));
    const confirmButtons = screen.getAllByRole('button', { name: 'Restart' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    expect(mockBacktestRestart).toHaveBeenCalledWith('backtest-1');
    expect(mockShowSuccess).toHaveBeenCalledWith(
      'Backtest restarted successfully'
    );
  });
});
