import type { ComponentProps, MouseEvent, TouchEvent } from 'react';
import type { TFunction } from 'i18next';
import { TaskTrendAlerts } from './TaskTrendAlerts';
import { TaskTrendChartSection } from './TaskTrendChartSection';
import { TaskTrendTablesSection } from './TaskTrendTablesSection';
import { TaskTrendToolbar } from './TaskTrendToolbar';
import type { TaskTrendOrchestrationParams } from './useTaskTrendOrchestration';
import { useTaskTrendOrchestration } from './useTaskTrendOrchestration';

export interface TaskTrendViewModelParams extends TaskTrendOrchestrationParams {
  timezone: string;
  pipSize?: number | null;
  t: TFunction<'common'>;
}

export type TaskTrendAlertsViewModel = ComponentProps<typeof TaskTrendAlerts>;
export type TaskTrendToolbarViewModel = Omit<
  ComponentProps<typeof TaskTrendToolbar>,
  'pollingIntervalOptions'
>;
export type TaskTrendChartSectionViewModel = ComponentProps<
  typeof TaskTrendChartSection
>;
export type TaskTrendTablesSectionViewModel = ComponentProps<
  typeof TaskTrendTablesSection
>;

export interface TaskTrendPanelStateViewModel {
  candleErrorMessage: string | null;
  candleErrorSeverity: 'info' | 'error';
  handleSeparatorMouseDown: (
    event: MouseEvent<HTMLElement> | TouchEvent<HTMLElement>
  ) => void;
}

export interface TaskTrendCandleStateViewModel {
  isInitialLoading: boolean;
  candles: Array<unknown>;
}

export interface TaskTrendReplayStateViewModel {
  errorMessage: string | null;
  warningMessage: string | null;
}

export interface TaskTrendViewModel {
  panelState: TaskTrendPanelStateViewModel;
  candleState: TaskTrendCandleStateViewModel;
  replayData: TaskTrendReplayStateViewModel;
  alertsProps: TaskTrendAlertsViewModel;
  toolbarProps: TaskTrendToolbarViewModel;
  chartSectionProps: TaskTrendChartSectionViewModel;
  tablesSectionProps: TaskTrendTablesSectionViewModel;
}

export function useTaskTrendViewModel(
  params: TaskTrendViewModelParams
): TaskTrendViewModel {
  const orchestration = useTaskTrendOrchestration(params);
  const {
    panelState,
    candleState,
    replayData,
    derivedData,
    tradeTable,
    longPositionsTable,
    shortPositionsTable,
    chartState,
    tableState,
    selectionNavigation,
  } = orchestration;

  return {
    panelState,
    candleState,
    replayData,
    alertsProps: {
      candleErrorMessage: panelState.candleErrorMessage,
      candleErrorSeverity: panelState.candleErrorSeverity,
      errorCode: panelState.errorCode,
      usingGranularityFallback: panelState.usingGranularityFallback,
      errorMessage: replayData.errorMessage,
      warningMessage: replayData.warningMessage,
      chartWarning: panelState.chartWarning,
      t: params.t,
    },
    toolbarProps: {
      replaySummary: replayData.replaySummary,
      pnlCurrency: derivedData.pnlCurrency,
      executionRunId: params.executionRunId,
      isRefreshing: replayData.isRefreshing,
      isCandleRefreshing: candleState.isRefreshing,
      pollingIntervalMs: panelState.pollingIntervalMs,
      granularity: panelState.granularity,
      granularityOptions: derivedData.granularityOptions,
      enableRealTimeUpdates: params.enableRealTimeUpdates ?? false,
      autoFollow: panelState.autoFollow,
      onPollingIntervalChange: panelState.setPollingIntervalMs,
      onGranularityChange: panelState.handleGranularityChange,
      onFollow: () => {
        panelState.setAutoFollow(true);
        panelState.setSelectedTradeId(null);
        tradeTable.setSelectedRowIds(new Set());
        panelState.setSelectedPosId(null);
        panelState.setHighlightedTradeIds(new Set());
        tradeTable.setPage(0);
      },
      onResetZoom: chartState.fitContent,
      onReloadCandles: () => void candleState.replaceWithCountWindow(),
    },
    chartSectionProps: {
      chartContainerRef: chartState.chartContainerRef,
      chartHeight: panelState.chartHeight,
      minChartHeight: panelState.minChartHeight,
      isDark: params.isDark,
      timezone: params.timezone,
      loadingOlder: candleState.loadingOlder,
      loadingNewer: candleState.loadingNewer,
    },
    tablesSectionProps: {
      tradesTableProps: {
        trades: tradeTable.sortedTrades,
        paginatedTrades: tradeTable.paginatedTrades,
        selectedTradeId: panelState.selectedTradeId,
        highlightedTradeIds: panelState.highlightedTradeIds,
        selectedRowIds: tradeTable.selectedRowIds,
        isAllPageSelected: tradeTable.isAllPageSelected,
        isRefreshing: replayData.isRefreshing,
        orderBy: tradeTable.orderBy,
        order: tradeTable.order,
        replayColWidths: tradeTable.colWidths,
        page: tradeTable.page,
        rowsPerPage: tradeTable.rowsPerPage,
        timezone: params.timezone,
        selectedRowRef: tradeTable.selectedRowRef,
        onConfigureColumns: tableState.openTradeColumns,
        onCopySelected: tradeTable.copySelectedRows,
        onSelectAllOnPage: tradeTable.selectAllOnPage,
        onResetSelection: tradeTable.resetSelection,
        onReload: replayData.fetchReplayData,
        onSelectTrade: selectionNavigation.selectTrade,
        onToggleRowSelection: tradeTable.toggleRowSelection,
        onTogglePageSelection: tradeTable.togglePageSelection,
        onSort: tradeTable.handleSort,
        onPageChange: (_e: unknown, newPage: number) =>
          tradeTable.setPage(newPage),
        onRowsPerPageChange: tableState.handleRowsPerPageChange,
        resizeHandle: tradeTable.createResizeHandle,
      },
      longPositionsTableProps: {
        title: params.t('tables.trend.longPositions'),
        count: derivedData.longPositions.length,
        positions: longPositionsTable.sortedPositions,
        paginatedPositions: longPositionsTable.paginatedPositions,
        selectedPosId: panelState.selectedPosId,
        selectedIds: longPositionsTable.selectedIds,
        isAllPageSelected: longPositionsTable.isAllPageSelected,
        isRefreshing: replayData.isRefreshing,
        showOpenOnly: longPositionsTable.showOpenOnly,
        orderBy: longPositionsTable.orderBy,
        order: longPositionsTable.order,
        colWidths: longPositionsTable.colWidths,
        currentPrice: derivedData.currentPrice,
        pipSize: params.pipSize,
        isShort: false,
        page: longPositionsTable.page,
        rowsPerPage: longPositionsTable.rowsPerPage,
        timezone: params.timezone,
        selectedPosRowRef: panelState.selectedPosRowRef,
        onConfigureColumns: tableState.openLongColumns,
        onCopySelected: () => longPositionsTable.copySelectedPositions(false),
        onSelectAllOnPage: longPositionsTable.selectAllOnPage,
        onResetSelection: longPositionsTable.resetSelection,
        onReload: replayData.fetchReplayData,
        onToggleOpenOnly: longPositionsTable.toggleOpenOnly,
        onTogglePageSelection: longPositionsTable.togglePageSelection,
        onSort: longPositionsTable.handleSort,
        onSelectPosition: selectionNavigation.selectPosition,
        onToggleSelection: longPositionsTable.toggleSelection,
        onPageChange: (_e: unknown, newPage: number) =>
          longPositionsTable.setPage(newPage),
        onRowsPerPageChange: tableState.handleRowsPerPageChange,
        resizeHandle: longPositionsTable.createResizeHandle,
      },
      shortPositionsTableProps: {
        title: params.t('tables.trend.shortPositions'),
        count: derivedData.shortPositions.length,
        positions: shortPositionsTable.sortedPositions,
        paginatedPositions: shortPositionsTable.paginatedPositions,
        selectedPosId: panelState.selectedPosId,
        selectedIds: shortPositionsTable.selectedIds,
        isAllPageSelected: shortPositionsTable.isAllPageSelected,
        isRefreshing: replayData.isRefreshing,
        showOpenOnly: shortPositionsTable.showOpenOnly,
        orderBy: shortPositionsTable.orderBy,
        order: shortPositionsTable.order,
        colWidths: shortPositionsTable.colWidths,
        currentPrice: derivedData.currentPrice,
        pipSize: params.pipSize,
        isShort: true,
        page: shortPositionsTable.page,
        rowsPerPage: shortPositionsTable.rowsPerPage,
        timezone: params.timezone,
        selectedPosRowRef: panelState.selectedPosRowRef,
        onConfigureColumns: tableState.openShortColumns,
        onCopySelected: () => shortPositionsTable.copySelectedPositions(true),
        onSelectAllOnPage: shortPositionsTable.selectAllOnPage,
        onResetSelection: shortPositionsTable.resetSelection,
        onReload: replayData.fetchReplayData,
        onToggleOpenOnly: shortPositionsTable.toggleOpenOnly,
        onTogglePageSelection: shortPositionsTable.togglePageSelection,
        onSort: shortPositionsTable.handleSort,
        onSelectPosition: selectionNavigation.selectPosition,
        onToggleSelection: shortPositionsTable.toggleSelection,
        onPageChange: (_e: unknown, newPage: number) =>
          shortPositionsTable.setPage(newPage),
        onRowsPerPageChange: tableState.handleRowsPerPageChange,
        resizeHandle: shortPositionsTable.createResizeHandle,
      },
      tradeDialogProps: {
        open: tradeTable.configOpen,
        columns: tradeTable.columnConfig,
        onClose: tableState.closeTradeColumns,
        onSave: tradeTable.updateColumns,
        onReset: tradeTable.resetToDefaults,
      },
      longDialogProps: {
        open: longPositionsTable.configOpen,
        columns: longPositionsTable.columnConfig,
        onClose: tableState.closeLongColumns,
        onSave: longPositionsTable.updateColumns,
        onReset: longPositionsTable.resetToDefaults,
      },
      shortDialogProps: {
        open: shortPositionsTable.configOpen,
        columns: shortPositionsTable.columnConfig,
        onClose: tableState.closeShortColumns,
        onSave: shortPositionsTable.updateColumns,
        onReset: shortPositionsTable.resetToDefaults,
      },
    },
  };
}
