/**
 * Hook for computing Overview PnL from positions API.
 *
 * Both Realized and Unrealized PnL are derived exclusively from the
 * Positions API so that every view shows the same numbers.
 *
 * Realized PnL  = sum of closed positions' (exit_price - entry_price) * units (direction-aware)
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

interface UseOverviewPnlOptions {
  /** Pre-fetched closed positions — when provided, skips internal fetch */
  closedPositions?: TaskPosition[];
  /** Pre-fetched open positions — when provided, skips internal fetch */
  openPositions?: TaskPosition[];
  /** Override trade count instead of fetching all trades */
  totalTrades?: number;
}

export function useOverviewPnl(
  taskId: string,
  taskType: TaskType,
  options?: UseOverviewPnlOptions
): OverviewPnl {
  const externalClosed = options?.closedPositions;
  const externalOpen = options?.openPositions;
  const externalTradeCount = options?.totalTrades;

  const skipInternalClosed = externalClosed !== undefined;
  const skipInternalOpen = externalOpen !== undefined;

  const [tradeCount, setTradeCount] = useState<number | null>(
    externalTradeCount ?? null
  );

  // Only fetch positions internally when not provided externally.
  // When skipped, pass empty taskId so useTaskPositions bails out early.
  const { positions: internalClosed } = useTaskPositions({
    taskId: skipInternalClosed ? '' : taskId,
    taskType,
    status: 'closed',
    pageSize: 1000,
  });

  const { positions: internalOpen } = useTaskPositions({
    taskId: skipInternalOpen ? '' : taskId,
    taskType,
    status: 'open',
    pageSize: 1000,
  });

  const closedPositions = externalClosed ?? internalClosed;
  const openPositions = externalOpen ?? internalOpen;

  useEffect(() => {
    if (externalTradeCount !== undefined) return;
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
  }, [taskId, taskType, externalTradeCount]);

  // Derive the effective trade count: prefer external, then fetched, then 0
  const effectiveTradeCount = externalTradeCount ?? tradeCount ?? 0;

  return useMemo(() => {
    const realizedPnl = closedPositions.reduce(
      (sum: number, p: TaskPosition) => {
        if (!p.exit_price || !p.entry_price) return sum;
        const exit = parseFloat(p.exit_price);
        const entry = parseFloat(p.entry_price);
        const units = Math.abs(p.units ?? 0);
        const dir = String(p.direction).toLowerCase();
        const pnl =
          dir === 'long' ? (exit - entry) * units : (entry - exit) * units;
        return sum + pnl;
      },
      0
    );

    const unrealizedRaw = openPositions.reduce(
      (sum: number, p: TaskPosition) =>
        sum + (p.unrealized_pnl ? parseFloat(p.unrealized_pnl) : 0),
      0
    );

    const totalTrades = effectiveTradeCount;

    return {
      realizedPnl: Number.isFinite(realizedPnl) ? realizedPnl : 0,
      unrealizedPnl: Number.isFinite(unrealizedRaw) ? unrealizedRaw : 0,
      totalTrades,
    };
  }, [closedPositions, openPositions, effectiveTradeCount]);
}
