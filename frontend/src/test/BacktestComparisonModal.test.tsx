import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { I18nextProvider } from 'react-i18next';
import i18n from '../i18n/config';
import BacktestComparisonModal from '../components/backtest/BacktestComparisonModal';
import type { Backtest, BacktestResult } from '../types/backtest';

// Mock lightweight-charts
vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => ({
    addLineSeries: vi.fn(() => ({
      setData: vi.fn(),
    })),
    timeScale: vi.fn(() => ({
      fitContent: vi.fn(),
    })),
    remove: vi.fn(),
  })),
}));

const mockBacktests: Backtest[] = [
  {
    id: 1,
    user: 1,
    strategy_type: 'MA Crossover',
    config: {},
    instrument: 'EUR_USD',
    start_date: '2024-01-01',
    end_date: '2024-03-31',
    initial_balance: 10000,
    status: 'completed',
    progress: 100,
    created_at: '2024-04-01T10:00:00Z',
    completed_at: '2024-04-01T11:00:00Z',
  },
  {
    id: 2,
    user: 1,
    strategy_type: 'RSI Strategy',
    config: {},
    instrument: 'EUR_USD',
    start_date: '2024-01-01',
    end_date: '2024-03-31',
    initial_balance: 10000,
    status: 'completed',
    progress: 100,
    created_at: '2024-04-02T10:00:00Z',
    completed_at: '2024-04-02T11:00:00Z',
  },
  {
    id: 3,
    user: 1,
    strategy_type: 'MACD Strategy',
    config: {},
    instrument: 'GBP_USD',
    start_date: '2024-01-01',
    end_date: '2024-03-31',
    initial_balance: 10000,
    status: 'running',
    progress: 50,
    created_at: '2024-04-03T10:00:00Z',
    completed_at: null,
  },
];

const mockResult: BacktestResult = {
  id: 1,
  backtest: 1,
  final_balance: 12000,
  total_return: 20.0,
  max_drawdown: -5.5,
  sharpe_ratio: 1.8,
  total_trades: 100,
  winning_trades: 60,
  losing_trades: 40,
  win_rate: 60.0,
  average_win: 150.0,
  average_loss: -80.0,
  profit_factor: 1.875,
  equity_curve: [
    { timestamp: '2024-01-01T00:00:00Z', balance: 10000 },
    { timestamp: '2024-02-01T00:00:00Z', balance: 11000 },
    { timestamp: '2024-03-01T00:00:00Z', balance: 12000 },
  ],
  trade_log: [
    {
      timestamp: '2024-01-15T10:00:00Z',
      instrument: 'EUR_USD',
      direction: 'long',
      entry_price: 1.1,
      exit_price: 1.12,
      units: 1000,
      pnl: 200,
      duration: 3600,
    },
  ],
};

describe('BacktestComparisonModal', () => {
  const mockOnClose = vi.fn();
  const mockOnFetchResult = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnFetchResult.mockResolvedValue(mockResult);
  });

  const renderComponent = (props = {}) => {
    return render(
      <I18nextProvider i18n={i18n}>
        <BacktestComparisonModal
          open={true}
          onClose={mockOnClose}
          backtests={mockBacktests}
          onFetchResult={mockOnFetchResult}
          {...props}
        />
      </I18nextProvider>
    );
  };

  it('renders modal with title', () => {
    renderComponent();
    expect(screen.getByText(/Compare Backtests/i)).toBeInTheDocument();
  });

  it('displays instructions', () => {
    renderComponent();
    expect(
      screen.getByText(/Select up to 4 backtests to compare/i)
    ).toBeInTheDocument();
  });

  it('shows only completed backtests for selection', () => {
    renderComponent();

    // Should show 2 completed backtests
    expect(screen.getByText(/MA Crossover/)).toBeInTheDocument();
    expect(screen.getByText(/RSI Strategy/)).toBeInTheDocument();

    // Should not show running backtest
    expect(screen.queryByText(/MACD Strategy/)).not.toBeInTheDocument();
  });

  it('allows selecting a backtest', async () => {
    const user = userEvent.setup();
    renderComponent();

    const checkbox = screen.getAllByRole('checkbox')[0];
    await user.click(checkbox);

    await waitFor(() => {
      expect(mockOnFetchResult).toHaveBeenCalledWith(1);
    });
  });

  it('prevents selecting more than 4 backtests', async () => {
    const user = userEvent.setup();
    const manyBacktests = [
      ...mockBacktests.slice(0, 2),
      { ...mockBacktests[0], id: 4, created_at: '2024-04-04T10:00:00Z' },
      { ...mockBacktests[0], id: 5, created_at: '2024-04-05T10:00:00Z' },
      { ...mockBacktests[0], id: 6, created_at: '2024-04-06T10:00:00Z' },
    ];

    render(
      <I18nextProvider i18n={i18n}>
        <BacktestComparisonModal
          open={true}
          onClose={mockOnClose}
          backtests={manyBacktests}
          onFetchResult={mockOnFetchResult}
        />
      </I18nextProvider>
    );

    const checkboxes = screen.getAllByRole('checkbox');

    // Select first 4
    for (let i = 0; i < 4; i++) {
      await user.click(checkboxes[i]);
    }

    // Try to select 5th
    await user.click(checkboxes[4]);

    // Should show error
    await waitFor(() => {
      expect(
        screen.getByText(/You can only compare up to 4 backtests at a time/i)
      ).toBeInTheDocument();
    });
  });

  it('displays comparison table when backtests are selected', async () => {
    const user = userEvent.setup();
    renderComponent();

    const checkbox = screen.getAllByRole('checkbox')[0];
    await user.click(checkbox);

    await waitFor(() => {
      expect(screen.getByText(/Metrics Comparison/i)).toBeInTheDocument();
      expect(screen.getByText(/Total Return/i)).toBeInTheDocument();
      expect(screen.getByText(/Max Drawdown/i)).toBeInTheDocument();
      expect(screen.getByText(/Sharpe Ratio/i)).toBeInTheDocument();
    });
  });

  it('displays equity curves section when backtests are selected', async () => {
    const user = userEvent.setup();
    renderComponent();

    const checkbox = screen.getAllByRole('checkbox')[0];
    await user.click(checkbox);

    await waitFor(() => {
      expect(screen.getByText(/Equity Curves/i)).toBeInTheDocument();
    });
  });

  it('displays statistical significance when 2+ backtests selected', async () => {
    const user = userEvent.setup();
    renderComponent();

    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[0]);
    await user.click(checkboxes[1]);

    await waitFor(() => {
      expect(screen.getByText(/Statistical Significance/i)).toBeInTheDocument();
      expect(screen.getByText(/t-Statistic/i)).toBeInTheDocument();
      expect(screen.getByText(/p-Value/i)).toBeInTheDocument();
    });
  });

  it('handles fetch error gracefully', async () => {
    const user = userEvent.setup();
    mockOnFetchResult.mockRejectedValueOnce(new Error('Fetch failed'));

    renderComponent();

    const checkbox = screen.getAllByRole('checkbox')[0];
    await user.click(checkbox);

    await waitFor(() => {
      expect(
        screen.getByText(/Failed to fetch backtest results/i)
      ).toBeInTheDocument();
    });
  });

  it('calls onClose when close button is clicked', async () => {
    const user = userEvent.setup();
    renderComponent();

    const closeButton = screen.getByRole('button', { name: /close/i });
    await user.click(closeButton);

    expect(mockOnClose).toHaveBeenCalled();
  });

  it('shows no selection message when no backtests selected', () => {
    renderComponent();
    expect(
      screen.getByText(/Select backtests above to compare their performance/i)
    ).toBeInTheDocument();
  });

  it('deselects a backtest when clicked again', async () => {
    const user = userEvent.setup();
    renderComponent();

    const checkbox = screen.getAllByRole('checkbox')[0];

    // Select
    await user.click(checkbox);
    await waitFor(() => {
      expect(mockOnFetchResult).toHaveBeenCalledWith(1);
    });

    // Deselect
    await user.click(checkbox);

    await waitFor(() => {
      expect(
        screen.getByText(/Select backtests above to compare their performance/i)
      ).toBeInTheDocument();
    });
  });
});
