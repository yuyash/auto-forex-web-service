/**
 * Hook for computing Overview PnL from trades API.
 *
 * Uses the same calculation logic as TaskReplayPanel to ensure
 * consistent PnL values between Overview and Replay tabs.
 *
 * Fetches all trade pages to compute accurate totals.
 */

import { useState, useEffect, useMemo } from 'react';
import { fetchAllTrades } from '../utils/fetchAllTrades';
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

    const load = async () => {
      try {
        const allTrades = await fetchAllTrades(taskId, taskType);
        if (!cancelled) setTrades(allTrades);
      } catch {
        // If trades fetch fails, leave empty — latestExecution fallback will apply
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [taskId, taskType]);

  return useMemo(() => {
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
