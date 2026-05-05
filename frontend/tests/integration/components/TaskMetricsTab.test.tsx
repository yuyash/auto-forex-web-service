import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { TaskMetricsTab } from '../../../src/components/tasks/detail/TaskMetricsTab';
import type { MetricPoint } from '../../../src/utils/fetchMetrics';

vi.mock('@mui/x-charts/LineChart', () => ({
  LineChart: () => <div data-testid="line-chart" />,
}));

describe('TaskMetricsTab', () => {
  it('renders large metric series without overflowing the call stack', () => {
    const data: MetricPoint[] = Array.from({ length: 150_000 }, (_, index) => ({
      t: 1_700_000_000 + index * 60,
      metrics: {
        current_balance: 10_000 + index * 0.01,
      },
    }));

    render(
      <TaskMetricsTab
        data={data}
        isLoading={false}
        error={null}
        interval={1}
        since=""
        until=""
        onIntervalChange={vi.fn()}
        onSinceChange={vi.fn()}
        onUntilChange={vi.fn()}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
  });

  it('renders SnowballNet strategy chart metrics without win/loss charts', () => {
    const data: MetricPoint[] = [1_700_000_000, 1_700_000_060].map(
      (t, index) => ({
        t,
        metrics: {
          total_pnl: 100 + index,
          total_pnl_quote: 100 + index,
          realized_pnl: 80 + index,
          realized_pnl_quote: 80 + index,
          unrealized_pnl: 20 + index,
          unrealized_pnl_quote: 20 + index,
          margin_ratio: 0.34 + index * 0.01,
          snowball_net_target_price: 156.2 + index * 0.01,
          snowball_net_next_add_price: 155.9 - index * 0.01,
          snowball_net_margin_ratio_pct: 34 + index,
          win_rate: 50,
          winning_trades: 1,
          losing_trades: 1,
        },
      })
    );

    render(
      <TaskMetricsTab
        data={data}
        isLoading={false}
        error={null}
        interval={1}
        since=""
        until=""
        onIntervalChange={vi.fn()}
        onSinceChange={vi.fn()}
        onUntilChange={vi.fn()}
        onRefresh={vi.fn()}
        strategyType="snowball_net"
      />
    );

    expect(screen.getByText('Exit Price')).toBeInTheDocument();
    expect(screen.getByText('Next Add Price')).toBeInTheDocument();
    expect(screen.getByText('Margin Closeout Ratio')).toBeInTheDocument();
    expect(screen.getByText('Total PnL')).toBeInTheDocument();
    expect(screen.getByText('Realized PnL')).toBeInTheDocument();
    expect(screen.getByText('Unrealized PnL')).toBeInTheDocument();
    expect(screen.queryByText('Total PnL (Quote)')).not.toBeInTheDocument();
    expect(screen.queryByText('Realized PnL (Quote)')).not.toBeInTheDocument();
    expect(
      screen.queryByText('Unrealized PnL (Quote)')
    ).not.toBeInTheDocument();
    expect(screen.getAllByText('Margin Closeout Ratio')).toHaveLength(1);
    expect(screen.queryByText('Win Rate')).not.toBeInTheDocument();
    expect(screen.queryByText('Winning Trades')).not.toBeInTheDocument();
    expect(screen.queryByText('Losing Trades')).not.toBeInTheDocument();
  });
});
