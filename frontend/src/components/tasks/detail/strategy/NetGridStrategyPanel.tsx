import { useCallback, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Chip,
  Divider,
  IconButton,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import CandlestickChartIcon from '@mui/icons-material/CandlestickChart';
import RefreshIcon from '@mui/icons-material/Refresh';
import SettingsIcon from '@mui/icons-material/Settings';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import { LineStyle } from 'lightweight-charts';
import type {
  CycleTrade,
  NetGridLedgerEntry,
  NetGridStrategyState,
} from '../../../../types/strategyVisualization';
import type { TaskType } from '../../../../types/common';
import { formatAppNumber } from '../../../../utils/numberFormat';
import { useTranslation } from 'react-i18next';
import { useTaskStrategyEvents } from '../../../../hooks/useTaskStrategyEvents';
import {
  StrategyGroupChart,
  type StrategyPriceLine,
} from './StrategyGroupChart';
import { formatDateTimeInTimezone } from '../../../../utils/timezone';
import { ColumnConfigDialog } from '../../../common/ColumnConfigDialog';
import { useColumnConfig } from '../../../../hooks/useColumnConfig';

interface NetGridStrategyPanelProps {
  state?: NetGridStrategyState | null;
  instrument?: string;
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  lastTickTimestamp?: string | null;
  timezone?: string;
}

interface NetGridMetricPoint {
  timestamp: string;
  netUnits: number;
  cumulativePnl: number;
}

type LedgerColumnKey =
  | 'timestamp'
  | 'action'
  | 'unitsDelta'
  | 'orderDirection'
  | 'fill'
  | 'orderPrice'
  | 'closePrice'
  | 'netAfter'
  | 'pnl';

const DEFAULT_LEDGER_COLUMNS: LedgerColumnKey[] = [
  'timestamp',
  'action',
  'unitsDelta',
  'orderDirection',
  'fill',
  'orderPrice',
  'closePrice',
  'netAfter',
  'pnl',
];

const LEDGER_ORDERING_OPTIONS = [
  '-timestamp',
  'timestamp',
  '-action',
  'action',
  '-units_delta',
  'units_delta',
  '-filled_price',
  'filled_price',
  '-net_units_after',
  'net_units_after',
  '-realized_pnl',
  'realized_pnl',
] as const;

function formatUnits(value?: number | null): string {
  return formatAppNumber(value ?? 0, {
    maximumFractionDigits: 0,
    signed: true,
  });
}

function formatAbsoluteUnits(value?: number | null): string {
  return formatAppNumber(Math.abs(value ?? 0), {
    maximumFractionDigits: 0,
  });
}

function directionLabel(value?: number | null): string {
  const numeric = value ?? 0;
  if (numeric > 0) return 'LONG';
  if (numeric < 0) return 'SHORT';
  return 'FLAT';
}

function formatDirectionalUnits(value?: number | null): string {
  const numeric = value ?? 0;
  if (numeric === 0) return 'FLAT';
  return `${directionLabel(numeric)} ${formatAbsoluteUnits(numeric)}`;
}

function formatPrice(value?: string | null): string {
  if (!value) return '-';
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return value;
  return formatAppNumber(numeric, { maximumFractionDigits: 5 });
}

function getQuoteCurrencyCode(instrument?: string): string | null {
  if (!instrument || !instrument.includes('_')) return null;
  const [, quoteCurrency] = instrument.split('_');
  return quoteCurrency?.trim().toUpperCase() || null;
}

function appendCurrencyUnit(
  value: string,
  currencyCode: string | null
): string {
  if (value === '-' || !currencyCode) return value;
  return `${value} ${currencyCode}`;
}

function formatPriceWithCurrency(
  value?: string | null,
  currencyCode?: string | null
): string {
  return appendCurrencyUnit(formatPrice(value), currencyCode ?? null);
}

function formatSignedAmountWithCurrency(
  value?: string | null,
  currencyCode?: string | null
): string {
  if (!value) return '-';
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return appendCurrencyUnit(value, currencyCode ?? null);
  }
  return appendCurrencyUnit(
    formatAppNumber(numeric, {
      maximumFractionDigits: 2,
      signed: true,
    }),
    currencyCode ?? null
  );
}

function formatPips(value?: string | null): string {
  if (!value) return '-';
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return value;
  return formatAppNumber(numeric, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
    signed: true,
  });
}

function formatPercent(value?: string | null): string {
  if (!value) return '-';
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return value;
  return `${formatAppNumber(numeric * 100, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}%`;
}

function formatTimestamp(value?: string | null, timezone = 'UTC'): string {
  if (!value) return '-';
  return formatDateTimeInTimezone(value, timezone, undefined, {
    includeSeconds: true,
    includeTimezone: true,
  });
}

function isoToMillis(value?: string | null): number | null {
  if (!value) return null;
  const ms = new Date(value).getTime();
  return Number.isFinite(ms) ? ms : null;
}

function directionIcon(units?: number) {
  if (!units) return <SwapHorizIcon fontSize="small" />;
  return units > 0 ? (
    <TrendingUpIcon fontSize="small" />
  ) : (
    <TrendingDownIcon fontSize="small" />
  );
}

function ledgerRows(entries?: NetGridLedgerEntry[]): NetGridLedgerEntry[] {
  return [...(entries ?? [])].reverse().slice(0, 12);
}

function buildMetricPoints(
  entries: NetGridLedgerEntry[] | undefined,
  state?: NetGridStrategyState | null
): NetGridMetricPoint[] {
  const points: NetGridMetricPoint[] = [];
  let cumulativePnl = 0;
  const sorted = [...(entries ?? [])].sort((a, b) => {
    const left = isoToMillis(a.timestamp);
    const right = isoToMillis(b.timestamp);
    return (left ?? 0) - (right ?? 0);
  });

  for (const entry of sorted) {
    if (!entry.timestamp) continue;
    cumulativePnl += Number(entry.realized_pnl ?? 0) || 0;
    points.push({
      timestamp: entry.timestamp,
      netUnits: entry.net_units_after ?? 0,
      cumulativePnl,
    });
  }

  const currentTimestamp = state?.last_tick_at ?? state?.started_at ?? null;
  if (state && currentTimestamp) {
    const last = points[points.length - 1];
    if (!last || last.timestamp !== currentTimestamp) {
      points.push({
        timestamp: currentTimestamp,
        netUnits: state.current_net_units ?? 0,
        cumulativePnl: last?.cumulativePnl ?? cumulativePnl,
      });
    }
  }

  return points;
}

function isClosingLedgerEntry(entry: NetGridLedgerEntry): boolean {
  return (
    entry.action === 'take_profit' ||
    entry.action === 'risk_exit' ||
    Math.abs(entry.net_units_after ?? 0) < Math.abs(entry.net_units_before ?? 0)
  );
}

function isOpeningLedgerEntry(entry: NetGridLedgerEntry): boolean {
  return (
    Boolean(entry.filled_price) &&
    !isClosingLedgerEntry(entry) &&
    Math.abs(entry.net_units_after ?? 0) > Math.abs(entry.net_units_before ?? 0)
  );
}

function ledgerEntryId(entry: NetGridLedgerEntry): string {
  return String(
    entry.broker_transaction_id ??
      entry.broker_order_id ??
      `${entry.timestamp ?? 'ledger'}-${entry.action}-${entry.units_delta}-${entry.filled_price ?? ''}`
  );
}

function numericPrice(value?: string | null): number | null {
  if (!value) return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function ledgerToTrades(
  entries: NetGridLedgerEntry[] | undefined,
  options: { fills: boolean; sync: boolean }
): CycleTrade[] {
  return (entries ?? [])
    .filter((entry) => {
      if (!entry.timestamp) return false;
      const isSync =
        entry.action === 'broker_backfill' ||
        entry.action === 'broker_reconciliation' ||
        entry.source === 'broker_transaction_history' ||
        entry.source === 'broker_reconciliation';
      return isSync ? options.sync : options.fills;
    })
    .map((entry) => {
      const unitsDelta = entry.units_delta ?? 0;
      const isSync =
        entry.action === 'broker_backfill' ||
        entry.action === 'broker_reconciliation' ||
        entry.source === 'broker_transaction_history' ||
        entry.source === 'broker_reconciliation';
      const isClose = isClosingLedgerEntry(entry);
      return {
        id: ledgerEntryId(entry),
        direction: unitsDelta >= 0 ? 'buy' : 'sell',
        units: Math.abs(unitsDelta),
        price: entry.filled_price ?? '',
        execution_method: isSync
          ? entry.action
          : isClose
            ? 'close_position'
            : 'open_position',
        description: `${entry.action}: ${entry.reason ?? entry.source ?? ''}`,
        timestamp: entry.timestamp ?? null,
        position_id: null,
        pnl: entry.realized_pnl ?? null,
      };
    });
}

function chartStartTime(state?: NetGridStrategyState | null): string | null {
  const ledgerStart = state?.grid_ledger?.find(
    (entry) => entry.timestamp
  )?.timestamp;
  return ledgerStart ?? state?.started_at ?? state?.last_tick_at ?? null;
}

export function NetGridStrategyPanel({
  state,
  instrument,
  taskId,
  taskType,
  executionRunId,
  lastTickTimestamp,
  timezone = 'UTC',
}: NetGridStrategyPanelProps) {
  const { t } = useTranslation('strategy');
  const [selectedLedgerId, setSelectedLedgerId] = useState<string | null>(null);
  const [showExecutionChart, setShowExecutionChart] = useState(true);
  const [ledgerPage, setLedgerPage] = useState(0);
  const [ledgerRowsPerPage, setLedgerRowsPerPage] = useState(25);
  const [ledgerOrdering, setLedgerOrdering] = useState('-timestamp');
  const [ledgerColumnDialogOpen, setLedgerColumnDialogOpen] = useState(false);
  const [visibleOverlays, setVisibleOverlays] = useState({
    fills: true,
    sync: true,
    averageEntry: true,
    takeProfit: true,
    lastGrid: true,
    nextGrid: true,
    riskExit: true,
  });
  const currentNet = state?.current_net_units ?? 0;
  const latestDecision = state?.latest_decision;
  const quoteCurrencyCode = getQuoteCurrencyCode(instrument);
  const ledgerColumnLabel = useCallback(
    (key: LedgerColumnKey) => t(`netGrid.ledger.columns.${key}`),
    [t]
  );
  const ledgerColumnDefaults = useMemo(
    () =>
      DEFAULT_LEDGER_COLUMNS.map((key) => ({
        id: key,
        label: ledgerColumnLabel(key),
        visible: true,
      })),
    [ledgerColumnLabel]
  );
  const {
    columns: ledgerColumnConfig,
    visibleColumns: visibleLedgerColumnConfig,
    updateColumns: updateLedgerColumns,
    resetToDefaults: resetLedgerColumns,
  } = useColumnConfig('net_grid_ledger_table', ledgerColumnDefaults);
  const visibleLedgerColumnKeys = useMemo(
    () =>
      visibleLedgerColumnConfig.map((column) => column.id as LedgerColumnKey),
    [visibleLedgerColumnConfig]
  );
  const metricPoints = useMemo(
    () => buildMetricPoints(state?.grid_ledger, state),
    [state]
  );
  const {
    data: ledgerData,
    isLoading: ledgerLoading,
    refresh: refreshLedger,
  } = useTaskStrategyEvents({
    taskId,
    taskType,
    executionRunId,
    enableRealTimeUpdates: false,
    params: {
      ledger_page: ledgerPage + 1,
      ledger_page_size: ledgerRowsPerPage,
      ledger_ordering: ledgerOrdering,
    },
  });
  const ledgerPageData = ledgerData?.net_grid_ledger;
  const rows = ledgerPageData?.results ?? ledgerRows(state?.grid_ledger);
  const trades = useMemo(
    () =>
      ledgerToTrades(state?.grid_ledger, {
        fills: visibleOverlays.fills,
        sync: visibleOverlays.sync,
      }),
    [state?.grid_ledger, visibleOverlays.fills, visibleOverlays.sync]
  );
  const startTime = chartStartTime(state);
  const endTime = lastTickTimestamp ?? state?.last_tick_at ?? null;
  const selectedTradeIds = useMemo(
    () => (selectedLedgerId ? new Set([selectedLedgerId]) : undefined),
    [selectedLedgerId]
  );
  const syncStatus = state?.broker_reconciliation_status;
  const priceLines: StrategyPriceLine[] = [
    {
      price: numericPrice(state?.average_entry_price) ?? Number.NaN,
      title: t('netGrid.chart.averageEntry'),
      color: '#1976d2',
      lineStyle: LineStyle.Solid,
    },
    {
      price: numericPrice(state?.net_take_profit_price) ?? Number.NaN,
      title: t('netGrid.chart.takeProfit'),
      color: '#2e7d32',
      lineStyle: LineStyle.Dashed,
    },
    {
      price: numericPrice(state?.last_grid_price) ?? Number.NaN,
      title: t('netGrid.chart.lastGrid'),
      color: '#f57c00',
      lineStyle: LineStyle.Dotted,
    },
    {
      price: numericPrice(state?.next_grid_price) ?? Number.NaN,
      title: t('netGrid.chart.nextGrid'),
      color: '#d32f2f',
      lineStyle: LineStyle.Dashed,
    },
    {
      price: numericPrice(state?.risk_exit_price) ?? Number.NaN,
      title: t('netGrid.chart.riskExit'),
      color: '#616161',
      lineStyle: LineStyle.Dashed,
    },
  ].filter((line) => {
    if (line.title === t('netGrid.chart.averageEntry')) {
      return visibleOverlays.averageEntry;
    }
    if (line.title === t('netGrid.chart.takeProfit')) {
      return visibleOverlays.takeProfit;
    }
    if (line.title === t('netGrid.chart.lastGrid')) {
      return visibleOverlays.lastGrid;
    }
    if (line.title === t('netGrid.chart.nextGrid')) {
      return visibleOverlays.nextGrid;
    }
    if (line.title === t('netGrid.chart.riskExit')) {
      return visibleOverlays.riskExit;
    }
    return true;
  });
  const toggleOverlay = (key: keyof typeof visibleOverlays) => {
    setVisibleOverlays((current) => ({ ...current, [key]: !current[key] }));
  };
  const renderLedgerCell = (
    entry: NetGridLedgerEntry,
    key: LedgerColumnKey
  ) => {
    switch (key) {
      case 'timestamp':
        return (
          <Typography variant="body2">
            {formatTimestamp(entry.timestamp, timezone)}
          </Typography>
        );
      case 'action':
        return (
          <Stack spacing={0.25}>
            <Typography variant="body2">
              {t(`netGrid.ledger.actions.${entry.action}`, {
                defaultValue: entry.action,
              })}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {entry.reason
                ? t(`netGrid.ledger.reasons.${entry.reason}`, {
                    defaultValue: entry.reason,
                  })
                : entry.source
                  ? t(`netGrid.ledger.sources.${entry.source}`, {
                      defaultValue: entry.source,
                    })
                  : '-'}
            </Typography>
          </Stack>
        );
      case 'unitsDelta':
        return formatUnits(entry.units_delta);
      case 'orderDirection':
        return directionLabel(entry.units_delta);
      case 'fill':
        return formatPriceWithCurrency(entry.filled_price, quoteCurrencyCode);
      case 'orderPrice':
        return isOpeningLedgerEntry(entry)
          ? formatPriceWithCurrency(entry.filled_price, quoteCurrencyCode)
          : '-';
      case 'closePrice':
        return isClosingLedgerEntry(entry)
          ? formatPriceWithCurrency(entry.filled_price, quoteCurrencyCode)
          : '-';
      case 'netAfter':
        return formatDirectionalUnits(entry.net_units_after);
      case 'pnl':
        return isOpeningLedgerEntry(entry)
          ? '-'
          : formatSignedAmountWithCurrency(
              entry.realized_pnl,
              quoteCurrencyCode
            );
      default:
        return '-';
    }
  };
  const chartSection =
    startTime && instrument ? (
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack spacing={1.5}>
          <Stack
            direction="row"
            spacing={1}
            sx={{ alignItems: 'flex-start', justifyContent: 'space-between' }}
          >
            <Box>
              <Typography variant="h6">{t('netGrid.chart.title')}</Typography>
            </Box>
            <Tooltip
              title={
                showExecutionChart
                  ? t('netGrid.chart.hide')
                  : t('netGrid.chart.show')
              }
            >
              <IconButton
                size="small"
                onClick={() => setShowExecutionChart((value) => !value)}
                color={showExecutionChart ? 'primary' : 'default'}
                aria-label={t('netGrid.chart.toggle')}
              >
                <CandlestickChartIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Stack>
          {showExecutionChart ? (
            <>
              <StrategyGroupChart
                instrument={instrument}
                startTime={startTime}
                endTime={endTime}
                trades={trades}
                height={360}
                taskId={taskId}
                taskType={taskType}
                executionRunId={executionRunId}
                lastTickTimestamp={lastTickTimestamp}
                priceLines={priceLines}
                selectedTradeIds={selectedTradeIds}
                focusedTradeId={selectedLedgerId}
                onMarkerClick={setSelectedLedgerId}
              />
              <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
                <LegendChip
                  color="#1976d2"
                  label={t('netGrid.chart.averageEntry')}
                  active={visibleOverlays.averageEntry}
                  onClick={() => toggleOverlay('averageEntry')}
                />
                <LegendChip
                  color="#2e7d32"
                  label={t('netGrid.chart.takeProfit')}
                  active={visibleOverlays.takeProfit}
                  onClick={() => toggleOverlay('takeProfit')}
                />
                <LegendChip
                  color="#f57c00"
                  label={t('netGrid.chart.lastGrid')}
                  active={visibleOverlays.lastGrid}
                  onClick={() => toggleOverlay('lastGrid')}
                />
                <LegendChip
                  color="#d32f2f"
                  label={t('netGrid.chart.nextGrid')}
                  active={visibleOverlays.nextGrid}
                  onClick={() => toggleOverlay('nextGrid')}
                />
                <LegendChip
                  color="#616161"
                  label={t('netGrid.chart.riskExit')}
                  active={visibleOverlays.riskExit}
                  onClick={() => toggleOverlay('riskExit')}
                />
                <LegendChip
                  color="#26a69a"
                  label={t('netGrid.chart.fillMarkers')}
                  active={visibleOverlays.fills}
                  onClick={() => toggleOverlay('fills')}
                />
                <LegendChip
                  color="#7b1fa2"
                  label={t('netGrid.chart.syncMarkers')}
                  active={visibleOverlays.sync}
                  onClick={() => toggleOverlay('sync')}
                />
              </Stack>
            </>
          ) : null}
        </Stack>
      </Paper>
    ) : null;

  return (
    <Stack spacing={2}>
      {!state && <Alert severity="info">{t('netGrid.noState')}</Alert>}
      {syncStatus === 'blocked' ? (
        <Alert severity="error">{t('netGrid.alerts.syncBlocked')}</Alert>
      ) : syncStatus === 'warning' ? (
        <Alert severity="warning">{t('netGrid.alerts.syncWarning')}</Alert>
      ) : null}

      {chartSection}

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack spacing={1.5}>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            justifyContent="space-between"
            spacing={1}
          >
            <Box>
              <Typography variant="h6">{t('netGrid.summary.title')}</Typography>
            </Box>
            <Chip
              size="small"
              icon={directionIcon(currentNet)}
              label={
                currentNet > 0
                  ? t('netGrid.directions.netLong')
                  : currentNet < 0
                    ? t('netGrid.directions.netShort')
                    : t('netGrid.directions.flat')
              }
              variant="outlined"
            />
          </Stack>

          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: '1fr',
                sm: 'repeat(2, minmax(0, 1fr))',
                md: 'repeat(4, minmax(0, 1fr))',
              },
              gap: 1,
            }}
          >
            <SummaryItem
              label={t('netGrid.summary.currentNet')}
              value={formatUnits(currentNet)}
            />
            <SummaryItem
              label={t('netGrid.summary.averageEntry')}
              value={formatPrice(state?.average_entry_price)}
            />
            <SummaryItem
              label={t('netGrid.summary.step')}
              value={t('netGrid.summary.stepValue', {
                step: state?.step ?? 0,
                max: state?.max_steps ?? '-',
                usage: formatPercent(state?.step_usage),
              })}
            />
            <SummaryItem
              label={t('netGrid.summary.lastGridPrice')}
              value={formatPrice(state?.last_grid_price)}
            />
            <SummaryItem
              label={t('netGrid.summary.effectiveGridInterval')}
              value={formatPips(state?.effective_grid_interval_pips)}
            />
            <SummaryItem
              label={t('netGrid.summary.takeProfitPrice')}
              value={formatPrice(state?.net_take_profit_price)}
            />
            <SummaryItem
              label={t('netGrid.summary.effectiveTakeProfit')}
              value={formatPips(state?.effective_take_profit_pips)}
            />
            <SummaryItem
              label={t('netGrid.summary.takeProfitRemaining')}
              value={formatPips(state?.take_profit_remaining_pips)}
            />
            <SummaryItem
              label={t('netGrid.summary.nextGridPrice')}
              value={formatPrice(state?.next_grid_price)}
            />
            <SummaryItem
              label={t('netGrid.summary.currentAtr')}
              value={formatPips(state?.current_atr_pips)}
            />
            <SummaryItem
              label={t('netGrid.summary.trendScore')}
              value={formatPips(state?.trend_score_pips)}
            />
            <SummaryItem
              label={t('netGrid.summary.sizeMultiplier')}
              value={formatPercent(state?.effective_order_size_multiplier)}
            />
            <SummaryItem
              label={t('netGrid.summary.regimeStatus')}
              value={
                state?.regime_status
                  ? t(`netGrid.regime.${state.regime_status}`, {
                      defaultValue: state.regime_status,
                    })
                  : '-'
              }
            />
            <SummaryItem
              label={t('netGrid.summary.lastBackfilledTransaction')}
              value={String(
                state?.broker_last_backfilled_transaction_id ?? '-'
              )}
            />
            <SummaryItem
              label={t('netGrid.summary.brokerSyncStatus')}
              value={state?.broker_reconciliation_status ?? '-'}
            />
            <SummaryItem
              label={t('netGrid.summary.brokerSyncedAt')}
              value={state?.broker_reconciled_at ?? '-'}
            />
          </Box>

          <MetricTrendChart
            points={metricPoints}
            netLabel={t('netGrid.summary.metricNetUnits')}
            pnlLabel={t('netGrid.summary.metricCumulativePnl')}
            timeLabel={t('netGrid.summary.metricTime')}
            emptyLabel={t('netGrid.summary.metricTrendEmpty')}
          />

          <Divider />
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: '1fr',
                md: 'repeat(4, minmax(0, 1fr))',
              },
              gap: 1.5,
            }}
          >
            <RiskProgress
              label={t('netGrid.risk.netExposure')}
              value={Math.abs(currentNet)}
              max={state?.max_net_units ?? null}
              formatter={(value) =>
                formatAppNumber(value, { maximumFractionDigits: 0 })
              }
            />
            <RiskProgress
              label={t('netGrid.risk.gridSteps')}
              value={state?.step ?? 0}
              max={state?.max_steps ?? null}
              formatter={(value) =>
                formatAppNumber(value, { maximumFractionDigits: 0 })
              }
            />
            <RiskProgress
              label={t('netGrid.risk.adverseMove')}
              value={Number(state?.current_adverse_pips ?? 0)}
              max={Number(state?.max_adverse_pips ?? 0) || null}
              formatter={(value) =>
                formatAppNumber(value, {
                  minimumFractionDigits: 1,
                  maximumFractionDigits: 1,
                })
              }
            />
            <RiskProgress
              label={t('netGrid.risk.unrealizedLoss')}
              value={Math.max(0, -Number(state?.current_unrealized_pnl ?? 0))}
              max={Number(state?.max_loss ?? 0) || null}
              formatter={(value) =>
                formatAppNumber(value, {
                  minimumFractionDigits: 0,
                  maximumFractionDigits: 2,
                })
              }
            />
          </Box>

          <Box sx={{ p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
            <Stack spacing={1}>
              <Typography variant="subtitle2">
                {t('netGrid.preview.title')}
              </Typography>
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: {
                    xs: '1fr',
                    sm: 'repeat(2, minmax(0, 1fr))',
                    md: 'repeat(4, minmax(0, 1fr))',
                  },
                  gap: 1,
                }}
              >
                <SummaryItem
                  label={t('netGrid.preview.nextAddPrice')}
                  value={formatPrice(state?.next_grid_price)}
                />
                <SummaryItem
                  label={t('netGrid.preview.nextOrderUnits')}
                  value={
                    state?.next_order_units == null
                      ? '-'
                      : formatUnits(state.next_order_units)
                  }
                />
                <SummaryItem
                  label={t('netGrid.preview.takeProfitPrice')}
                  value={formatPrice(state?.net_take_profit_price)}
                />
                <SummaryItem
                  label={t('netGrid.preview.riskExitPrice')}
                  value={formatPrice(state?.risk_exit_price)}
                />
              </Box>
            </Stack>
          </Box>

          <Divider />
          <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
            <Chip
              size="small"
              label={t('netGrid.summary.backfilledFills', {
                count: state?.broker_backfilled_fill_count ?? 0,
              })}
              variant="outlined"
            />
            <Chip
              size="small"
              label={t('netGrid.summary.openTrades', {
                count: state?.broker_open_trade_count ?? 0,
              })}
              variant="outlined"
            />
            <Chip
              size="small"
              label={t('netGrid.summary.pendingOrders', {
                count: state?.broker_pending_order_count ?? 0,
              })}
              color={
                (state?.broker_pending_order_count ?? 0) > 0
                  ? 'warning'
                  : 'default'
              }
              variant="outlined"
            />
          </Stack>

          {latestDecision && (
            <Alert severity="info" variant="outlined">
              {t('netGrid.latestDecision', {
                action: t(`netGrid.decisionActions.${latestDecision.action}`, {
                  defaultValue: latestDecision.action,
                }),
                reason: t(`netGrid.ledger.reasons.${latestDecision.reason}`, {
                  defaultValue: latestDecision.reason,
                }),
                units: formatUnits(latestDecision.units_delta),
              })}
            </Alert>
          )}
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack spacing={1.5}>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 1,
              flexWrap: 'wrap',
            }}
          >
            <Typography variant="h6">{t('netGrid.ledger.title')}</Typography>
            <Stack
              direction="row"
              spacing={1}
              sx={{ alignItems: 'center', flexWrap: 'wrap' }}
            >
              <Select
                size="small"
                value={ledgerOrdering}
                onChange={(event) => {
                  setLedgerOrdering(event.target.value);
                  setLedgerPage(0);
                }}
                sx={{ minWidth: 180 }}
              >
                {LEDGER_ORDERING_OPTIONS.map((option) => (
                  <MenuItem key={option} value={option}>
                    {t(
                      `netGrid.ledger.ordering.${option.replace('-', 'desc_')}`
                    )}
                  </MenuItem>
                ))}
              </Select>
              <Tooltip title={t('chartControls.reloadRange')}>
                <span>
                  <IconButton
                    size="small"
                    onClick={() => void refreshLedger()}
                    disabled={ledgerLoading}
                    aria-label={t('chartControls.reloadRange')}
                  >
                    <RefreshIcon fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title={t('common:columnConfig.configureColumns')}>
                <IconButton
                  size="small"
                  onClick={() => setLedgerColumnDialogOpen(true)}
                  aria-label={t('common:columnConfig.configureColumns')}
                >
                  <SettingsIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Stack>
          </Box>

          {rows.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              {t('netGrid.ledger.empty')}
            </Typography>
          ) : (
            <Box sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    {visibleLedgerColumnKeys.map((key) => (
                      <TableCell
                        key={key}
                        align={
                          key === 'timestamp' || key === 'action'
                            ? 'left'
                            : 'right'
                        }
                      >
                        {ledgerColumnLabel(key)}
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((entry, index) => {
                    const id = ledgerEntryId(entry);
                    const selected = selectedLedgerId === id;
                    return (
                      <TableRow
                        key={`${id}-${index}`}
                        hover
                        selected={selected}
                        onClick={() =>
                          setSelectedLedgerId(selected ? null : id)
                        }
                        sx={{ cursor: 'pointer' }}
                      >
                        {visibleLedgerColumnKeys.map((key) => (
                          <TableCell
                            key={key}
                            align={
                              key === 'timestamp' || key === 'action'
                                ? 'left'
                                : 'right'
                            }
                          >
                            {renderLedgerCell(entry, key)}
                          </TableCell>
                        ))}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
              <TablePagination
                component="div"
                count={ledgerPageData?.count ?? rows.length}
                page={ledgerPage}
                rowsPerPage={ledgerRowsPerPage}
                onPageChange={(_, page) => setLedgerPage(page)}
                onRowsPerPageChange={(event) => {
                  setLedgerRowsPerPage(Number(event.target.value));
                  setLedgerPage(0);
                }}
                rowsPerPageOptions={[10, 25, 50, 100, 200]}
              />
            </Box>
          )}
          <ColumnConfigDialog
            open={ledgerColumnDialogOpen}
            onClose={() => setLedgerColumnDialogOpen(false)}
            columns={ledgerColumnConfig}
            onSave={updateLedgerColumns}
            onReset={resetLedgerColumns}
          />
        </Stack>
      </Paper>
    </Stack>
  );
}

function LegendChip({
  color,
  label,
  active,
  onClick,
}: {
  color: string;
  label: string;
  active: boolean;
  onClick?: () => void;
}) {
  return (
    <Chip
      size="small"
      variant={active ? 'outlined' : 'filled'}
      label={label}
      onClick={onClick}
      icon={
        <Box
          component="span"
          sx={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            bgcolor: color,
          }}
        />
      }
    />
  );
}

function RiskProgress({
  label,
  value,
  max,
  formatter,
}: {
  label: string;
  value: number;
  max?: number | null;
  formatter: (value: number) => string;
}) {
  const ratio = max && max > 0 ? Math.min(Math.max(value / max, 0), 1) : 0;
  return (
    <Box sx={{ minWidth: 0 }}>
      <Stack direction="row" justifyContent="space-between" spacing={1}>
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
        <Typography variant="caption">
          {max && max > 0
            ? `${formatter(value)} / ${formatter(max)}`
            : formatter(value)}
        </Typography>
      </Stack>
      <LinearProgress
        variant="determinate"
        value={ratio * 100}
        color={ratio >= 0.9 ? 'error' : ratio >= 0.7 ? 'warning' : 'primary'}
        sx={{ mt: 0.75, height: 6, borderRadius: 1 }}
      />
    </Box>
  );
}

function MetricTrendChart({
  points,
  netLabel,
  pnlLabel,
  timeLabel,
  emptyLabel,
}: {
  points: NetGridMetricPoint[];
  netLabel: string;
  pnlLabel: string;
  timeLabel: string;
  emptyLabel: string;
}) {
  if (points.length < 2) {
    return (
      <Box
        sx={{
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
          p: 1.5,
        }}
      >
        <Typography variant="body2" color="text.secondary">
          {emptyLabel}
        </Typography>
      </Box>
    );
  }

  const width = 720;
  const height = 220;
  const padLeft = 64;
  const padRight = 76;
  const padTop = 18;
  const padBottom = 48;
  const plotBottom = height - padBottom;
  const plotRight = width - padRight;
  const innerWidth = width - padLeft - padRight;
  const innerHeight = height - padTop - padBottom;
  const times = points.map((point) => isoToMillis(point.timestamp) ?? 0);
  const minTime = Math.min(...times);
  const maxTime = Math.max(...times);
  const netValues = points.map((point) => point.netUnits);
  const pnlValues = points.map((point) => point.cumulativePnl);
  const netExtent = extentWithPadding(netValues);
  const pnlExtent = extentWithPadding(pnlValues);
  const xFor = (time: number) =>
    padLeft + ((time - minTime) / Math.max(1, maxTime - minTime)) * innerWidth;
  const yFor = (value: number, [min, max]: [number, number]) =>
    padTop + (1 - (value - min) / Math.max(1, max - min)) * innerHeight;
  const xTicks = [minTime, minTime + (maxTime - minTime) / 2, maxTime];
  const netTicks = ticksForExtent(netExtent);
  const pnlTicks = ticksForExtent(pnlExtent);
  const pathFor = (
    selector: (point: NetGridMetricPoint) => number,
    extent: [number, number]
  ) =>
    points
      .map((point, index) => {
        const x = xFor(isoToMillis(point.timestamp) ?? minTime);
        const y = yFor(selector(point), extent);
        return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
      })
      .join(' ');

  return (
    <Box
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        p: 1.5,
      }}
    >
      <Stack
        direction="row"
        spacing={2}
        sx={{ mb: 1, flexWrap: 'wrap', alignItems: 'center' }}
      >
        <LegendChip color="#1976d2" label={netLabel} active />
        <LegendChip color="#2e7d32" label={pnlLabel} active />
      </Stack>
      <Box
        component="svg"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        sx={{
          display: 'block',
          width: '100%',
          height: { xs: 240, sm: 260 },
          color: 'text.secondary',
        }}
      >
        {netTicks.map((tick) => {
          const y = yFor(tick, netExtent);
          return (
            <g key={`grid-${tick}`}>
              <line
                x1={padLeft}
                y1={y}
                x2={plotRight}
                y2={y}
                stroke="currentColor"
                opacity="0.1"
              />
              <text
                x={padLeft - 8}
                y={y + 4}
                textAnchor="end"
                fontSize="11"
                fill="currentColor"
              >
                {formatAxisNumber(tick)}
              </text>
            </g>
          );
        })}
        {pnlTicks.map((tick) => {
          const y = yFor(tick, pnlExtent);
          return (
            <text
              key={`pnl-tick-${tick}`}
              x={plotRight + 8}
              y={y + 4}
              textAnchor="start"
              fontSize="11"
              fill="currentColor"
            >
              {formatAxisNumber(tick)}
            </text>
          );
        })}
        <line
          x1={padLeft}
          y1={plotBottom}
          x2={plotRight}
          y2={plotBottom}
          stroke="currentColor"
          opacity="0.35"
        />
        <line
          x1={padLeft}
          y1={padTop}
          x2={padLeft}
          y2={plotBottom}
          stroke="currentColor"
          opacity="0.35"
        />
        <line
          x1={plotRight}
          y1={padTop}
          x2={plotRight}
          y2={plotBottom}
          stroke="currentColor"
          opacity="0.25"
        />
        {xTicks.map((tick, index) => {
          const x = xFor(tick);
          return (
            <g key={`x-tick-${index}`}>
              <line
                x1={x}
                y1={plotBottom}
                x2={x}
                y2={plotBottom + 5}
                stroke="currentColor"
                opacity="0.35"
              />
              <text
                x={x}
                y={plotBottom + 20}
                textAnchor={
                  index === 0 ? 'start' : index === 2 ? 'end' : 'middle'
                }
                fontSize="11"
                fill="currentColor"
              >
                {formatAxisTime(tick)}
              </text>
            </g>
          );
        })}
        <text
          x={(padLeft + plotRight) / 2}
          y={height - 8}
          textAnchor="middle"
          fontSize="12"
          fill="currentColor"
        >
          {timeLabel}
        </text>
        <text
          x={14}
          y={(padTop + plotBottom) / 2}
          textAnchor="middle"
          fontSize="12"
          fill="#1976d2"
          transform={`rotate(-90 14 ${(padTop + plotBottom) / 2})`}
        >
          {netLabel}
        </text>
        <text
          x={width - 14}
          y={(padTop + plotBottom) / 2}
          textAnchor="middle"
          fontSize="12"
          fill="#2e7d32"
          transform={`rotate(90 ${width - 14} ${(padTop + plotBottom) / 2})`}
        >
          {pnlLabel}
        </text>
        <path
          d={pathFor((point) => point.netUnits, netExtent)}
          fill="none"
          stroke="#1976d2"
          strokeWidth="2.5"
        />
        <path
          d={pathFor((point) => point.cumulativePnl, pnlExtent)}
          fill="none"
          stroke="#2e7d32"
          strokeWidth="2.5"
        />
      </Box>
    </Box>
  );
}

function ticksForExtent([min, max]: [number, number]): number[] {
  return [max, min + (max - min) / 2, min];
}

function formatAxisNumber(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000)
    return `${formatAppNumber(value / 1_000_000, { maximumFractionDigits: 1 })}M`;
  if (abs >= 1_000)
    return `${formatAppNumber(value / 1_000, { maximumFractionDigits: 1 })}k`;
  return formatAppNumber(value, { maximumFractionDigits: abs < 10 ? 2 : 0 });
}

function formatAxisTime(value: number): string {
  return new Date(value).toLocaleString(undefined, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function extentWithPadding(values: number[]): [number, number] {
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 1];
  if (min === max) {
    const pad = Math.max(1, Math.abs(min) * 0.1);
    return [min - pad, max + pad];
  }
  const pad = (max - min) * 0.1;
  return [min - pad, max + pad];
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <Box
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        p: 1.25,
        minWidth: 0,
      }}
    >
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="subtitle1" sx={{ overflowWrap: 'anywhere' }}>
        {value}
      </Typography>
    </Box>
  );
}
