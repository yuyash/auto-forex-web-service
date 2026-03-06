/**
 * Integration test for BacktestTaskDetail page.
 * Tests component rendering, tab navigation, loading/error states.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BacktestTaskDetail } from '../../../src/components/backtest/BacktestTaskDetail';
import { TaskStatus } from '../../../src/types/common';

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
    refetch: vi.fn(),
  })),
}));

vi.mock('../../../src/hooks/useTaskPolling', () => ({
  useTaskPolling: vi.fn(() => ({
    status: null,
    isPolling: false,
    startPolling: vi.fn(),
    stopPolling: vi.fn(),
  })),
}));

vi.mock('../../../src/hooks/useTaskSummary', () => ({
  useTaskSummary: vi.fn(() => ({
    summary: {
      timestamp: null,
      pnl: { realized: 0, unrealized: 0 },
      counts: { totalTrades: 0, openPositions: 0, closedPositions: 0 },
      execution: { currentBalance: null, ticksProcessed: 0 },
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
    refetch: vi.fn(),
  })),
}));

vi.mock('../../../src/hooks/useBacktestTaskMutations', () => ({
  useDeleteBacktestTask: vi.fn(() => ({ mutate: vi.fn(), isLoading: false })),
}));

// Mock child components to isolate page-level behavior
vi.mock('../../../src/components/common/TaskControlButtons', () => ({
  TaskControlButtons: () => <div data-testid="task-controls">Controls</div>,
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
vi.mock('../../../src/components/tasks/detail/TaskReplayPanel', () => ({
  TaskReplayPanel: () => <div data-testid="replay-panel">Replay</div>,
}));
vi.mock('../../../src/components/tasks/TaskProgress', () => ({
  TaskProgress: () => <div>Progress</div>,
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
      <MemoryRouter initialEntries={['/backtest-tasks/1']}>
        <Routes>
          <Route path="/backtest-tasks/:id" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('BacktestTaskDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
      expect(screen.getByText('Events')).toBeInTheDocument();
      expect(screen.getByText('Logs')).toBeInTheDocument();
      expect(screen.getByText('Positions')).toBeInTheDocument();
      expect(screen.getByText('Trend')).toBeInTheDocument();
    });
  });

  it('shows Overview tab by default', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText('Task Information')).toBeInTheDocument();
    });
  });

  it('switches to Events tab', async () => {
    const user = userEvent.setup();
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await user.click(screen.getByText('Events'));
    await waitFor(() => {
      expect(screen.getByTestId('events-table')).toBeInTheDocument();
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

  it('switches to Trend tab', async () => {
    const user = userEvent.setup();
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await user.click(screen.getByText('Trend'));
    await waitFor(() => {
      expect(screen.getByTestId('replay-panel')).toBeInTheDocument();
    });
  });

  it('shows loading state', async () => {
    const mod = await import('../../../src/hooks/useBacktestTasks');
    vi.mocked(mod.useBacktestTask).mockReturnValueOnce({
      data: null,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
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
      refetch: vi.fn(),
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
});
