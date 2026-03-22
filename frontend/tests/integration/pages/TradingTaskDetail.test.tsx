/**
 * Integration tests for TradingTaskDetail page action wiring.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TradingTaskDetail } from '../../../src/components/trading/TradingTaskDetail';
import { TaskStatus } from '../../../src/types/common';
import { buildTaskTrendViewModel } from '../../fixtures/taskTrendViewModel';

const {
  mockTradingStart,
  mockTradingStop,
  mockTradingPause,
  mockTradingResume,
  mockTradingRestart,
} = vi.hoisted(() => ({
  mockTradingStart: vi.fn(),
  mockTradingStop: vi.fn(),
  mockTradingPause: vi.fn(),
  mockTradingResume: vi.fn(),
  mockTradingRestart: vi.fn(),
}));

const mockTaskData = {
  id: 1,
  name: 'Test Trading Task',
  description: 'A test trading task',
  status: TaskStatus.RUNNING,
  config_name: 'Test Config',
  config_id: 1,
  account_id: '1',
  strategy_type: 'floor',
  instrument: 'EUR_USD',
  pip_size: '0.0001',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  started_at: '2024-01-01T00:00:00Z',
  completed_at: null,
  latest_execution: null,
  execution_id: null,
  error_message: null,
  sell_on_stop: false,
  dry_run: false,
  hedging_enabled: false,
};

vi.mock('../../../src/hooks/useTradingTasks', () => ({
  useTradingTask: vi.fn(() => ({
    data: mockTaskData,
    isLoading: false,
    error: null,
    refresh: vi.fn(),
  })),
}));

vi.mock('../../../src/hooks/useStrategies', () => ({
  useStrategies: vi.fn(() => ({
    strategies: [],
  })),
  getStrategyDisplayName: vi.fn(() => 'Floor Strategy'),
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
        progress: 0,
      },
    },
    isLoading: false,
    error: null,
    refresh: vi.fn(),
  })),
}));

vi.mock('../../../src/hooks/useTradingTaskMutations', () => ({
  useStartTradingTask: vi.fn(() => ({
    mutate: mockTradingStart,
    isLoading: false,
  })),
  useStopTradingTask: vi.fn(() => ({
    mutate: mockTradingStop,
    isLoading: false,
  })),
  usePauseTradingTask: vi.fn(() => ({
    mutate: mockTradingPause,
    isLoading: false,
  })),
  useResumeTradingTask: vi.fn(() => ({
    mutate: mockTradingResume,
    isLoading: false,
  })),
  useRestartTradingTask: vi.fn(() => ({
    mutate: mockTradingRestart,
    isLoading: false,
  })),
  useDeleteTradingTask: vi.fn(() => ({ mutate: vi.fn(), isLoading: false })),
}));

vi.mock('../../../src/hooks/useOptimisticTaskStatus', () => ({
  useOptimisticTaskStatus: vi.fn(() => ({
    optimisticStatus: null,
    statusPollingIntervalMs: 1000,
    applyOptimisticStatus: vi.fn(),
    clearOptimisticStatus: vi.fn(),
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
vi.mock('../../../src/components/tasks/detail/TaskEventsTable', () => ({
  TaskEventsTable: () => <div data-testid="events-table">Events</div>,
}));
vi.mock('../../../src/components/tasks/detail/TaskLogsTable', () => ({
  TaskLogsTable: () => <div data-testid="logs-table">Logs</div>,
}));
vi.mock('../../../src/components/tasks/detail/TaskPositionsTable', () => ({
  TaskPositionsTable: () => <div data-testid="positions-table">Positions</div>,
}));
vi.mock('../../../src/components/tasks/detail/TaskTradesTable', () => ({
  TaskTradesTable: () => <div data-testid="trades-table">Trades</div>,
}));
vi.mock('../../../src/components/tasks/detail/TaskOrdersTable', () => ({
  TaskOrdersTable: () => <div data-testid="orders-table">Orders</div>,
}));
vi.mock('../../../src/components/tasks/detail/TaskTrendPanel', () => ({
  TaskTrendPanel: () => {
    const fixture = buildTaskTrendViewModel();
    return (
      <div data-testid="trend-panel">
        Trend {fixture.toolbarProps.executionRunId}
      </div>
    );
  },
}));
vi.mock('../../../src/components/tasks/actions/DeleteTaskDialog', () => ({
  DeleteTaskDialog: () => null,
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/trading-tasks/1']}>
        <Routes>
          <Route path="/trading-tasks/:id" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('TradingTaskDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockTradingStart.mockResolvedValue({
      ...mockTaskData,
      status: TaskStatus.STARTING,
    });
    mockTradingStop.mockResolvedValue({});
    mockTradingPause.mockResolvedValue({
      ...mockTaskData,
      status: TaskStatus.PAUSED,
    });
    mockTradingResume.mockResolvedValue({
      ...mockTaskData,
      status: TaskStatus.RUNNING,
    });
    mockTradingRestart.mockResolvedValue({
      ...mockTaskData,
      status: TaskStatus.STARTING,
    });
  });

  it('starts created trading tasks from the detail header', async () => {
    const mod = await import('../../../src/hooks/useTradingTasks');
    vi.mocked(mod.useTradingTask).mockReturnValueOnce({
      data: { ...mockTaskData, status: TaskStatus.CREATED },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    const user = userEvent.setup();

    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await user.click(screen.getByRole('button', { name: 'Start' }));

    await waitFor(() => {
      expect(mockTradingStart).toHaveBeenCalledWith('1');
    });
  });

  it('stops running trading tasks from the detail header', async () => {
    const user = userEvent.setup();

    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await user.click(screen.getByRole('button', { name: 'Stop' }));

    await waitFor(() => {
      expect(mockTradingStop).toHaveBeenCalledWith({ id: '1' });
    });
  });

  it('pauses running trading tasks from the detail header', async () => {
    const user = userEvent.setup();

    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await user.click(screen.getByRole('button', { name: 'Pause' }));

    await waitFor(() => {
      expect(mockTradingPause).toHaveBeenCalledWith('1');
    });
  });

  it('resumes paused trading tasks from the detail header', async () => {
    const mod = await import('../../../src/hooks/useTradingTasks');
    vi.mocked(mod.useTradingTask).mockReturnValueOnce({
      data: { ...mockTaskData, status: TaskStatus.PAUSED },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    const user = userEvent.setup();

    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await user.click(screen.getByRole('button', { name: 'Resume' }));

    await waitFor(() => {
      expect(mockTradingResume).toHaveBeenCalledWith('1');
    });
  });

  it('restarts stopped trading tasks from the detail header', async () => {
    const mod = await import('../../../src/hooks/useTradingTasks');
    vi.mocked(mod.useTradingTask).mockReturnValueOnce({
      data: { ...mockTaskData, status: TaskStatus.STOPPED },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    const user = userEvent.setup();

    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await user.click(screen.getByRole('button', { name: 'Restart' }));

    await waitFor(() => {
      expect(mockTradingRestart).toHaveBeenCalledWith('1');
    });
  });
});
