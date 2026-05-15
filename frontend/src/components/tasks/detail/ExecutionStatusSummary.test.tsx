import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { TaskSummary } from '../../../hooks/useTaskSummary';
import { ExecutionStatusSummary } from './ExecutionStatusSummary';

vi.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { timezone: 'UTC', language: 'en' },
  }),
}));

const baseSummary: TaskSummary = {
  timestamp: null,
  pnl: {
    realized: 0,
    unrealized: 0,
    currency: null,
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
    currentBalance: 10000,
    currentBalanceMoney: { amount: '10000', currency: 'JPY' },
    ticksProcessed: 0,
    accountCurrency: 'JPY',
    currentBalanceCurrency: 'JPY',
    currentBalanceDisplay: 67.89,
    currentBalanceDisplayMoney: { amount: '67.89', currency: 'USD' },
    currentBalanceDisplayConversionContext: null,
    displayCurrency: 'USD',
    resumeCursorTimestamp: null,
    marginRatio: null,
    currentAtr: null,
    recoveryStatus: null,
    recoveryWarnings: [],
    recoveryBlockers: [],
    reconciledAt: null,
    tickDelivery: null,
  },
  tick: { timestamp: null, bid: null, ask: null, mid: null },
  task: {
    status: '',
    startedAt: null,
    completedAt: null,
    errorMessage: null,
    errorCode: null,
    stopReason: null,
    progress: 0,
  },
};

describe('ExecutionStatusSummary', () => {
  it('shows current balance only in the configured display currency', () => {
    render(
      <ExecutionStatusSummary
        taskNamespace="backtest"
        summary={baseSummary}
        pnlCurrency="USD"
      />
    );

    expect(screen.getByText('$ 67.89')).toBeInTheDocument();
    expect(screen.queryByText(/¥ 10,000/)).not.toBeInTheDocument();
  });
});
