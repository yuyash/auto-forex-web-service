import { vi } from 'vitest';
import type {
  TaskTrendAlertsViewModel,
  TaskTrendCandleStateViewModel,
  TaskTrendChartSectionViewModel,
  TaskTrendPanelStateViewModel,
  TaskTrendReplayStateViewModel,
  TaskTrendTablesSectionViewModel,
  TaskTrendToolbarViewModel,
  TaskTrendViewModel,
} from '../../src/components/tasks/detail/taskTrendPanel/useTaskTrendViewModel';

export function buildTaskTrendAlertsViewModel(
  overrides: Partial<TaskTrendAlertsViewModel> = {}
): TaskTrendAlertsViewModel {
  return {
    candleErrorMessage: null,
    candleErrorSeverity: 'info',
    errorCode: null,
    usingGranularityFallback: false,
    errorMessage: null,
    warningMessage: null,
    chartWarning: null,
    t: (key: string) => key,
    ...overrides,
  };
}

export function buildTaskTrendToolbarViewModel(
  overrides: Partial<TaskTrendToolbarViewModel> = {}
): TaskTrendToolbarViewModel {
  return {
    replaySummary: {
      realizedPnl: 0,
      unrealizedPnl: 0,
      totalTrades: 0,
      openPositions: 0,
    },
    pnlCurrency: 'JPY',
    executionRunId: 'run-1',
    isRefreshing: false,
    isCandleRefreshing: false,
    pollingIntervalMs: 5000,
    granularity: 'M1',
    granularityOptions: [{ value: 'M1', label: 'M1' }],
    pollingIntervalOptions: [{ value: 5000, label: '5s' }],
    enableRealTimeUpdates: true,
    autoFollow: false,
    onPollingIntervalChange: vi.fn(),
    onGranularityChange: vi.fn(),
    onFollow: vi.fn(),
    onResetZoom: vi.fn(),
    ...overrides,
  };
}

export function buildTaskTrendChartSectionViewModel(
  overrides: Partial<TaskTrendChartSectionViewModel> = {}
): TaskTrendChartSectionViewModel {
  return {
    chartContainerRef: { current: null },
    chartHeight: 420,
    minChartHeight: 280,
    isDark: false,
    timezone: 'UTC',
    loadingOlder: false,
    loadingNewer: false,
    ...overrides,
  };
}

export function buildTaskTrendTablesSectionViewModel(
  overrides: Partial<TaskTrendTablesSectionViewModel> = {}
): TaskTrendTablesSectionViewModel {
  return {
    tradesTableProps: {
      trades: [],
      paginatedTrades: [],
      selectedTradeId: null,
      highlightedTradeIds: new Set<string>(),
      selectedRowIds: new Set<string>(),
      isAllPageSelected: false,
      isRefreshing: false,
      orderBy: 'timestamp',
      order: 'desc',
      replayColWidths: {},
      page: 0,
      rowsPerPage: 10,
      timezone: 'UTC',
      selectedRowRef: { current: null },
      onConfigureColumns: vi.fn(),
      onCopySelected: vi.fn(),
      onSelectAllOnPage: vi.fn(),
      onResetSelection: vi.fn(),
      onReload: vi.fn(),
      onSelectTrade: vi.fn(),
      onToggleRowSelection: vi.fn(),
      onTogglePageSelection: vi.fn(),
      onSort: vi.fn(),
      onPageChange: vi.fn(),
      onRowsPerPageChange: vi.fn(),
      resizeHandle: () => null,
    },
    longPositionsTableProps: {
      title: 'Long',
      count: 0,
      positions: [],
      paginatedPositions: [],
      selectedPosId: null,
      selectedIds: new Set<string>(),
      isAllPageSelected: false,
      isRefreshing: false,
      showOpenOnly: false,
      orderBy: 'entry_time',
      order: 'desc',
      colWidths: {},
      currentPrice: null,
      pipSize: null,
      isShort: false,
      page: 0,
      rowsPerPage: 10,
      timezone: 'UTC',
      selectedPosRowRef: { current: null },
      onConfigureColumns: vi.fn(),
      onCopySelected: vi.fn(),
      onSelectAllOnPage: vi.fn(),
      onResetSelection: vi.fn(),
      onReload: vi.fn(),
      onToggleOpenOnly: vi.fn(),
      onTogglePageSelection: vi.fn(),
      onSort: vi.fn(),
      onSelectPosition: vi.fn(),
      onToggleSelection: vi.fn(),
      onPageChange: vi.fn(),
      onRowsPerPageChange: vi.fn(),
      resizeHandle: () => null,
    },
    shortPositionsTableProps: {
      title: 'Short',
      count: 0,
      positions: [],
      paginatedPositions: [],
      selectedPosId: null,
      selectedIds: new Set<string>(),
      isAllPageSelected: false,
      isRefreshing: false,
      showOpenOnly: false,
      orderBy: 'entry_time',
      order: 'desc',
      colWidths: {},
      currentPrice: null,
      pipSize: null,
      isShort: true,
      page: 0,
      rowsPerPage: 10,
      timezone: 'UTC',
      selectedPosRowRef: { current: null },
      onConfigureColumns: vi.fn(),
      onCopySelected: vi.fn(),
      onSelectAllOnPage: vi.fn(),
      onResetSelection: vi.fn(),
      onReload: vi.fn(),
      onToggleOpenOnly: vi.fn(),
      onTogglePageSelection: vi.fn(),
      onSort: vi.fn(),
      onSelectPosition: vi.fn(),
      onToggleSelection: vi.fn(),
      onPageChange: vi.fn(),
      onRowsPerPageChange: vi.fn(),
      resizeHandle: () => null,
    },
    tradeDialogProps: {
      open: false,
      columns: [],
      onClose: vi.fn(),
      onSave: vi.fn(),
      onReset: vi.fn(),
    },
    longDialogProps: {
      open: false,
      columns: [],
      onClose: vi.fn(),
      onSave: vi.fn(),
      onReset: vi.fn(),
    },
    shortDialogProps: {
      open: false,
      columns: [],
      onClose: vi.fn(),
      onSave: vi.fn(),
      onReset: vi.fn(),
    },
    ...overrides,
  };
}

export function buildTaskTrendViewModel(
  overrides: Partial<TaskTrendViewModel> = {}
): TaskTrendViewModel {
  const panelState: TaskTrendPanelStateViewModel = {
    candleErrorMessage: null,
    candleErrorSeverity: 'info',
    handleSeparatorMouseDown: vi.fn(),
  };
  const candleState: TaskTrendCandleStateViewModel = {
    isInitialLoading: false,
    candles: [{}],
  };
  const replayData: TaskTrendReplayStateViewModel = {
    errorMessage: null,
    warningMessage: null,
  };

  return {
    panelState,
    candleState,
    replayData,
    alertsProps: buildTaskTrendAlertsViewModel(),
    toolbarProps: buildTaskTrendToolbarViewModel(),
    chartSectionProps: buildTaskTrendChartSectionViewModel(),
    tablesSectionProps: buildTaskTrendTablesSectionViewModel(),
    ...overrides,
  };
}
