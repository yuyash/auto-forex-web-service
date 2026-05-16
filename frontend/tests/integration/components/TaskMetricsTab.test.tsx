import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TaskMetricsTab } from '../../../src/components/tasks/detail/TaskMetricsTab';
import type { MetricPoint } from '../../../src/utils/fetchMetrics';

const lineChartProps = vi.hoisted(
  () =>
    [] as Array<{
      series?: Array<{ label?: string; data?: Array<number | null> }>;
    }>
);
const barChartProps = vi.hoisted(
  () =>
    [] as Array<{
      xAxis?: Array<{ data?: string[] }>;
    }>
);

vi.mock('@mui/x-charts/LineChart', () => ({
  LineChart: (props: {
    series?: Array<{ label?: string; data?: Array<number | null> }>;
  }) => {
    lineChartProps.push(props);
    return <div data-testid="line-chart" />;
  },
}));

vi.mock('@mui/x-charts/BarChart', () => ({
  BarChart: (props: { xAxis?: Array<{ data?: string[] }> }) => {
    barChartProps.push(props);
    return <div data-testid="bar-chart" />;
  },
}));

describe('TaskMetricsTab', () => {
  beforeEach(() => {
    lineChartProps.length = 0;
    barChartProps.length = 0;
  });

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
          snowball_net_current_price: 156 + index * 0.01,
          snowball_net_target_price: 156.2 + index * 0.01,
          snowball_net_next_add_price: 155.9 - index * 0.01,
          snowball_net_theoretical_next_add_price: 155.7 - index * 0.01,
          snowball_net_pips_from_average: 4 + index,
          snowball_net_margin_ratio_pct: 34 + index,
          snowball_net_next_add_distance_pips: 12 - index,
          snowball_net_loss_cut_threshold_pips: -120,
          snowball_net_margin_reduce_threshold_pct: 85,
          snowball_net_margin_reduce_target_pct: 70,
          snowball_net_emergency_threshold_pct: 95,
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

    expect(screen.getByText('Price Levels')).toBeInTheDocument();
    expect(screen.getByText('Pips From Average')).toBeInTheDocument();
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
    expect(screen.queryByText('Exit Price')).not.toBeInTheDocument();
    expect(screen.queryByText('Next Add Price')).not.toBeInTheDocument();
    expect(screen.queryByText('Current Net Price')).not.toBeInTheDocument();
    expect(
      screen.queryByText('Theoretical Next Add Price')
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Next Add Distance')).not.toBeInTheDocument();
    expect(screen.queryByText('Loss Cut Threshold')).not.toBeInTheDocument();
    expect(
      screen.queryByText('Margin Reduce Threshold')
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Margin Reduce Target')).not.toBeInTheDocument();
    expect(
      screen.queryByText('Emergency Stop Threshold')
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Win Rate')).not.toBeInTheDocument();
    expect(screen.queryByText('Winning Trades')).not.toBeInTheDocument();
    expect(screen.queryByText('Losing Trades')).not.toBeInTheDocument();

    const lineChartLabels = lineChartProps.map(
      (props) => props.series?.map((series) => series.label ?? '') ?? []
    );
    const hasChartWithLabels = (...labels: string[]) =>
      lineChartLabels.some((chartLabels) =>
        labels.every((label) => chartLabels.includes(label))
      );
    const hasSingleSeriesChart = (label: string) =>
      lineChartLabels.some(
        (chartLabels) => chartLabels.length === 1 && chartLabels[0] === label
      );

    expect(
      hasChartWithLabels('Next Add Price', 'Current Net Price', 'Exit Price')
    ).toBe(true);
    expect(hasChartWithLabels('Pips From Average', 'Loss Cut Threshold')).toBe(
      true
    );
    expect(
      hasChartWithLabels(
        'Margin Closeout Ratio',
        'Margin Reduce Threshold',
        'Margin Reduce Target',
        'Emergency Stop Threshold'
      )
    ).toBe(true);
    expect(hasSingleSeriesChart('Current Net Price')).toBe(false);
    expect(hasSingleSeriesChart('Exit Price')).toBe(false);
    expect(hasSingleSeriesChart('Next Add Price')).toBe(false);
    expect(hasSingleSeriesChart('Margin Reduce Threshold')).toBe(false);
    expect(hasSingleSeriesChart('Margin Reduce Target')).toBe(false);
    expect(hasSingleSeriesChart('Emergency Stop Threshold')).toBe(false);
    expect(lineChartLabels.flat().includes('Theoretical Next Add Price')).toBe(
      false
    );
    expect(lineChartLabels.flat().includes('Next Add Distance')).toBe(false);
  });

  it('labels weekly period returns by the week start date', () => {
    const data: MetricPoint[] = [
      ['2026-01-06T00:00:00Z', 0],
      ['2026-01-09T00:00:00Z', 0.02],
      ['2026-01-13T00:00:00Z', 0.02],
      ['2026-01-16T00:00:00Z', 0.05],
    ].map(([iso, totalReturn]) => ({
      t: Math.floor(new Date(iso).getTime() / 1000),
      metrics: {
        total_return: totalReturn,
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
        timezone="UTC"
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Weekly Return' }));

    const latestBarChart = barChartProps.at(-1);
    expect(latestBarChart?.xAxis?.[0]?.data).toEqual([
      '2026-01-05',
      '2026-01-12',
    ]);
    expect(latestBarChart?.xAxis?.[0]?.data).not.toContain('2026-W02');
  });
});
