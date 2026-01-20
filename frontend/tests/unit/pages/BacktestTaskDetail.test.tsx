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

vi.mock('../../../src/api/generated/services/ExecutionsService', () => ({
  ExecutionsService: {
    getExecutionLatestMetrics: vi.fn(() =>
      Promise.resolve({
        realized_pnl: '100.50',
        unrealized_pnl: '25.75',
        total_pnl: '126.25',
        open_positions: 3,
        total_trades: 15,
        timestamp: '2024-01-01T12:00:00Z',
      })
    ),
    getExecutionEquity: vi.fn(() =>
      Promise.resolve({
        bins: [
          {
            timestamp: '2024-01-01T00:00:00Z',
            realized_pnl_min: 90,
            realized_pnl_max: 110,
            realized_pnl_avg: 100,
            realized_pnl_median: 100,
            unrealized_pnl_min: 20,
            unrealized_pnl_max: 30,
            unrealized_pnl_avg: 25,
            unrealized_pnl_median: 25,
            tick_ask_min: 1.1,
            tick_ask_max: 1.2,
            tick_ask_avg: 1.15,
            tick_ask_median: 1.15,
            tick_bid_min: 1.0,
            tick_bid_max: 1.1,
            tick_bid_avg: 1.05,
            tick_bid_median: 1.05,
            tick_mid_min: 1.05,
            tick_mid_max: 1.15,
            tick_mid_avg: 1.1,
            tick_mid_median: 1.1,
            trade_count: 5,
          },
        ],
      })
    ),
    getExecutionMetrics: vi.fn(() =>
      Promise.resolve({
        metrics: [
          {
            timestamp: '2024-01-01T00:00:00Z',
            sequence: 1,
            realized_pnl: 100,
            unrealized_pnl: 25,
            total_pnl: 125,
            open_positions: 3,
            total_trades: 15,
            tick_ask_min: 1.1,
            tick_ask_max: 1.2,
            tick_ask_avg: 1.15,
            tick_bid_min: 1.0,
            tick_bid_max: 1.1,
            tick_bid_avg: 1.05,
            tick_mid_min: 1.05,
            tick_mid_max: 1.15,
            tick_mid_avg: 1.1,
          },
        ],
      })
    ),
    getExecutionEvents: vi.fn(() => Promise.resolve({ events: [] })),
    getExecutionLogs: vi.fn(() => Promise.resolve({ logs: [] })),
    getExecutionTrades: vi.fn(() => Promise.resolve({ trades: [] })),
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
      strategy_type: 'floor',
      start_time: '2024-01-01T00:00:00Z',
      end_time: null,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  })),
}));

// Mock common components
vi.mock('../../../src/components/common', () => ({
  ExecutionDataProvider: ({
    children,
  }: {
    children: (
      executionId: number | null,
      isLoading: boolean
    ) => React.ReactNode;
  }) => <div>{children(123, false)}</div>,
  TaskControlButtons: () => <div>Task Control Buttons</div>,
  useToast: () => ({
    showError: vi.fn(),
    showSuccess: vi.fn(),
  }),
}));

// Mock detail components
vi.mock('../../../src/components/backtest/detail/EventsTable', () => ({
  EventsTable: () => <div>Events Table</div>,
}));

vi.mock('../../../src/components/backtest/detail/LogsTable', () => ({
  LogsTable: () => <div>Logs Table</div>,
}));

vi.mock('../../../src/components/backtest/detail/TradesTable', () => ({
  TradesTable: () => <div>Trades Table</div>,
}));

vi.mock('../../../src/components/backtest/detail/EquityChart', () => ({
  EquityChart: () => <div>Equity Chart</div>,
}));

vi.mock('../../../src/components/backtest/detail/MetricsChart', () => ({
  MetricsChart: () => <div>Metrics Chart</div>,
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
      expect(screen.getByText('Test Backtest Task')).toBeInTheDocument();
      expect(screen.getByText(TaskStatus.RUNNING)).toBeInTheDocument();
    });
  });

  it('renders task configuration details', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByText(/Configuration: Test Config/)
      ).toBeInTheDocument();
      expect(screen.getByText(/Strategy: floor/)).toBeInTheDocument();
    });
  });

  it('renders task description', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Test description')).toBeInTheDocument();
    });
  });

  it('renders execution ID when available', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/Execution ID: 123/)).toBeInTheDocument();
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
      expect(screen.getByText('Events')).toBeInTheDocument();
      expect(screen.getByText('Logs')).toBeInTheDocument();
      expect(screen.getByText('Trades')).toBeInTheDocument();
      expect(screen.getByText('Equity')).toBeInTheDocument();
      expect(screen.getByText('Metrics')).toBeInTheDocument();
    });
  });

  it('renders Events tab content by default', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Events Table')).toBeInTheDocument();
    });
  });

  it('switches to Logs tab when clicked', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Events Table')).toBeInTheDocument();
    });

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

  it('switches to Equity tab when clicked', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    const equityTab = screen.getByText('Equity');
    fireEvent.click(equityTab);

    await waitFor(() => {
      expect(screen.getByText('Equity Chart')).toBeInTheDocument();
    });
  });

  it('switches to Metrics tab when clicked', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    const metricsTab = screen.getByText('Metrics');
    fireEvent.click(metricsTab);

    await waitFor(() => {
      expect(screen.getByText('Metrics Chart')).toBeInTheDocument();
    });
  });

  it('renders breadcrumbs with navigation', async () => {
    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Backtest Tasks')).toBeInTheDocument();
      expect(screen.getByText('Test Backtest Task')).toBeInTheDocument();
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

  it('shows info message when no execution data available', async () => {
    const commonMock = await import('../../../src/components/common');
    vi.mocked(commonMock.ExecutionDataProvider).mockImplementationOnce(
      ({
        children,
      }: {
        children: (
          executionId: number | null,
          isLoading: boolean
        ) => React.ReactNode;
      }) => <div>{children(null, false)}</div>
    );

    render(<BacktestTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByText('No execution data available')
      ).toBeInTheDocument();
    });
  });
});
