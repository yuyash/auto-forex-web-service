import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import BacktestResultsPanel from '../components/backtest/BacktestResultsPanel';
import type { BacktestResult } from '../types/backtest';
import '../i18n/config';

// Mock lightweight-charts
vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => ({
    addLineSeries: vi.fn(() => ({
      setData: vi.fn(),
    })),
    addHistogramSeries: vi.fn(() => ({
      setData: vi.fn(),
    })),
    timeScale: vi.fn(() => ({
      fitContent: vi.fn(),
    })),
    remove: vi.fn(),
  })),
  ColorType: {
    Solid: 0,
  },
}));

describe('BacktestResultsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockResult: BacktestResult = {
    id: 1,
    backtest: 1,
    final_balance: 11500,
    total_return: 15.0,
    max_drawdown: -8.5,
    sharpe_ratio: 1.8,
    total_trades: 45,
    winning_trades: 28,
    losing_trades: 17,
    win_rate: 62.2,
    average_win: 250.0,
    average_loss: -150.0,
    profit_factor: 1.67,
    equity_curve: [
      { timestamp: '2024-01-01T00:00:00Z', balance: 10000 },
      { timestamp: '2024-01-02T00:00:00Z', balance: 10250 },
      { timestamp: '2024-01-03T00:00:00Z', balance: 10500 },
      { timestamp: '2024-01-04T00:00:00Z', balance: 10750 },
      { timestamp: '2024-01-05T00:00:00Z', balance: 11000 },
    ],
    trade_log: [
      {
        timestamp: '2024-01-01T10:00:00Z',
        instrument: 'EUR_USD',
        direction: 'long',
        entry_price: 1.1,
        exit_price: 1.105,
        units: 10000,
        pnl: 50,
        duration: 3600,
      },
      {
        timestamp: '2024-01-02T10:00:00Z',
        instrument: 'GBP_USD',
        direction: 'short',
        entry_price: 1.25,
        exit_price: 1.245,
        units: 10000,
        pnl: 50,
        duration: 1800,
      },
    ],
  };

  it('renders no results message when result is null', () => {
    render(<BacktestResultsPanel result={null} />);
    expect(screen.getByText(/No results available/i)).toBeInTheDocument();
  });

  it('renders performance metrics cards', () => {
    render(<BacktestResultsPanel result={mockResult} />);

    // Check for metric titles
    expect(screen.getByText('Total Return')).toBeInTheDocument();
    expect(screen.getByText('Max Drawdown')).toBeInTheDocument();
    expect(screen.getByText('Sharpe Ratio')).toBeInTheDocument();
    expect(screen.getByText('Win Rate')).toBeInTheDocument();
    expect(screen.getByText('Profit Factor')).toBeInTheDocument();
    expect(screen.getByText('Total Trades')).toBeInTheDocument();
    expect(screen.getByText('Avg Win')).toBeInTheDocument();
    expect(screen.getByText('Avg Loss')).toBeInTheDocument();
  });

  it('displays correct metric values', () => {
    render(<BacktestResultsPanel result={mockResult} />);

    // Check for metric values
    expect(screen.getByText('15.00%')).toBeInTheDocument();
    expect(screen.getByText('-8.50%')).toBeInTheDocument();
    expect(screen.getByText('1.80')).toBeInTheDocument();
    expect(screen.getByText('62.2%')).toBeInTheDocument();
    expect(screen.getByText('1.67')).toBeInTheDocument();
    expect(screen.getByText('45')).toBeInTheDocument();
    expect(screen.getByText('$250.00')).toBeInTheDocument();
    expect(screen.getByText('$150.00')).toBeInTheDocument();
  });

  it('renders chart titles', () => {
    render(<BacktestResultsPanel result={mockResult} />);

    expect(screen.getByText('Equity Curve')).toBeInTheDocument();
    expect(screen.getByText('Drawdown')).toBeInTheDocument();
    expect(screen.getByText('Trade Distribution')).toBeInTheDocument();
    expect(screen.getByText('Monthly Returns')).toBeInTheDocument();
  });

  it('displays winning and losing trades count', () => {
    render(<BacktestResultsPanel result={mockResult} />);

    expect(screen.getByText('28W / 17L')).toBeInTheDocument();
  });

  it('displays win rate with trade count', () => {
    render(<BacktestResultsPanel result={mockResult} />);

    expect(screen.getByText('28/45 trades')).toBeInTheDocument();
  });
});
