import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ExecutionStatusSummary } from '../../../src/components/tasks/detail/ExecutionStatusSummary';
import type { TaskSummary } from '../../../src/hooks/useTaskSummary';

vi.mock('../../../src/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { timezone: 'UTC', language: 'en' },
  }),
}));

const summary: TaskSummary = {
  timestamp: null,
  pnl: {
    realized: 0,
    unrealized: 0,
    currency: 'JPY',
    realizedMoney: null,
    unrealizedMoney: null,
    totalMoney: null,
    realizedDisplayMoney: null,
    unrealizedDisplayMoney: null,
    totalDisplayMoney: null,
    displayConversionContext: null,
  },
  counts: {
    totalTrades: 0,
    openPositions: 0,
    closedPositions: 0,
    openLongUnits: 0,
    openShortUnits: 0,
    winningTrades: 0,
    losingTrades: 0,
  },
  execution: {
    currentBalance: null,
    currentBalanceMoney: null,
    ticksProcessed: 0,
    accountCurrency: 'JPY',
    currentBalanceCurrency: null,
    currentBalanceDisplay: null,
    currentBalanceDisplayMoney: null,
    currentBalanceDisplayConversionContext: null,
    displayCurrency: 'JPY',
    resumeCursorTimestamp: null,
    marginRatio: null,
    currentAtr: null,
    recoveryStatus: null,
    recoveryWarnings: [],
    recoveryBlockers: [],
    reconciledAt: null,
    tickDelivery: null,
  },
  tick: {
    timestamp: null,
    bid: null,
    ask: null,
    mid: null,
  },
  task: {
    status: 'running',
    startedAt: null,
    completedAt: null,
    errorMessage: null,
    errorCode: null,
    stopReason: null,
    progress: 0,
  },
};

describe('ExecutionStatusSummary', () => {
  it('shows the current base units metric in execution status', () => {
    render(
      <ExecutionStatusSummary
        taskNamespace="backtest"
        summary={summary}
        pnlCurrency="JPY"
        latestMetrics={{
          t: 1_767_225_600,
          metrics: {
            current_base_units: '1200',
          },
        }}
      />
    );

    expect(screen.getByText('Current Base Units')).toBeInTheDocument();
    expect(screen.getByText('1,200')).toBeInTheDocument();
  });
});
