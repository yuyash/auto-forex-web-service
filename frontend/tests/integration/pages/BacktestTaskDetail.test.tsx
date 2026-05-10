/**
 * Integration test for BacktestTaskDetail page.
 * Tests component rendering, tab navigation, loading/error states.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BacktestTaskDetail } from '../../../src/components/backtest/BacktestTaskDetail';
import { TaskStatus } from '../../../src/types/common';
import { createRouteQueryWrapper } from '../../utils/routeQueryTestUtils';

const {
  mockBacktestStart,
  mockBacktestStop,
  mockBacktestPause,
  mockBacktestResume,
  mockBacktestRestart,
  mockBacktestAdjust,
  mockShowError,
} = vi.hoisted(() => ({
  mockBacktestStart: vi.fn(),
  mockBacktestStop: vi.fn(),
  mockBacktestPause: vi.fn(),
  mockBacktestResume: vi.fn(),
  mockBacktestRestart: vi.fn(),
  mockBacktestAdjust: vi.fn(),
  mockShowError: vi.fn(),
}));

// Mock API services
vi.mock('../../../src/api/generated/services/TradingService', () => ({
  TradingService: {
    tradingBacktestTasksStartCreate: vi.fn(),
    tradingBacktestTasksStopCreate: vi.fn(),
    tradingBacktestTasksResumeCreate: vi.fn(),
    tradingBacktestTasksRestartCreate: vi.fn(),
    tradingBacktestTasksDestroy: vi.fn(),
  },
}));

const mockTaskData = {
  id: 1,
  name: 'Test Backtest',
  description: 'A test backtest task',
  status: TaskStatus.RUNNING,
  config_name: 'Test Config',
  config_id: 1,
  strategy_type: 'floor',
  instrument: 'EUR_USD',
  pip_size: '0.0001',
  data_source: 'oanda',
  initial_balance: '10000.00',
  commission_per_trade: '0.00',
  start_time: '2024-01-01T00:00:00Z',
  end_time: '2024-01-02T00:00:00Z',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  latest_execution: null,
  celery_task_id: null,
  progress: 0,
};

vi.mock('../../../src/hooks/useBacktestTasks', () => ({
  useBacktestTask: vi.fn(() => ({
    data: mockTaskData,
    isLoading: false,
    error: null,
    refresh: vi.fn(),
  })),
}));

vi.mock('../../../src/hooks/useTaskSummary', () => ({
  useTaskSummary: vi.fn(() => ({
    summary: {
      timestamp: null,
      pnl: { realized: 0, unrealized: 0 },
      counts: { totalTrades: 0, openPositions: 0, closedPositions: 0 },
      execution: {
        currentBalance: null,
        ticksProcessed: 0,
        accountCurrency: null,
        currentBalanceDisplay: null,
        displayCurrency: null,
      },
      tick: { timestamp: null, bid: null, ask: null, mid: null },
      task: {
        status: '',
        startedAt: null,
        completedAt: null,
        errorMessage: null,
        errorCode: null,
        progress: 0,
      },
    },
    isLoading: false,
    error: null,
    refresh: vi.fn(),
  })),
}));

vi.mock('../../../src/hooks/useBacktestTaskMutations', () => ({
  useStartBacktestTask: vi.fn(() => ({
    mutate: mockBacktestStart,
    isLoading: false,
  })),
  useStopBacktestTask: vi.fn(() => ({
    mutate: mockBacktestStop,
    isLoading: false,
  })),
  usePauseBacktestTask: vi.fn(() => ({
    mutate: mockBacktestPause,
    isLoading: false,
  })),
  useResumeBacktestTask: vi.fn(() => ({
    mutate: mockBacktestResume,
    isLoading: false,
  })),
  useRerunBacktestTask: vi.fn(() => ({
    mutate: mockBacktestRestart,
    isLoading: false,
  })),
  useAdjustBacktestBalance: vi.fn(() => ({
    mutate: mockBacktestAdjust,
    isLoading: false,
  })),
  useDeleteBacktestTask: vi.fn(() => ({ mutate: vi.fn(), isLoading: false })),
}));

vi.mock('../../../src/components/common', async () => {
  const actual = await vi.importActual('../../../src/components/common');
  return {
    ...actual,
    useToast: vi.fn(() => ({
      showError: mockShowError,
      showSuccess: vi.fn(),
      showInfo: vi.fn(),
      showWarning: vi.fn(),
    })),
  };
});

// Mock child components to isolate page-level behavior
vi.mock('../../../src/hooks/useTaskMetrics', () => ({
  useTaskMetrics: vi.fn(() => ({
    data: [],
    latest: null,
    isLoading: false,
    error: null,
    refresh: vi.fn(),
  })),
}));

vi.mock('../../../src/contexts/AuthContext', () => ({
  useAuth: vi.fn(() => ({
    user: { timezone: 'UTC' },
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    register: vi.fn(),
  })),
}));
vi.mock('../../../src/components/common/TaskControlButtons', () => ({
  TaskControlButtons: ({
    onStart,
    onStop,
    onPause,
    onResume,
    onRestart,
  }: {
    onStart?: (taskId: string) => void | Promise<void>;
    onStop?: (taskId: string) => void | Promise<void>;
    onPause?: (taskId: string) => void | Promise<void>;
    onResume?: (taskId: string) => void | Promise<void>;
    onRestart?: (taskId: string) => void | Promise<void>;
  }) => (
    <div data-testid="task-controls">
      <button type="button" onClick={() => onStart?.('1')}>
        Start
      </button>
      <button type="button" onClick={() => onStop?.('1')}>
        Stop
      </button>
      <button type="button" onClick={() => onPause?.('1')}>
        Pause
      </button>
      <button type="button" onClick={() => onResume?.('1')}>
        Resume
      </button>
      <button type="button" onClick={() => onRestart?.('1')}>
        Restart
      </button>
    </div>
  ),
}));
vi.mock('../../../src/components/tasks/display/StatusBadge', () => ({
  StatusBadge: ({ status }: { status: string }) => <span>{status}</span>,
}));
vi.mock('../../../src/components/tasks/detail/TaskLogsTable', () => ({
  TaskLogsTable: () => <div data-testid="logs-table">Logs</div>,
}));
vi.mock('../../../src/components/tasks/detail/TaskPositionsTable', () => ({
  TaskPositionsTable: () => <div data-testid="positions-table">Positions</div>,
}));
vi.mock('../../../src/components/tasks/TaskProgress', () => ({
  TaskProgress: () => <div>Progress</div>,
}));
vi.mock('../../../src/components/tasks/actions/DeleteTaskDialog', () => ({
  DeleteTaskDialog: () => null,
}));

function createWrapper() {
  return createRouteQueryWrapper({
    initialEntry: '/backtest-tasks/1',
    path: '/backtest-tasks/:id',
  }).wrapper;
}

describe('BacktestTaskDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockBacktestStart.mockResolvedValue({
      ...mockTaskData,
      status: TaskStatus.STARTING,
    });
    mockBacktestStop.mockResolvedValue({});
    mockBacktestPause.mockResolvedValue({
      ...mockTaskData,
      status: TaskStatus.PAUSED,
    });
    mockBacktestResume.mockResolvedValue({
      ...mockTaskData,
      status: TaskStatus.RUNNING,
    });
    mockBacktestRestart.mockResolvedValue({
      ...mockTaskData,
      status: TaskStatus.STARTING,
    });
    mockBacktestAdjust.mockResolvedValue({
      current_balance: '12500.0000000000',
    });
  });

  it('renders task name and status', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Test Backtest' })
      ).toBeInTheDocument();
    });
  });

  it('renders all tab labels', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText('Overview')).toBeInTheDocument();
      expect(screen.getByText('Logs')).toBeInTheDocument();
      expect(screen.getByText('Positions')).toBeInTheDocument();
    });
  });

  it('shows Overview tab by default', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText('Task Information')).toBeInTheDocument();
    });
  });

  it('switches to Logs tab', async () => {
    const user = userEvent.setup();
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await user.click(screen.getByText('Logs'));
    await waitFor(() => {
      expect(screen.getByTestId('logs-table')).toBeInTheDocument();
    });
  });

  it('switches to Positions tab', async () => {
    const user = userEvent.setup();
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await user.click(screen.getByText('Positions'));
    await waitFor(() => {
      expect(screen.getByTestId('positions-table')).toBeInTheDocument();
    });
  });

  it('shows loading state', async () => {
    const mod = await import('../../../src/hooks/useBacktestTasks');
    vi.mocked(mod.useBacktestTask).mockReturnValueOnce({
      data: null,
      isLoading: true,
      error: null,
      refresh: vi.fn(),
    });

    render(<BacktestTaskDetail />, { wrapper: createWrapper() });
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows error state', async () => {
    const mod = await import('../../../src/hooks/useBacktestTasks');
    vi.mocked(mod.useBacktestTask).mockReturnValueOnce({
      data: null,
      isLoading: false,
      error: new Error('Failed to load'),
      refresh: vi.fn(),
    });

    render(<BacktestTaskDetail />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText('Failed to load')).toBeInTheDocument();
    });
  });

  it('renders breadcrumb navigation', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByRole('navigation')).toBeInTheDocument();
    });
  });

  it('starts created backtest tasks from the detail header', async () => {
    const mod = await import('../../../src/hooks/useBacktestTasks');
    vi.mocked(mod.useBacktestTask).mockReturnValueOnce({
      data: { ...mockTaskData, status: TaskStatus.CREATED },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    const user = userEvent.setup();

    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await user.click(screen.getByRole('button', { name: 'Start' }));
    const startConfirmButtons = screen.getAllByRole('button', {
      name: 'Start',
    });
    await user.click(startConfirmButtons[startConfirmButtons.length - 1]);

    await waitFor(() => {
      expect(mockBacktestStart).toHaveBeenCalledWith('1');
    });
  });

  it('confirms before stopping a backtest task', async () => {
    const user = userEvent.setup();
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await user.click(screen.getByRole('button', { name: 'Stop' }));

    expect(mockBacktestStop).not.toHaveBeenCalled();
    expect(
      screen.getByRole('heading', { name: 'Stop Backtest Task' })
    ).toBeInTheDocument();

    // Pick the default "keep positions" option, then confirm.
    await user.click(
      screen.getByRole('button', { name: /Stop \(Keep Positions\)/i })
    );
    await user.click(screen.getByRole('button', { name: 'Stop Task' }));

    await waitFor(() => {
      expect(mockBacktestStop).toHaveBeenCalledWith({
        id: '1',
        mode: 'graceful',
      });
    });
  });

  it('pauses running backtest tasks from the detail header', async () => {
    const user = userEvent.setup();
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await user.click(screen.getByRole('button', { name: 'Pause' }));
    const confirmButtons = screen.getAllByRole('button', { name: 'Pause' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(mockBacktestPause).toHaveBeenCalledWith('1');
    });
  });

  it('resumes paused backtest tasks from the detail header', async () => {
    const mod = await import('../../../src/hooks/useBacktestTasks');
    vi.mocked(mod.useBacktestTask).mockReturnValueOnce({
      data: { ...mockTaskData, status: TaskStatus.PAUSED },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    const user = userEvent.setup();

    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await user.click(screen.getByRole('button', { name: 'Resume' }));
    const confirmButtons = screen.getAllByRole('button', { name: 'Resume' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(mockBacktestResume).toHaveBeenCalledWith('1');
    });
  });

  it('restarts stopped backtest tasks from the detail header', async () => {
    const mod = await import('../../../src/hooks/useBacktestTasks');
    vi.mocked(mod.useBacktestTask).mockReturnValueOnce({
      data: { ...mockTaskData, status: TaskStatus.STOPPED },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    const user = userEvent.setup();

    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await user.click(screen.getByRole('button', { name: 'Restart' }));
    const confirmButtons = screen.getAllByRole('button', { name: 'Restart' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(mockBacktestRestart).toHaveBeenCalledWith('1');
    });
  });

  it('adjusts balance for paused backtest tasks from the detail header', async () => {
    const taskMod = await import('../../../src/hooks/useBacktestTasks');
    const summaryMod = await import('../../../src/hooks/useTaskSummary');
    vi.mocked(taskMod.useBacktestTask).mockReturnValueOnce({
      data: { ...mockTaskData, status: TaskStatus.PAUSED },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    const summary = {
      timestamp: null,
      pnl: { realized: 0, unrealized: 0 },
      counts: {
        totalTrades: 0,
        openPositions: 0,
        closedPositions: 0,
        openLongUnits: 0,
        openShortUnits: 0,
        winningTrades: 0,
        losingTrades: 0,
      },
      execution: {
        currentBalance: 10000,
        ticksProcessed: 0,
        accountCurrency: 'USD',
        currentBalanceDisplay: null,
        displayCurrency: null,
        resumeCursorTimestamp: null,
        marginRatio: null,
        currentAtr: null,
        recoveryStatus: null,
        recoveryWarnings: [],
        recoveryBlockers: [],
        reconciledAt: null,
      },
      tick: { timestamp: null, bid: null, ask: null, mid: null },
      task: {
        status: '',
        startedAt: null,
        completedAt: null,
        errorMessage: null,
        errorCode: null,
        stopReason: null,
        progress: 0,
      },
    };
    vi.mocked(summaryMod.useTaskSummary).mockReturnValueOnce({
      data: summary,
      summary,
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    const user = userEvent.setup();

    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await user.click(screen.getByRole('button', { name: 'Adjust Balance' }));
    const input = screen.getByLabelText('New Current Balance');
    await user.clear(input);
    await user.type(input, '12500');
    await user.click(screen.getByRole('button', { name: 'OK' }));

    await waitFor(() => {
      expect(mockBacktestAdjust).toHaveBeenCalledWith({
        id: '1',
        data: { current_balance: '12500' },
      });
    });
  });

  it('shows backend action failure details', async () => {
    const mod = await import('../../../src/hooks/useBacktestTasks');
    const { ApiError } = await import('../../../src/api/apiClient');
    vi.mocked(mod.useBacktestTask).mockReturnValueOnce({
      data: { ...mockTaskData, status: TaskStatus.CREATED },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    mockBacktestStart.mockRejectedValueOnce(
      new ApiError('/api/test', 409, 'Conflict', {
        detail: 'Backtest capacity exhausted for backtest.',
        required_stops: [{ message: 'Stop at least 1 backtest task.' }],
      })
    );
    const user = userEvent.setup();

    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await user.click(screen.getByRole('button', { name: 'Start' }));
    const confirmButtons = screen.getAllByRole('button', { name: 'Start' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(mockShowError).toHaveBeenCalledWith(
        'Backtest capacity exhausted for backtest. Stop at least 1 backtest task.'
      );
    });
  });
});
