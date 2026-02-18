/**
 * Hook for computing Overview PnL from trades API.
 *
 * Uses the same calculation logic as TaskReplayPanel to ensure
 * consistent PnL values between Overview and Replay tabs.
 */

import { useState, useEffect, useMemo } from 'react';
import { TradingService } from '../api/generated/services/TradingService';
import type { ExecutionSummary } from '../types/execution';
import { TaskType } from '../types/common';

interface OverviewPnl {
  realizedPnl: number;
  unrealizedPnl: number;
  totalTrades: number;
}

export function useOverviewPnl(
  taskId: string,
  taskType: TaskType,
  latestExecution?: ExecutionSummary
): OverviewPnl {
  const [trades, setTrades] = useState<Array<{ pnl?: string | number | null }>>(
    []
  );

  useEffect(() => {
    if (!taskId) return;

    let cancelled = false;

    const fetchTrades = async () => {
      try {
        const response =
          taskType === TaskType.BACKTEST
            ? await TradingService.tradingTasksBacktestTradesList(taskId)
            : await TradingService.tradingTasksTradingTradesList(taskId);

        if (cancelled) return;

        const results = Array.isArray(
          (response as { results?: unknown[] })?.results
        )
          ? (response as { results: Array<{ pnl?: string | number | null }> })
              .results
          : Array.isArray(response)
            ? (response as Array<{ pnl?: string | number | null }>)
            : [];

        setTrades(results);
      } catch {
        // If trades fetch fails, leave empty — latestExecution fallback will apply
      }
    };

    fetchTrades();
    return () => {
      cancelled = true;
    };
  }, [taskId, taskType]);

  return useMemo(() => {
    // Same logic as TaskReplayPanel.replaySummary
    const pnlFromTrades = trades.reduce((sum, trade) => {
      const pnl = Number(trade.pnl);
      return Number.isFinite(pnl) ? sum + pnl : sum;
    }, 0);

    const realizedRaw =
      latestExecution?.realized_pnl !== undefined
        ? Number(latestExecution.realized_pnl)
        : pnlFromTrades;
    const unrealizedRaw =
      latestExecution?.unrealized_pnl !== undefined
        ? Number(latestExecution.unrealized_pnl)
        : 0;
    const totalTradesRaw =
      typeof latestExecution?.total_trades === 'number'
        ? latestExecution.total_trades
        : trades.length;

    return {
      realizedPnl: Number.isFinite(realizedRaw) ? realizedRaw : 0,
      unrealizedPnl: Number.isFinite(unrealizedRaw) ? unrealizedRaw : 0,
      totalTrades: totalTradesRaw,
    };
  }, [latestExecution, trades]);
}
