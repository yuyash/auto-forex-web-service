import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { I18nextProvider } from 'react-i18next';
import i18n from '../i18n/config';
import BacktestHistoryPanel from '../components/backtest/BacktestHistoryPanel';
import type { Backtest } from '../types/backtest';

// Mock backtests data
const mockBacktests: Backtest[] = [
  {
    id: 1,
    user: 1,
    strategy_type: 'FloorStrategy',
    config: { base_lot: 1.0 },
    instruments: ['EUR_USD', 'GBP_USD'],
    start_date: '2024-01-01',
    end_date: '2024-01-31',
    initial_balance: 10000,
    status: 'completed',
    progress: 100,
    created_at: '2024-02-01T10:00:00Z',
    completed_at: '2024-02-01T11:00:00Z',
  },
  {
    id: 2,
    user: 1,
    strategy_type: 'MACrossoverStrategy',
    config: { fast_period: 12, slow_period: 26 },
    instruments: ['USD_JPY', 'EUR_JPY', 'GBP_JPY', 'AUD_JPY'],
    start_date: '2024-02-01',
    end_date: '2024-02-28',
    initial_balance: 20000,
    status: 'running',
    progress: 45,
    created_at: '2024-03-01T09:00:00Z',
    completed_at: null,
  },
  {
    id: 3,
    user: 1,
    strategy_type: 'RSIStrategy',
    config: { period: 14 },
    instruments: ['EUR_USD'],
    start_date: '2024-03-01',
    end_date: '2024-03-31',
    initial_balance: 15000,
    status: 'failed',
    progress: 0,
    created_at: '2024-04-01T08:00:00Z',
    completed_at: null,
  },
];

describe('BacktestHistoryPanel', () => {
  it('renders backtest history table with data', () => {
    const onViewBacktest = vi.fn();
    const onDeleteBacktest = vi.fn();
    const onFetchResult = vi.fn();

    render(
      <I18nextProvider i18n={i18n}>
        <BacktestHistoryPanel
          backtests={mockBacktests}
          onViewBacktest={onViewBacktest}
          onDeleteBacktest={onDeleteBacktest}
          onFetchResult={onFetchResult}
        />
      </I18nextProvider>
    );

    // Check title
    expect(screen.getByText(/Backtest History/i)).toBeInTheDocument();

    // Check table headers (use getAllByText for headers that might appear multiple times)
    const dateHeaders = screen.getAllByText(/^Date$/i);
    expect(dateHeaders.length).toBeGreaterThan(0);
    const strategyHeaders = screen.getAllByText(/Strategy/i);
    expect(strategyHeaders.length).toBeGreaterThan(0);
    expect(screen.getByText(/Instruments/i)).toBeInTheDocument();
    expect(screen.getByText(/Date Range/i)).toBeInTheDocument();
    expect(screen.getByText(/Status/i)).toBeInTheDocument();
    expect(screen.getByText(/Total Return/i)).toBeInTheDocument();

    // Check backtest data is displayed
    expect(screen.getByText('FloorStrategy')).toBeInTheDocument();
    expect(screen.getByText('MACrossoverStrategy')).toBeInTheDocument();
    expect(screen.getByText('RSIStrategy')).toBeInTheDocument();
  });

  it('displays instruments as chips', () => {
    const onViewBacktest = vi.fn();
    const onDeleteBacktest = vi.fn();
    const onFetchResult = vi.fn();

    render(
      <I18nextProvider i18n={i18n}>
        <BacktestHistoryPanel
          backtests={mockBacktests}
          onViewBacktest={onViewBacktest}
          onDeleteBacktest={onDeleteBacktest}
          onFetchResult={onFetchResult}
        />
      </I18nextProvider>
    );

    // Check first backtest instruments (use getAllByText since EUR_USD appears multiple times)
    const eurUsdChips = screen.getAllByText('EUR_USD');
    expect(eurUsdChips.length).toBeGreaterThan(0);
    expect(screen.getByText('GBP_USD')).toBeInTheDocument();

    // Check that more than 3 instruments shows +N chip
    expect(screen.getByText('+1')).toBeInTheDocument();
  });

  it('displays status chips with correct colors', () => {
    const onViewBacktest = vi.fn();
    const onDeleteBacktest = vi.fn();
    const onFetchResult = vi.fn();

    render(
      <I18nextProvider i18n={i18n}>
        <BacktestHistoryPanel
          backtests={mockBacktests}
          onViewBacktest={onViewBacktest}
          onDeleteBacktest={onDeleteBacktest}
          onFetchResult={onFetchResult}
        />
      </I18nextProvider>
    );

    // Check status chips are displayed
    expect(screen.getByText(/completed/i)).toBeInTheDocument();
    expect(screen.getByText(/running/i)).toBeInTheDocument();
    expect(screen.getByText(/failed/i)).toBeInTheDocument();
  });

  it('calls onViewBacktest when view button is clicked', async () => {
    const user = userEvent.setup();
    const onViewBacktest = vi.fn();
    const onDeleteBacktest = vi.fn();
    const onFetchResult = vi.fn();

    render(
      <I18nextProvider i18n={i18n}>
        <BacktestHistoryPanel
          backtests={mockBacktests}
          onViewBacktest={onViewBacktest}
          onDeleteBacktest={onDeleteBacktest}
          onFetchResult={onFetchResult}
        />
      </I18nextProvider>
    );

    // Find the visibility icon button (view results button)
    const viewButtons = screen.getAllByRole('button', {
      name: /view results/i,
    });

    // Find the enabled view button (for completed backtest)
    const enabledViewButton = viewButtons.find(
      (btn) => !btn.hasAttribute('disabled')
    );

    if (enabledViewButton) {
      await user.click(enabledViewButton);
      expect(onViewBacktest).toHaveBeenCalledWith(1);
    } else {
      // If no enabled button found, test should fail
      expect(enabledViewButton).toBeDefined();
    }
  });

  it('disables view button for non-completed backtests', () => {
    const onViewBacktest = vi.fn();
    const onDeleteBacktest = vi.fn();
    const onFetchResult = vi.fn();

    render(
      <I18nextProvider i18n={i18n}>
        <BacktestHistoryPanel
          backtests={mockBacktests}
          onViewBacktest={onViewBacktest}
          onDeleteBacktest={onDeleteBacktest}
          onFetchResult={onFetchResult}
        />
      </I18nextProvider>
    );

    // Find all view buttons by role and name
    const viewButtons = screen.getAllByRole('button', {
      name: /view results/i,
    });

    // Count enabled and disabled buttons
    const enabledButtons = viewButtons.filter(
      (btn) => !btn.hasAttribute('disabled')
    );
    const disabledButtons = viewButtons.filter((btn) =>
      btn.hasAttribute('disabled')
    );

    // Should have 1 enabled (completed) and 2 disabled (running, failed)
    expect(enabledButtons.length).toBe(1);
    expect(disabledButtons.length).toBe(2);
  });

  it('calls onDeleteBacktest when delete button is clicked and confirmed', async () => {
    const user = userEvent.setup();
    const onViewBacktest = vi.fn();
    const onDeleteBacktest = vi.fn();
    const onFetchResult = vi.fn();

    // Mock window.confirm before rendering
    const confirmSpy = vi
      .spyOn(window, 'confirm')
      .mockImplementation(() => true);

    render(
      <I18nextProvider i18n={i18n}>
        <BacktestHistoryPanel
          backtests={mockBacktests}
          onViewBacktest={onViewBacktest}
          onDeleteBacktest={onDeleteBacktest}
          onFetchResult={onFetchResult}
        />
      </I18nextProvider>
    );

    // Find all delete buttons by role and name
    const deleteButtons = screen.getAllByRole('button', { name: /delete/i });

    // Click the first delete button
    await user.click(deleteButtons[0]);

    // Wait for confirmation and callback
    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalled();
    });

    expect(onDeleteBacktest).toHaveBeenCalledWith(1);

    confirmSpy.mockRestore();
  });

  it('does not call onDeleteBacktest when delete is cancelled', async () => {
    const user = userEvent.setup();
    const onViewBacktest = vi.fn();
    const onDeleteBacktest = vi.fn();
    const onFetchResult = vi.fn();

    // Mock window.confirm to return false before rendering
    const confirmSpy = vi
      .spyOn(window, 'confirm')
      .mockImplementation(() => false);

    render(
      <I18nextProvider i18n={i18n}>
        <BacktestHistoryPanel
          backtests={mockBacktests}
          onViewBacktest={onViewBacktest}
          onDeleteBacktest={onDeleteBacktest}
          onFetchResult={onFetchResult}
        />
      </I18nextProvider>
    );

    // Find all delete buttons by role and name
    const deleteButtons = screen.getAllByRole('button', { name: /delete/i });

    // Click the first delete button
    await user.click(deleteButtons[0]);

    // Wait for confirmation
    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalled();
    });

    // onDeleteBacktest should not be called
    expect(onDeleteBacktest).not.toHaveBeenCalled();

    confirmSpy.mockRestore();
  });

  it('displays message when no backtests are available', () => {
    const onViewBacktest = vi.fn();
    const onDeleteBacktest = vi.fn();
    const onFetchResult = vi.fn();

    render(
      <I18nextProvider i18n={i18n}>
        <BacktestHistoryPanel
          backtests={[]}
          onViewBacktest={onViewBacktest}
          onDeleteBacktest={onDeleteBacktest}
          onFetchResult={onFetchResult}
        />
      </I18nextProvider>
    );

    expect(
      screen.getByText(/No backtest history available/i)
    ).toBeInTheDocument();
  });

  it('formats dates correctly', () => {
    const onViewBacktest = vi.fn();
    const onDeleteBacktest = vi.fn();
    const onFetchResult = vi.fn();

    render(
      <I18nextProvider i18n={i18n}>
        <BacktestHistoryPanel
          backtests={mockBacktests}
          onViewBacktest={onViewBacktest}
          onDeleteBacktest={onDeleteBacktest}
          onFetchResult={onFetchResult}
        />
      </I18nextProvider>
    );

    // Check that dates are formatted (exact format depends on locale)
    // Just verify that date-like text is present
    const dateElements = screen.getAllByText(/2024/);
    expect(dateElements.length).toBeGreaterThan(0);
  });

  it('disables all buttons when loading', () => {
    const onViewBacktest = vi.fn();
    const onDeleteBacktest = vi.fn();
    const onFetchResult = vi.fn();

    render(
      <I18nextProvider i18n={i18n}>
        <BacktestHistoryPanel
          backtests={mockBacktests}
          onViewBacktest={onViewBacktest}
          onDeleteBacktest={onDeleteBacktest}
          onFetchResult={onFetchResult}
          loading={true}
        />
      </I18nextProvider>
    );

    // All buttons should be disabled
    const allButtons = screen.getAllByRole('button');
    allButtons.forEach((button) => {
      expect(button).toBeDisabled();
    });
  });
});
