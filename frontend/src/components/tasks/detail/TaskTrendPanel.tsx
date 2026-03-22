import React, { useRef } from 'react';
import { Alert, Box, CircularProgress } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
import { type TaskSummary } from '../../../hooks/useTaskSummary';
import { useAuth } from '../../../contexts/AuthContext';
import { TaskType } from '../../../types/common';
import { POLLING_INTERVAL_OPTIONS } from './taskTrendPanel/shared';
import { TaskTrendAlerts } from './taskTrendPanel/TaskTrendAlerts';
import { TaskTrendChartSection } from './taskTrendPanel/TaskTrendChartSection';
import { TaskTrendTablesSection } from './taskTrendPanel/TaskTrendTablesSection';
import { TaskTrendToolbar } from './taskTrendPanel/TaskTrendToolbar';
import { useTaskTrendOrchestration } from './taskTrendPanel/useTaskTrendOrchestration';

interface TaskTrendPanelProps {
  taskId: string | number;
  taskType: TaskType;
  instrument: string;
  executionRunId?: string;
  startTime?: string;
  endTime?: string;
  enableRealTimeUpdates?: boolean;
  currentTick?: { timestamp: string; price: string | null } | null;
  latestExecution?: {
    total_trades?: number;
  };
  summary?: TaskSummary;
  pipSize?: number | null;
  configId?: string;
}

export const TaskTrendPanel: React.FC<TaskTrendPanelProps> = ({
  taskId,
  taskType,
  instrument,
  executionRunId,
  startTime,
  endTime,
  enableRealTimeUpdates = false,
  currentTick,
  latestExecution,
  summary,
  pipSize,
}) => {
  const panelRootRef = useRef<HTMLDivElement | null>(null);
  const { user } = useAuth();
  const { t } = useTranslation('common');
  const muiTheme = useTheme();
  const isDark = muiTheme.palette.mode === 'dark';
  const timezone = user?.timezone || 'UTC';

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
  } = useTaskTrendOrchestration({
    taskId,
    taskType,
    instrument,
    executionRunId,
    startTime,
    endTime,
    enableRealTimeUpdates,
    currentTick,
    latestExecution,
    summary,
    pipSize,
    timezone,
    isDark,
    t,
  });
  const { chartContainerRef, fitContent } = chartState;

  if (candleState.isInitialLoading) {
    return (
      <Box
        ref={panelRootRef}
        sx={{ p: 4, display: 'flex', justifyContent: 'center' }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (panelState.candleErrorMessage && candleState.candles.length === 0) {
    return (
      <Box ref={panelRootRef} sx={{ p: 3 }}>
        <Alert severity={panelState.candleErrorSeverity}>
          {panelState.candleErrorMessage}
        </Alert>
      </Box>
    );
  }

  return (
    <Box
      ref={panelRootRef}
      sx={{ p: 2, pt: 0, pb: 2, boxSizing: 'border-box' }}
    >
      <TaskTrendAlerts
        candleErrorMessage={panelState.candleErrorMessage}
        candleErrorSeverity={panelState.candleErrorSeverity}
        errorCode={panelState.errorCode}
        usingGranularityFallback={panelState.usingGranularityFallback}
        errorMessage={replayData.errorMessage}
        warningMessage={replayData.warningMessage}
        chartWarning={panelState.chartWarning}
        t={t}
      />

      <TaskTrendToolbar
        replaySummary={replayData.replaySummary}
        pnlCurrency={derivedData.pnlCurrency}
        executionRunId={executionRunId}
        isRefreshing={replayData.isRefreshing}
        isCandleRefreshing={candleState.isRefreshing}
        pollingIntervalMs={panelState.pollingIntervalMs}
        granularity={panelState.granularity}
        granularityOptions={derivedData.granularityOptions}
        pollingIntervalOptions={POLLING_INTERVAL_OPTIONS}
        enableRealTimeUpdates={enableRealTimeUpdates}
        autoFollow={panelState.autoFollow}
        onPollingIntervalChange={panelState.setPollingIntervalMs}
        onGranularityChange={panelState.handleGranularityChange}
        onFollow={() => {
          panelState.setAutoFollow(true);
          panelState.setSelectedTradeId(null);
          tradeTable.setSelectedRowIds(new Set());
          panelState.setSelectedPosId(null);
          panelState.setHighlightedTradeIds(new Set());
          tradeTable.setPage(0);
        }}
        onResetZoom={fitContent}
      />

      <TaskTrendChartSection
        chartContainerRef={chartContainerRef}
        chartHeight={panelState.chartHeight}
        minChartHeight={panelState.minChartHeight}
        isDark={isDark}
        timezone={timezone}
        loadingOlder={candleState.loadingOlder}
        loadingNewer={candleState.loadingNewer}
      />

      <Box
        onMouseDown={panelState.handleSeparatorMouseDown}
        onTouchStart={panelState.handleSeparatorMouseDown}
        sx={{
          height: 8,
          cursor: 'row-resize',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          '&:hover': { '& > div': { backgroundColor: 'primary.main' } },
        }}
      >
        <Box
          sx={{
            width: 40,
            height: 3,
            borderRadius: 1.5,
            backgroundColor: 'divider',
            transition: 'background-color 0.15s',
          }}
        />
      </Box>

      <TaskTrendTablesSection
        tradesTableProps={{
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
          timezone,
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
          onPageChange: (_e, newPage) => tradeTable.setPage(newPage),
          onRowsPerPageChange: tableState.handleRowsPerPageChange,
          resizeHandle: tradeTable.createResizeHandle,
        }}
        longPositionsTableProps={{
          title: t('tables.trend.longPositions'),
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
          pipSize,
          isShort: false,
          page: longPositionsTable.page,
          rowsPerPage: longPositionsTable.rowsPerPage,
          timezone,
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
          onPageChange: (_e, newPage) => longPositionsTable.setPage(newPage),
          onRowsPerPageChange: tableState.handleRowsPerPageChange,
          resizeHandle: longPositionsTable.createResizeHandle,
        }}
        shortPositionsTableProps={{
          title: t('tables.trend.shortPositions'),
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
          pipSize,
          isShort: true,
          page: shortPositionsTable.page,
          rowsPerPage: shortPositionsTable.rowsPerPage,
          timezone,
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
          onPageChange: (_e, newPage) => shortPositionsTable.setPage(newPage),
          onRowsPerPageChange: tableState.handleRowsPerPageChange,
          resizeHandle: shortPositionsTable.createResizeHandle,
        }}
        tradeDialogProps={{
          open: tradeTable.configOpen,
          columns: tradeTable.columnConfig,
          onClose: tableState.closeTradeColumns,
          onSave: tradeTable.updateColumns,
          onReset: tradeTable.resetToDefaults,
        }}
        longDialogProps={{
          open: longPositionsTable.configOpen,
          columns: longPositionsTable.columnConfig,
          onClose: tableState.closeLongColumns,
          onSave: longPositionsTable.updateColumns,
          onReset: longPositionsTable.resetToDefaults,
        }}
        shortDialogProps={{
          open: shortPositionsTable.configOpen,
          columns: shortPositionsTable.columnConfig,
          onClose: tableState.closeShortColumns,
          onSave: shortPositionsTable.updateColumns,
          onReset: shortPositionsTable.resetToDefaults,
        }}
      />
    </Box>
  );
};

export default TaskTrendPanel;
