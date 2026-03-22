import { useTaskSelectionNavigation } from '../../../../hooks/useTaskSelectionNavigation';
import type { TrendPosition } from './shared';
import { useTaskTrendPositionsTable } from './useTaskTrendPositionsTable';
import { useTaskTrendTableState } from './useTaskTrendTableState';
import { useTaskTrendTradesTable } from './useTaskTrendTradesTable';

interface TaskTrendTableModelParams {
  trades: Array<Record<string, unknown>>;
  allPositions: TrendPosition[];
  longPositions: TrendPosition[];
  shortPositions: TrendPosition[];
  currentPrice: number | null;
  pipSize?: number | null;
  timezone: string;
  panelState: {
    selectedTradeId: string | null;
    selectedPosId: string | null;
    highlightedTradeIds: Set<string>;
    chartClickedRef: { current: boolean };
    setSelectedTradeId: (
      value: string | null | ((prev: string | null) => string | null)
    ) => void;
    setSelectedPosId: (value: string | null) => void;
    setHighlightedTradeIds: (value: Set<string>) => void;
    setAutoFollow: (value: boolean) => void;
    reportChartWarning: (message: string | null) => void;
  };
  chartState: {
    chartRef: { current: unknown };
    programmaticScrollRef: { current: boolean };
  };
}

export function useTaskTrendTableModel({
  trades,
  allPositions,
  longPositions,
  shortPositions,
  currentPrice,
  pipSize,
  timezone,
  panelState,
  chartState,
}: TaskTrendTableModelParams) {
  const tradeTable = useTaskTrendTradesTable(trades, timezone);
  const longPositionsTable = useTaskTrendPositionsTable({
    positions: longPositions,
    currentPrice,
    pipSize,
    storageKey: 'trend_long_positions',
    timezone,
  });
  const shortPositionsTable = useTaskTrendPositionsTable({
    positions: shortPositions,
    currentPrice,
    pipSize,
    storageKey: 'trend_short_positions',
    timezone,
  });

  const selectionNavigation = useTaskSelectionNavigation({
    trades,
    positions: allPositions,
    selectedTradeId: panelState.selectedTradeId,
    selectedPosId: panelState.selectedPosId,
    highlightedTradeIds: panelState.highlightedTradeIds,
    sortedTrades: tradeTable.sortedTrades,
    sortedLongPositions: longPositionsTable.sortedPositions,
    sortedShortPositions: shortPositionsTable.sortedPositions,
    tradeRowsPerPage: tradeTable.rowsPerPage,
    longPosRowsPerPage: longPositionsTable.rowsPerPage,
    shortPosRowsPerPage: shortPositionsTable.rowsPerPage,
    chartClickedRef: panelState.chartClickedRef,
    chartRef: chartState.chartRef,
    programmaticScrollRef: chartState.programmaticScrollRef,
    setSelectedTradeId: panelState.setSelectedTradeId,
    setSelectedPosId: panelState.setSelectedPosId,
    setHighlightedTradeIds: panelState.setHighlightedTradeIds,
    setAutoFollow: panelState.setAutoFollow,
    setTradePage: tradeTable.setPage,
    setLongPosPage: longPositionsTable.setPage,
    setShortPosPage: shortPositionsTable.setPage,
    reportChartWarning: panelState.reportChartWarning,
  });

  const tableState = useTaskTrendTableState({
    setTradePage: tradeTable.setPage,
    setLongPosPage: longPositionsTable.setPage,
    setShortPosPage: shortPositionsTable.setPage,
    setTradeRowsPerPage: tradeTable.setRowsPerPage,
    setLongPosRowsPerPage: longPositionsTable.setRowsPerPage,
    setShortPosRowsPerPage: shortPositionsTable.setRowsPerPage,
    setTradeConfigOpen: tradeTable.setConfigOpen,
    setLongPosConfigOpen: longPositionsTable.setConfigOpen,
    setShortPosConfigOpen: shortPositionsTable.setConfigOpen,
  });

  return {
    tradeTable,
    longPositionsTable,
    shortPositionsTable,
    selectionNavigation,
    tableState,
  };
}
