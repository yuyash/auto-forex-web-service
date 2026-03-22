import { useCallback, useEffect, useMemo } from 'react';
import type { Time } from 'lightweight-charts';
import type {
  ReplayTrade,
  TrendPosition,
} from '../components/tasks/detail/taskTrendPanel/shared';
import { logger } from '../utils/logger';

interface ChartRefLike {
  current: {
    timeScale: () => {
      getVisibleRange: () => { from: number; to: number } | null;
      setVisibleRange: (range: { from: Time; to: Time }) => void;
    };
  } | null;
}

interface UseTaskSelectionNavigationParams {
  trades: ReplayTrade[];
  positions: TrendPosition[];
  selectedTradeId: string | null;
  selectedPosId: string | null;
  highlightedTradeIds: Set<string>;
  sortedTrades: ReplayTrade[];
  sortedLongPositions: TrendPosition[];
  sortedShortPositions: TrendPosition[];
  tradeRowsPerPage: number;
  longPosRowsPerPage: number;
  shortPosRowsPerPage: number;
  chartClickedRef: { current: boolean };
  chartRef: ChartRefLike;
  programmaticScrollRef: { current: boolean };
  setSelectedTradeId: (
    value: string | null | ((prev: string | null) => string | null)
  ) => void;
  setSelectedPosId: (value: string | null) => void;
  setHighlightedTradeIds: (value: Set<string>) => void;
  setAutoFollow: (value: boolean) => void;
  setTradePage: (value: number) => void;
  setLongPosPage: (value: number) => void;
  setShortPosPage: (value: number) => void;
  reportChartWarning: (message: string | null) => void;
}

export function useTaskSelectionNavigation({
  trades,
  positions,
  selectedTradeId,
  selectedPosId,
  sortedTrades,
  sortedLongPositions,
  sortedShortPositions,
  tradeRowsPerPage,
  longPosRowsPerPage,
  shortPosRowsPerPage,
  chartClickedRef,
  chartRef,
  programmaticScrollRef,
  setSelectedTradeId,
  setSelectedPosId,
  setHighlightedTradeIds,
  setAutoFollow,
  setTradePage,
  setLongPosPage,
  setShortPosPage,
  reportChartWarning,
}: UseTaskSelectionNavigationParams) {
  const positionById = useMemo(() => {
    const map = new Map<string, TrendPosition>();
    for (const pos of positions) {
      map.set(pos.id, pos);
    }
    return map;
  }, [positions]);

  const tradeById = useMemo(() => {
    const map = new Map<string, ReplayTrade>();
    for (const trade of trades) {
      map.set(trade.id, trade);
    }
    return map;
  }, [trades]);

  const posToTradeIds = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const pos of positions) {
      if (pos.trade_ids?.length) {
        map.set(pos.id, pos.trade_ids);
      }
    }
    return map;
  }, [positions]);

  const findPositionForTrade = useCallback(
    (trade: ReplayTrade): TrendPosition | null => {
      if (!trade.position_id) {
        return null;
      }
      return positionById.get(trade.position_id) ?? null;
    },
    [positionById]
  );

  const findTradeIdsForPosition = useCallback(
    (position: TrendPosition): string[] => posToTradeIds.get(position.id) ?? [],
    [posToTradeIds]
  );

  const navigateToPosition = useCallback(
    (position: TrendPosition) => {
      setSelectedPosId(position.id);
      if (position.direction === 'long') {
        const index = sortedLongPositions.findIndex(
          (entry) => entry.id === position.id
        );
        if (index !== -1) {
          setLongPosPage(Math.floor(index / longPosRowsPerPage));
        }
        return;
      }
      if (position.direction === 'short') {
        const index = sortedShortPositions.findIndex(
          (entry) => entry.id === position.id
        );
        if (index !== -1) {
          setShortPosPage(Math.floor(index / shortPosRowsPerPage));
        }
      }
    },
    [
      longPosRowsPerPage,
      setLongPosPage,
      setSelectedPosId,
      setShortPosPage,
      shortPosRowsPerPage,
      sortedLongPositions,
      sortedShortPositions,
    ]
  );

  useEffect(() => {
    if (!chartClickedRef.current || !selectedTradeId) {
      return;
    }
    chartClickedRef.current = false;

    const tradeIndex = sortedTrades.findIndex(
      (trade) => trade.id === selectedTradeId
    );
    if (tradeIndex !== -1) {
      setTradePage(Math.floor(tradeIndex / tradeRowsPerPage));
    }

    const highlightReset = requestAnimationFrame(() => {
      setHighlightedTradeIds(new Set());
    });

    const trade = trades.find((entry) => entry.id === selectedTradeId);
    if (!trade) {
      return () => cancelAnimationFrame(highlightReset);
    }

    const position = findPositionForTrade(trade);
    if (!position) {
      const raf = requestAnimationFrame(() => {
        setSelectedPosId(null);
      });
      return () => {
        cancelAnimationFrame(highlightReset);
        cancelAnimationFrame(raf);
      };
    }

    const relatedTradeIds = findTradeIdsForPosition(position).filter(
      (tradeId) => tradeId !== selectedTradeId
    );
    const highlightRelatedMarkers = requestAnimationFrame(() => {
      setHighlightedTradeIds(new Set(relatedTradeIds));
    });
    const raf = requestAnimationFrame(() => {
      navigateToPosition(position);
    });

    return () => {
      cancelAnimationFrame(highlightReset);
      cancelAnimationFrame(highlightRelatedMarkers);
      cancelAnimationFrame(raf);
    };
  }, [
    chartClickedRef,
    findPositionForTrade,
    findTradeIdsForPosition,
    navigateToPosition,
    selectedTradeId,
    setHighlightedTradeIds,
    setSelectedPosId,
    setTradePage,
    sortedTrades,
    tradeRowsPerPage,
    trades,
  ]);

  const selectTrade = useCallback(
    (row: ReplayTrade) => {
      if (row.id === selectedTradeId) {
        setSelectedTradeId(null);
        setSelectedPosId(null);
        setHighlightedTradeIds(new Set());
        return;
      }

      setSelectedTradeId(row.id);
      setHighlightedTradeIds(new Set());
      setAutoFollow(false);

      const position = findPositionForTrade(row);
      if (position) {
        navigateToPosition(position);
      } else {
        setSelectedPosId(null);
      }

      const timeScale = chartRef.current?.timeScale();
      const visibleRange = timeScale?.getVisibleRange();
      if (!timeScale || !visibleRange) {
        return;
      }

      const from = Number(visibleRange.from);
      const to = Number(visibleRange.to);
      const target = Number(row.timeSec);
      if (target >= from && target <= to) {
        return;
      }

      const span = to - from;
      const half = span / 2;
      programmaticScrollRef.current = true;
      try {
        timeScale.setVisibleRange({
          from: (target - half) as Time,
          to: (target + half) as Time,
        });
        reportChartWarning(null);
      } catch {
        reportChartWarning(
          'Failed to update the chart range for the selected row.'
        );
      }
    },
    [
      chartRef,
      findPositionForTrade,
      navigateToPosition,
      programmaticScrollRef,
      reportChartWarning,
      selectedTradeId,
      setAutoFollow,
      setHighlightedTradeIds,
      setSelectedPosId,
      setSelectedTradeId,
    ]
  );

  const selectPosition = useCallback(
    (position: TrendPosition) => {
      if (position.id === selectedPosId) {
        setSelectedPosId(null);
        setSelectedTradeId(null);
        setHighlightedTradeIds(new Set());
        return;
      }

      setSelectedPosId(position.id);
      setAutoFollow(false);

      const relatedTradeIds = findTradeIdsForPosition(position);
      setHighlightedTradeIds(new Set(relatedTradeIds));
      const relatedTrades = relatedTradeIds
        .map((tradeId) => tradeById.get(tradeId))
        .filter((trade): trade is ReplayTrade => trade != null)
        .sort(
          (a, b) =>
            new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        );

      if (relatedTrades.length === 0) {
        setSelectedTradeId(null);
        return;
      }

      const openTrade = relatedTrades[0];
      setSelectedTradeId(openTrade.id);
      const tradeIndex = sortedTrades.findIndex(
        (trade) => trade.id === openTrade.id
      );
      if (tradeIndex !== -1) {
        setTradePage(Math.floor(tradeIndex / tradeRowsPerPage));
      }

      const timeScale = chartRef.current?.timeScale();
      const visibleRange = timeScale?.getVisibleRange();
      if (!timeScale || !visibleRange) {
        return;
      }

      const from = Number(visibleRange.from);
      const to = Number(visibleRange.to);
      const span = to - from;
      const times = relatedTrades.map((trade) => Number(trade.timeSec));
      const minTime = Math.min(...times);
      const maxTime = Math.max(...times);
      const markerSpan = maxTime - minTime;
      const padding = Math.max(markerSpan * 0.1, span * 0.05);
      const paddedMin = minTime - padding;
      const paddedMax = maxTime + padding;
      const paddedSpan = paddedMax - paddedMin;
      const allVisible = minTime >= from && maxTime <= to;

      if (allVisible) {
        return;
      }

      programmaticScrollRef.current = true;
      try {
        if (paddedSpan <= span) {
          const centre = (minTime + maxTime) / 2;
          const half = span / 2;
          timeScale.setVisibleRange({
            from: (centre - half) as Time,
            to: (centre + half) as Time,
          });
        } else {
          timeScale.setVisibleRange({
            from: paddedMin as Time,
            to: paddedMax as Time,
          });
        }
        reportChartWarning(null);
      } catch (error) {
        logger.warn('Failed to set visible range on position select', {
          error: error instanceof Error ? error.message : String(error),
        });
        reportChartWarning(
          'Failed to update the visible chart range after selecting a position.'
        );
      }
    },
    [
      chartRef,
      findTradeIdsForPosition,
      programmaticScrollRef,
      reportChartWarning,
      selectedPosId,
      setAutoFollow,
      setHighlightedTradeIds,
      setSelectedPosId,
      setSelectedTradeId,
      setTradePage,
      sortedTrades,
      tradeById,
      tradeRowsPerPage,
    ]
  );

  return {
    selectTrade,
    selectPosition,
  };
}
