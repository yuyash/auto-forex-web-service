/**
 * TaskPerformanceTab Integration Tests
 *
 * Tests the integration of TradingTaskChart with TaskPerformanceTab:
 * - Chart renders with task data
 * - Start vertical line appears
 * - Stop vertical line appears (when stopped)
 * - Trade markers appear
 * - Auto-refresh works for running tasks
 * - Granularity changes work
 * - Trade click highlights table row
 * - Timezone formatting
 * - Error scenarios
 */

import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TaskPerformanceTab } from './TaskPerformanceTab';
import { TaskStatus, TaskType } from '../../../types/common';
import type { TradingTask } from '../../../types/tradingTask';
import type { TaskResults } from '../../../types/results';

// Mock dependencies
vi.mock('../../../hooks/useTaskResults');
vi.mock('../TradingTaskChart', () => ({
  TradingTaskChart: vi.fn(({ onTradeClick }) => (
    <div data-testid="trading-task-chart">
      <button
        data-testid="trade-marker-0"
        onClick={() => onTradeClick && onTradeClick(0)}
      >
        Trade 0
      </button>
      <button
        data-testid="trade-marker-1"
        onClick={() => onTradeClick && onTradeClick(1)}
      >
        Trade 1
      </button>
    </div>
  )),
}));
vi.mock('../../tasks/charts/TradeLogTable', () => ({
  TradeLogTable: vi.fn(({ selectedTradeIndex }) => (
    <div data-testid="trade-log-table">
      Selected: {selectedTradeIndex !== null ? selectedTradeIndex : 'none'}
    </div>
  )),
}));
vi.mock('../../tasks/charts/EquityCurveChart', () => ({
  EquityCurveChart: vi.fn(() => <div data-testid="equity-curve-chart" />),
}));
vi.mock('../../tasks/display/MetricCard', () => ({
  MetricCard: vi.fn(({ title, value }) => (
    <div data-testid={`metric-${title.toLowerCase().replace(/\s+/g, '-')}`}>
      {value}
    </div>
  )),
}));

// Import mocked modules
import { useTradingResults } from '../../../hooks/useTaskResults';
import { TradingTaskChart } from '../TradingTaskChart';

describe('TaskPerformanceTab Integration Tests', () => {
  // Mock scrollIntoView
  beforeAll(() => {
    Element.prototype.scrollIntoView = vi.fn();
  });

  const mockTask: TradingTask = {
    id: 1,
    user_id: 1,
    config_id: 1,
    config_name: 'EUR_USD - MA Crossover',
    strategy_type: 'ma_crossover',
    instrument: 'EUR_USD',
    account_id: 1,
    account_name: 'Test Account',
    account_type: 'practice',
    name: 'Test Trading Task',
    description: 'Test task description',
    status: TaskStatus.RUNNING,
    sell_on_stop: false,
    has_strategy_state: false,
    has_open_positions: false,
    open_positions_count: 0,
    can_resume: false,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };

  const mockResults: TaskResults = {
    task_id: 1,
    task_type: TaskType.TRADING,
    status: TaskStatus.RUNNING,
    execution: {
      id: 1,
      execution_number: 1,
      status: TaskStatus.RUNNING,
      progress: 50,
      started_at: '2024-01-01T00:00:00Z',
      completed_at: null,
      error_message: null,
    },
    has_live: false,
    live: null,
    has_metrics: true,
    metrics: {
      id: 1,
      execution_id: 1,
      total_return: '5.25',
      total_pnl: '525.00',
      total_trades: 10,
      winning_trades: 6,
      losing_trades: 4,
      win_rate: '60.00',
      max_drawdown: '2.50',
      sharpe_ratio: '1.5',
      profit_factor: '1.8',
      average_win: '150.00',
      average_loss: '75.00',
      equity_curve: [
        { timestamp: '2024-01-01T00:00:00Z', balance: 10000 },
        { timestamp: '2024-01-01T12:00:00Z', balance: 10525 },
      ],
      trade_log: [
        {
          entry_time: '2024-01-01T01:00:00Z',
          exit_time: '2024-01-01T02:00:00Z',
          instrument: 'EUR_USD',
          direction: 'long',
          units: 1000,
          entry_price: 1.1,
          exit_price: 1.11,
          pnl: 100,
        },
        {
          entry_time: '2024-01-01T03:00:00Z',
          exit_time: '2024-01-01T04:00:00Z',
          instrument: 'EUR_USD',
          direction: 'short',
          units: 1000,
          entry_price: 1.11,
          exit_price: 1.105,
          pnl: 50,
        },
      ],
      created_at: '2024-01-01T00:00:00Z',
    },
    equity_curve_granularity_seconds: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(useTradingResults).mockReturnValue({
      results: mockResults,
      isLoading: false,
      error: null,
      isPolling: false,
      refetch: vi.fn(),
    });
  });

  it('renders chart with task data', async () => {
    render(<TaskPerformanceTab task={mockTask} />);

    await waitFor(() => {
      expect(screen.getByTestId('trading-task-chart')).toBeInTheDocument();
    });

    // Verify TradingTaskChart was called with correct props
    const chartCall = vi.mocked(TradingTaskChart).mock.calls[0][0];
    expect(chartCall).toMatchObject({
      instrument: 'EUR_USD',
      startDate: mockResults.execution?.started_at,
      stopDate: undefined, // Running task has no stop date
      trades: mockResults.metrics?.trade_log,
      timezone: 'UTC',
      autoRefresh: true, // Running task has auto-refresh enabled
      refreshInterval: 60000,
    });
  });

  it('renders start vertical line for running task', async () => {
    render(<TaskPerformanceTab task={mockTask} />);

    await waitFor(() => {
      expect(screen.getByTestId('trading-task-chart')).toBeInTheDocument();
    });

    // Verify chart was called with startDate
    const chartCall = vi.mocked(TradingTaskChart).mock.calls[0][0];
    expect(chartCall.startDate).toBe(mockResults.execution?.started_at);
  });

  it('renders stop vertical line when task is stopped', async () => {
    const stoppedTask = {
      ...mockTask,
      status: TaskStatus.STOPPED,
    };

    const stoppedResults: TaskResults = {
      ...mockResults,
      status: TaskStatus.STOPPED,
      execution: {
        ...(mockResults.execution ?? {
          id: 1,
          execution_number: 1,
          status: TaskStatus.STOPPED,
          progress: 100,
        }),
        status: TaskStatus.STOPPED,
        completed_at: '2024-01-02T00:00:00Z',
      },
    };

    vi.mocked(useTradingResults).mockReturnValue({
      results: stoppedResults,
      isLoading: false,
      error: null,
      isPolling: false,
      refetch: vi.fn(),
    });

    render(<TaskPerformanceTab task={stoppedTask} />);

    await waitFor(() => {
      expect(screen.getByTestId('trading-task-chart')).toBeInTheDocument();
    });

    // Verify chart was called with stopDate
    const chartCall = vi.mocked(TradingTaskChart).mock.calls[0][0];
    expect(chartCall.stopDate).toBe(stoppedResults.execution?.completed_at);
    expect(chartCall.autoRefresh).toBe(false); // Stopped task has auto-refresh disabled
  });

  it('renders trade markers', async () => {
    render(<TaskPerformanceTab task={mockTask} />);

    await waitFor(() => {
      expect(screen.getByTestId('trading-task-chart')).toBeInTheDocument();
    });

    // Verify chart was called with trades
    const chartCall = vi.mocked(TradingTaskChart).mock.calls[0][0];
    expect(chartCall.trades).toEqual(mockResults.metrics?.trade_log);
  });

  it('enables auto-refresh for running tasks', async () => {
    render(<TaskPerformanceTab task={mockTask} />);

    await waitFor(() => {
      expect(screen.getByTestId('trading-task-chart')).toBeInTheDocument();
    });

    // Verify auto-refresh is enabled
    const chartCall = vi.mocked(TradingTaskChart).mock.calls[0][0];
    expect(chartCall.autoRefresh).toBe(true);
    expect(chartCall.refreshInterval).toBe(60000);
  });

  it('disables auto-refresh for stopped tasks', async () => {
    const stoppedTask = {
      ...mockTask,
      status: TaskStatus.STOPPED,
    };

    const stoppedResults: TaskResults = {
      ...mockResults,
      status: TaskStatus.STOPPED,
      execution: {
        ...(mockResults.execution ?? {
          id: 1,
          execution_number: 1,
          status: TaskStatus.STOPPED,
          progress: 100,
        }),
        status: TaskStatus.STOPPED,
        completed_at: '2024-01-02T00:00:00Z',
      },
    };

    vi.mocked(useTradingResults).mockReturnValue({
      results: stoppedResults,
      isLoading: false,
      error: null,
      isPolling: false,
      refetch: vi.fn(),
    });

    render(<TaskPerformanceTab task={stoppedTask} />);

    await waitFor(() => {
      expect(screen.getByTestId('trading-task-chart')).toBeInTheDocument();
    });

    // Verify auto-refresh is disabled
    const chartCall = vi.mocked(TradingTaskChart).mock.calls[0][0];
    expect(chartCall.autoRefresh).toBe(false);
  });

  it('handles trade click and highlights table row', async () => {
    const user = userEvent.setup();
    render(<TaskPerformanceTab task={mockTask} />);

    await waitFor(() => {
      expect(screen.getByTestId('trading-task-chart')).toBeInTheDocument();
    });

    // Initially no trade selected
    expect(screen.getByTestId('trade-log-table')).toHaveTextContent(
      'Selected: none'
    );

    // Click on trade marker 0
    const tradeMarker0 = screen.getByTestId('trade-marker-0');
    await user.click(tradeMarker0);

    // Verify trade 0 is selected
    await waitFor(() => {
      expect(screen.getByTestId('trade-log-table')).toHaveTextContent(
        'Selected: 0'
      );
    });

    // Click on trade marker 1
    const tradeMarker1 = screen.getByTestId('trade-marker-1');
    await user.click(tradeMarker1);

    // Verify trade 1 is selected
    await waitFor(() => {
      expect(screen.getByTestId('trade-log-table')).toHaveTextContent(
        'Selected: 1'
      );
    });
  });

  it('passes UTC timezone', async () => {
    render(<TaskPerformanceTab task={mockTask} />);

    await waitFor(() => {
      expect(screen.getByTestId('trading-task-chart')).toBeInTheDocument();
    });

    // Verify timezone is passed
    const chartCall = vi.mocked(TradingTaskChart).mock.calls[0][0];
    expect(chartCall.timezone).toBe('UTC');
  });

  it('handles task with no metrics', async () => {
    const noMetricsResults: TaskResults = {
      ...mockResults,
      has_metrics: false,
      metrics: null,
    };

    vi.mocked(useTradingResults).mockReturnValue({
      results: noMetricsResults,
      isLoading: false,
      error: null,
      isPolling: false,
      refetch: vi.fn(),
    });

    render(<TaskPerformanceTab task={mockTask} />);

    await waitFor(() => {
      expect(
        screen.getByText(/No performance metrics available yet/i)
      ).toBeInTheDocument();
    });

    // Chart should not be rendered
    expect(screen.queryByTestId('trading-task-chart')).not.toBeInTheDocument();
  });

  it('handles created task status', async () => {
    const createdTask = {
      ...mockTask,
      status: TaskStatus.CREATED,
    };

    render(<TaskPerformanceTab task={createdTask} />);

    await waitFor(() => {
      expect(
        screen.getByText(/This task has not been started yet/i)
      ).toBeInTheDocument();
    });

    // Chart should not be rendered
    expect(screen.queryByTestId('trading-task-chart')).not.toBeInTheDocument();
  });

  it('handles failed task status', async () => {
    const failedTask = {
      ...mockTask,
      status: TaskStatus.FAILED,
    };

    const failedResults: TaskResults = {
      ...mockResults,
      status: TaskStatus.FAILED,
      execution: {
        ...(mockResults.execution ?? {
          id: 1,
          execution_number: 1,
          status: TaskStatus.FAILED,
          progress: 0,
        }),
        status: TaskStatus.FAILED,
        error_message: 'Test error message',
      },
    };

    vi.mocked(useTradingResults).mockReturnValue({
      results: failedResults,
      isLoading: false,
      error: null,
      isPolling: false,
      refetch: vi.fn(),
    });

    render(<TaskPerformanceTab task={failedTask} />);

    await waitFor(() => {
      expect(
        screen.getByText(/This task execution failed/i)
      ).toBeInTheDocument();
      expect(screen.getByText(/Test error message/i)).toBeInTheDocument();
    });

    // Chart should not be rendered
    expect(screen.queryByTestId('trading-task-chart')).not.toBeInTheDocument();
  });

  it('shows loading state', async () => {
    vi.mocked(useTradingResults).mockReturnValue({
      results: null,
      isLoading: true,
      error: null,
      isPolling: false,
      refetch: vi.fn(),
    });

    render(<TaskPerformanceTab task={mockTask} />);

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('renders trade log table with trades', async () => {
    render(<TaskPerformanceTab task={mockTask} />);

    await waitFor(() => {
      expect(screen.getByTestId('trade-log-table')).toBeInTheDocument();
    });
  });

  it('renders metrics cards', async () => {
    render(<TaskPerformanceTab task={mockTask} />);

    await waitFor(() => {
      expect(screen.getByTestId('metric-total-return')).toHaveTextContent(
        '5.25%'
      );
      expect(screen.getByTestId('metric-win-rate')).toHaveTextContent('60.00%');
      expect(screen.getByTestId('metric-total-trades')).toHaveTextContent('10');
      expect(screen.getByTestId('metric-max-drawdown')).toHaveTextContent(
        '2.50%'
      );
    });
  });
});
