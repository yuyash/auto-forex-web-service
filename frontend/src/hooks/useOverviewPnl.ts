/**
 * Hook for computing Overview PnL from positions API.
 *
 * Both Realized and Unrealized PnL are derived exclusively from the
 * Positions API so that every view shows the same numbers.
 *
 * Realized PnL  = sum of closed positions' realized_pnl
 * Unrealized PnL = sum of open positions' unrealized_pnl
 * Total Trades count comes from the trades API.
 */

import { useState, useEffect, useMemo } from 'react';
import { fetchAllTrades } from '../utils/fetchAllTrades';
import { useTaskPositions, type TaskPosition } from './useTaskPositions';
import { TaskType } from '../types/common';

interface OverviewPnl {
  realizedPnl: number;
  unrealizedPnl: number;
  totalTrades: number;
}

export function useOverviewPnl(
  taskId: string,
  taskType: TaskType
): OverviewPnl {
  const [tradeCount, setTradeCount] = useState<number | null>(null);

  const { positions: closedPositions } = useTaskPositions({
    taskId,
    taskType,
    status: 'closed',
    pageSize: 1000,
  });

  const { positions: openPositions } = useTaskPositions({
    taskId,
    taskType,
    status: 'open',
    pageSize: 1000,
  });

  useEffect(() => {
    if (!taskId) return;

    let cancelled = false;
    const load = async () => {
      try {
        const allTrades = await fetchAllTrades(taskId, taskType);
        if (!cancelled) setTradeCount(allTrades.length);
      } catch {
        // leave null — will fall back to 0
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [taskId, taskType]);

  return useMemo(() => {
    const realizedPnl = closedPositions.reduce(
      (sum: number, p: TaskPosition) =>
        sum + (p.realized_pnl ? parseFloat(p.realized_pnl) : 0),
      0
    );

    const unrealizedRaw = openPositions.reduce(
      (sum: number, p: TaskPosition) =>
        sum + (p.unrealized_pnl ? parseFloat(p.unrealized_pnl) : 0),
      0
    );

    const totalTrades = tradeCount ?? 0;

    return {
      realizedPnl: Number.isFinite(realizedPnl) ? realizedPnl : 0,
      unrealizedPnl: Number.isFinite(unrealizedRaw) ? unrealizedRaw : 0,
      totalTrades,
    };
  }, [closedPositions, openPositions, tradeCount]);
}
