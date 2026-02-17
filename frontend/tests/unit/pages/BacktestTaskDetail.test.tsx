/**
 * Unit tests for BacktestTaskDetail
 *
 * Tests component rendering, tab navigation, and data fetching.
 * Requirements: 11.5, 11.6, 11.7, 11.8, 11.9
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BacktestTaskDetail } from '../../../src/components/backtest/BacktestTaskDetail';
import { TaskStatus } from '../../../src/types/common';

// Mock the generated API services
vi.mock('../../../src/api/generated/services/TradingService', () => ({
  TradingService: {
    tradingBacktestTasksStartCreate: vi.fn(),
    tradingBacktestTasksStopCreate: vi.fn(),
    tradingBacktestTasksResumeCreate: vi.fn(),
    tradingBacktestTasksRestartCreate: vi.fn(),
    tradingBacktestTasksDestroy: vi.fn(),
  },
}));

// Mock hooks
vi.mock('../../../src/hooks/useBacktestTasks', () => ({
  useBacktestTask: vi.fn((id: number) => ({
    data: {
      id,
      name: 'Test Backtest Task',
      description: 'Test description',
      status: TaskStatus.RUNNING,
      config_name: 'Test Config',
      config_id: 1,
      strategy_type: 'floor',
      instrument: 'EUR_USD',
      pip_size: '0.0001',
      trading_mode: 'backtest',
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
    },
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

// Mock child components
vi.mock('../../../src/components/common/TaskControlButtons', () => ({
  TaskControlButtons: () => <div>Task Control Buttons</div>,
}));

vi.mock('../../../src/components/tasks/display/StatusBadge', () => ({
  StatusBadge: ({ status }: { status: string }) => <span>{status}</span>,
}));

vi.mock('../../../src/components/tasks/detail/TaskEventsTable', () => ({
  TaskEventsTable: () => <div>Events Table</div>,
}));

vi.mock('../../../src/components/tasks/detail/TaskLogsTable', () => ({
  TaskLogsTable: () => <div>Logs Table</div>,
}));

vi.mock('../../../src/components/tasks/detail/TaskTradesTable', () => ({
  TaskTradesTable: () => <div>Trades Table</div>,
}));

vi.mock('../../../src/components/tasks/detail/TaskReplayPanel', () => ({
  TaskReplayPanel: () => <div>Replay Panel</div>,
}));

vi.mock('../../../src/components/tasks/TaskProgress', () => ({
  TaskProgress: () => <div>Task Progress</div>,
}));

// Test wrapper
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
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
};

describe('BacktestTaskDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the task name and status', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Test Backtest Task' })
      ).toBeInTheDocument();
      const statusElements = screen.getAllByText(TaskStatus.RUNNING);
      expect(statusElements.length).toBeGreaterThan(0);
    });
  });

  it('renders task configuration details', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      const floorElements = screen.getAllByText('floor');
      expect(floorElements.length).toBeGreaterThan(0);
    });
  });

  it('renders task description', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      const descElements = screen.getAllByText('Test description');
      expect(descElements.length).toBeGreaterThan(0);
    });
  });

  it('renders task control buttons', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Task Control Buttons')).toBeInTheDocument();
    });
  });

  it('renders all tab labels', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Overview')).toBeInTheDocument();
      expect(screen.getByText('Events')).toBeInTheDocument();
      expect(screen.getByText('Logs')).toBeInTheDocument();
      expect(screen.getByText('Trades')).toBeInTheDocument();
      expect(screen.getByText('Replay')).toBeInTheDocument();
    });
  });

  it('renders Overview tab content by default', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Task Information')).toBeInTheDocument();
    });
  });

  it('switches to Events tab when clicked', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    const eventsTab = screen.getByText('Events');
    fireEvent.click(eventsTab);

    await waitFor(() => {
      expect(screen.getByText('Events Table')).toBeInTheDocument();
    });
  });

  it('switches to Logs tab when clicked', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    const logsTab = screen.getByText('Logs');
    fireEvent.click(logsTab);

    await waitFor(() => {
      expect(screen.getByText('Logs Table')).toBeInTheDocument();
    });
  });

  it('switches to Trades tab when clicked', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    const tradesTab = screen.getByText('Trades');
    fireEvent.click(tradesTab);

    await waitFor(() => {
      expect(screen.getByText('Trades Table')).toBeInTheDocument();
    });
  });

  it('switches to Replay tab when clicked', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    const replayTab = screen.getByText('Replay');
    fireEvent.click(replayTab);

    await waitFor(() => {
      expect(screen.getByText('Replay Panel')).toBeInTheDocument();
    });
  });

  it('renders breadcrumbs with navigation', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByRole('navigation')).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: 'Backtest Tasks' })
      ).toBeInTheDocument();
    });
  });

  it('shows loading state initially', async () => {
    const useBacktestTaskMock = await import(
      '../../../src/hooks/useBacktestTasks'
    );
    vi.mocked(useBacktestTaskMock.useBacktestTask).mockReturnValueOnce({
      data: null,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    });

    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows error state when task fails to load', async () => {
    const useBacktestTaskMock = await import(
      '../../../src/hooks/useBacktestTasks'
    );
    vi.mocked(useBacktestTaskMock.useBacktestTask).mockReturnValueOnce({
      data: null,
      isLoading: false,
      error: new Error('Failed to load task'),
      refetch: vi.fn(),
    });

    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Failed to load task')).toBeInTheDocument();
    });
  });
});
