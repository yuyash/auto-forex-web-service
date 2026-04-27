import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { NetGridStrategyPanel } from '../../../../../../src/components/tasks/detail/strategy/NetGridStrategyPanel';
import type { NetGridStrategyState } from '../../../../../../src/types/strategyVisualization';

vi.mock(
  '../../../../../../src/components/tasks/detail/strategy/StrategyGroupChart',
  () => ({
    StrategyGroupChart: () => <div data-testid="strategy-chart" />,
  })
);

const state: NetGridStrategyState = {
  current_net_units: 2000,
  target_net_units: 2000,
  open_units: 2000,
  open_direction: 'long',
  average_entry_price: '150.100',
  last_grid_price: '149.900',
  net_take_profit_price: '150.200',
  next_grid_price: '149.700',
  risk_exit_price: '148.100',
  take_profit_remaining_pips: '10',
  current_atr_pips: '5',
  trend_score_pips: '1.5',
  effective_grid_interval_pips: '20',
  effective_take_profit_pips: '8',
  effective_order_size_multiplier: '0.5',
  current_adverse_pips: '25',
  current_unrealized_pnl: '-12.5',
  next_order_units: 500,
  max_net_units: 10000,
  max_adverse_pips: '200',
  max_loss: '100',
  regime_status: 'blocked_counter_trend',
  step: 2,
  step_usage: '0.4',
  max_steps: 5,
  started_at: '2026-01-01T00:00:00Z',
  last_tick_at: '2026-01-01T00:01:00Z',
  grid_ledger: [
    {
      timestamp: '2026-01-01T00:00:30Z',
      action: 'add',
      reason: 'grid_interval_hit',
      units_delta: 1000,
      filled_price: '149.900',
      net_units_before: 1000,
      net_units_after: 2000,
      realized_pnl: '0',
      source: 'event_execution',
    },
  ],
};

describe('NetGridStrategyPanel', () => {
  it('renders risk preview, risk line toggle, and localized ledger labels', () => {
    render(
      <NetGridStrategyPanel
        state={state}
        instrument="USD_JPY"
        taskId="task-1"
        taskType="backtest"
        executionRunId="run-1"
        lastTickTimestamp="2026-01-01T00:01:00Z"
      />
    );

    expect(screen.getByText('Next Decision Preview')).toBeInTheDocument();
    expect(screen.getByText('Risk-exit price')).toBeInTheDocument();
    expect(screen.getByText('Risk Exit')).toBeInTheDocument();
    expect(screen.getByText('Counter-trend blocked')).toBeInTheDocument();
    expect(screen.getByText('Add exposure')).toBeInTheDocument();
    expect(screen.getByText('Grid interval hit')).toBeInTheDocument();
    expect(screen.getByText('Unrealized loss')).toBeInTheDocument();
  });
});
