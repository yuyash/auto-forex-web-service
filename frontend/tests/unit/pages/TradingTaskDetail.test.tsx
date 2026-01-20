/**
 * Unit tests for TradingTaskDetail
 *
 * Tests component rendering, tab navigation, and data fetching.
 * Requirements: 11.14, 11.15, 11.16, 11.17, 11.18
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TradingTaskDetail } from '../../../src/components/trading/TradingTaskDetail';
import { TaskStatus } from '../../../src/types/common';

// Mock the generated API services
vi.mock('../../../src/api/generated/services/TradingService', () => ({
  TradingService: {
    tradingTradingTasksStartCreate: vi.fn(),
    tradingTradingTasksStopCreate: vi.fn(),
    tradingTradingTasksResumeCreate: vi.fn(),
    tradingTradingTasksRestartCreate: vi.fn(),
    tradingTradingTasksDestroy: vi.fn(),
  },
}));

vi.mock('../../../src/api/generated/services/ExecutionsService', () => ({
  ExecutionsService: {
    getExecutionLatestMetrics: vi.fn(() =>
      Promise.resolve({
        realized_pnl: '150.75',
        unrealized_pnl: '35.25',
        total_pnl: '186.00',
        open_positions: 5,
        total_trades: 25,
        timestamp: '2024-01-01T12:00:00Z',
      })
    ),
    getExecutionEquity: vi.fn(() =>
      Promise.resolve({
        bins: [
          {
            timestamp: '2024-01-01T00:00:00Z',
            realized_pnl_min: 140,
            realized_pnl_max: 160,
            realized_pnl_avg: 150,
            realized_pnl_median: 150,
            unrealized_pnl_min: 30,
            unrealized_pnl_max: 40,
            unrealized_pnl_avg: 35,
            unrealized_pnl_median: 35,
            tick_ask_min: 1.2,
            tick_ask_max: 1.3,
            tick_ask_avg: 1.25,
            tick_ask_median: 1.25,
            tick_bid_min: 1.1,
            tick_bid_max: 1.2,
            tick_bid_avg: 1.15,
            tick_bid_median: 1.15,
            tick_mid_min: 1.15,
            tick_mid_max: 1.25,
            tick_mid_avg: 1.2,
            tick_mid_median: 1.2,
            trade_count: 8,
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
            realized_pnl: 150,
            unrealized_pnl: 35,
            total_pnl: 185,
            open_positions: 5,
            total_trades: 25,
            tick_ask_min: 1.2,
            tick_ask_max: 1.3,
            tick_ask_avg: 1.25,
            tick_bid_min: 1.1,
            tick_bid_max: 1.2,
            tick_bid_avg: 1.15,
            tick_mid_min: 1.15,
            tick_mid_max: 1.25,
            tick_mid_avg: 1.2,
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
vi.mock('../../../src/hooks/useTradingTasks', () => ({
  useTradingTask: vi.fn((id: number) => ({
    data: {
      id,
      name: 'Test Trading Task',
      description: 'Test trading description',
      status: TaskStatus.RUNNING,
      config_name: 'Live Config',
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
  }) => <div>{children(456, false)}</div>,
  TaskControlButtons: () => <div>Task Control Buttons</div>,
  useToast: () => ({
    showError: vi.fn(),
    showSuccess: vi.fn(),
  }),
}));

// Mock detail components (reused from backtest)
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
      <MemoryRouter initialEntries={['/trading-tasks/1']}>
        <Routes>
          <Route path="/trading-tasks/:id" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
};

describe('TradingTaskDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the task name and status', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Test Trading Task' })
      ).toBeInTheDocument();
      expect(screen.getByText(TaskStatus.RUNNING)).toBeInTheDocument();
    });
  });

  it('renders task configuration details', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByText(/Configuration: Live Config/)
      ).toBeInTheDocument();
      expect(screen.getByText(/Strategy: floor/)).toBeInTheDocument();
    });
  });

  it('renders task description', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Test trading description')).toBeInTheDocument();
    });
  });

  it('renders execution ID when available', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/Execution ID: 456/)).toBeInTheDocument();
    });
  });

  it('renders task control buttons', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Task Control Buttons')).toBeInTheDocument();
    });
  });

  it('renders all tab labels', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Events')).toBeInTheDocument();
      expect(screen.getByText('Logs')).toBeInTheDocument();
      expect(screen.getByText('Trades')).toBeInTheDocument();
      expect(screen.getByText('Equity')).toBeInTheDocument();
      expect(screen.getByText('Metrics')).toBeInTheDocument();
    });
  });

  it('renders Events tab content by default', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Events Table')).toBeInTheDocument();
    });
  });

  it('switches to Logs tab when clicked', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

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
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    const tradesTab = screen.getByText('Trades');
    fireEvent.click(tradesTab);

    await waitFor(() => {
      expect(screen.getByText('Trades Table')).toBeInTheDocument();
    });
  });

  it('switches to Equity tab when clicked', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    const equityTab = screen.getByText('Equity');
    fireEvent.click(equityTab);

    await waitFor(() => {
      expect(screen.getByText('Equity Chart')).toBeInTheDocument();
    });
  });

  it('switches to Metrics tab when clicked', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    const metricsTab = screen.getByText('Metrics');
    fireEvent.click(metricsTab);

    await waitFor(() => {
      expect(screen.getByText('Metrics Chart')).toBeInTheDocument();
    });
  });

  it('renders breadcrumbs with navigation', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      const breadcrumbs = screen.getByRole('navigation');
      expect(breadcrumbs).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: 'Trading Tasks' })
      ).toBeInTheDocument();
    });
  });

  it('renders latest metrics when loaded', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    // Click the "Load latest metrics" link
    await waitFor(() => {
      const loadLink = screen.getByText('Load latest metrics');
      fireEvent.click(loadLink);
    });

    // Wait for metrics to load
    await waitFor(() => {
      expect(screen.getByText('Realized PnL')).toBeInTheDocument();
      expect(screen.getByText('$150.75')).toBeInTheDocument();
      expect(screen.getByText('Unrealized PnL')).toBeInTheDocument();
      expect(screen.getByText('$35.25')).toBeInTheDocument();
      expect(screen.getByText('Total PnL')).toBeInTheDocument();
      expect(screen.getByText('$186.00')).toBeInTheDocument();
      expect(screen.getByText('Open Positions')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('Total Trades')).toBeInTheDocument();
      expect(screen.getByText('25')).toBeInTheDocument();
    });
  });
});
