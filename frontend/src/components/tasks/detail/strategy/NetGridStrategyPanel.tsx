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
  TableContainer,
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
import type {
  CycleTrade,
  NetGridDecision,
  NetGridLedgerEntry,
  NetGridStrategyState,
  StrategyOhlcLayers,
} from '../../../../types/strategyVisualization';
import type { TaskType } from '../../../../types/common';
import { formatAppNumber } from '../../../../utils/numberFormat';
import { useTranslation } from 'react-i18next';
import { useTaskStrategyEvents } from '../../../../hooks/useTaskStrategyEvents';
import { StrategyGroupChart } from './StrategyGroupChart';
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
  ohlcLayers?: StrategyOhlcLayers | null;
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

const OHLC_LAYER_OVERLAY_KEYS = {
  average_entry_price: 'averageEntry',
  net_take_profit_price: 'takeProfit',
  profit_trailing_stop_price: 'trailingStop',
  last_grid_price: 'lastGrid',
  next_grid_price: 'nextGrid',
  risk_exit_price: 'riskExit',
} as const;

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
    entry.action === 'partial_derisk' ||
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

function numericStateValue(value?: string | number | null): number | null {
  if (value == null || value === '') return null;
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

function currentDisplayPrice(
  state?: NetGridStrategyState | null
): string | null {
  return state?.last_mid ?? state?.last_bid ?? state?.last_ask ?? null;
}

function trendBiasKey(state?: NetGridStrategyState | null): string {
  const trend = numericStateValue(state?.trend_score_pips) ?? 0;
  const required = Math.abs(
    numericStateValue(state?.auto_direction_required_trend_pips) ?? 0
  );
  const threshold = required > 0 ? required : 0.1;
  if (trend >= threshold) return 'up';
  if (trend <= -threshold) return 'down';
  return 'flat';
}

function trendRelationKey(
  state: NetGridStrategyState | null | undefined,
  currentNet: number
): string {
  const bias = trendBiasKey(state);
  if (currentNet === 0 || bias === 'flat') return 'neutral';
  if (
    (currentNet > 0 && bias === 'up') ||
    (currentNet < 0 && bias === 'down')
  ) {
    return 'aligned';
  }
  return 'counter';
}

function aimKey(
  state: NetGridStrategyState | null | undefined,
  currentNet: number
): string {
  if (!state || currentNet === 0) return 'noPositionAim';
  return currentNet > 0 ? 'longAim' : 'shortAim';
}

function trendMarkerPercent(
  state: NetGridStrategyState | null | undefined
): number {
  const trend = numericStateValue(state?.trend_score_pips) ?? 0;
  const required = Math.abs(
    numericStateValue(state?.auto_direction_required_trend_pips) ?? 0
  );
  const scale = Math.max(Math.abs(trend), required, 1) * 1.25;
  return Math.min(Math.max(((trend + scale) / (scale * 2)) * 100, 0), 100);
}

function levelPercent(value: number, min: number, max: number): number {
  if (max <= min) return 50;
  return Math.min(Math.max(((value - min) / (max - min)) * 100, 0), 100);
}

function scenarioDecision(
  state: NetGridStrategyState | null | undefined,
  currentNet: number,
  movePips: number
): string {
  if (!state || currentNet === 0) return 'waitTrend';
  const current = numericPrice(currentDisplayPrice(state));
  if (current == null) return 'unknown';
  const pipSize = inferPipSize(state);
  const simulated = current + movePips * pipSize;
  const nextAdd = numericPrice(state.next_grid_price);
  const takeProfit = numericPrice(state.net_take_profit_price);
  const trailing = numericPrice(state.profit_trailing_stop_price);
  const risk = numericPrice(state.risk_exit_price);
  if (currentNet > 0) {
    if (risk != null && simulated <= risk) return 'riskExit';
    if (nextAdd != null && simulated <= nextAdd) return 'add';
    if (trailing != null && simulated <= trailing) return 'trailingStop';
    if (takeProfit != null && simulated >= takeProfit) return 'takeProfit';
  } else {
    if (risk != null && simulated >= risk) return 'riskExit';
    if (nextAdd != null && simulated >= nextAdd) return 'add';
    if (trailing != null && simulated >= trailing) return 'trailingStop';
    if (takeProfit != null && simulated <= takeProfit) return 'takeProfit';
  }
  return 'hold';
}

function inferPipSize(state?: NetGridStrategyState | null): number {
  const current = numericPrice(currentDisplayPrice(state));
  const average = numericPrice(state?.average_entry_price);
  const favorable = Math.abs(
    numericStateValue(state?.current_favorable_pips) ?? 0
  );
  const adverse = Math.abs(numericStateValue(state?.current_adverse_pips) ?? 0);
  const pips = favorable > 0 ? favorable : adverse;
  if (current != null && average != null && pips > 0) {
    return Math.abs(current - average) / pips;
  }
  return 0.01;
}

export function NetGridStrategyPanel({
  state,
  instrument,
  taskId,
  taskType,
  executionRunId,
  lastTickTimestamp,
  timezone = 'UTC',
  ohlcLayers,
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
    trailingStop: true,
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
  const activeOhlcLayers = ohlcLayers;
  const priceSeries = useMemo(
    () =>
      (activeOhlcLayers?.price_series ?? []).filter((series) => {
        const key =
          OHLC_LAYER_OVERLAY_KEYS[
            series.id as keyof typeof OHLC_LAYER_OVERLAY_KEYS
          ];
        return key ? visibleOverlays[key] : true;
      }),
    [activeOhlcLayers, visibleOverlays]
  );
  const priceBandSeries = activeOhlcLayers?.price_band_series ?? [];
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
                priceSeries={priceSeries}
                priceBandSeries={priceBandSeries}
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
                  color="#00897b"
                  label={t('netGrid.chart.trailingStop')}
                  active={visibleOverlays.trailingStop}
                  onClick={() => toggleOverlay('trailingStop')}
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
                <LegendChip
                  color="rgba(211, 47, 47, 0.45)"
                  label={t('netGrid.chartBands.addZone')}
                  active
                />
                <LegendChip
                  color="rgba(46, 125, 50, 0.45)"
                  label={t('netGrid.chartBands.recoveryZone')}
                  active
                />
                <LegendChip
                  color="rgba(0, 137, 123, 0.45)"
                  label={t('netGrid.chartBands.trailingZone')}
                  active
                />
                <LegendChip
                  color="rgba(97, 97, 97, 0.45)"
                  label={t('netGrid.chartBands.riskZone')}
                  active
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

      <StrategyLogicMap
        state={state}
        currentNet={currentNet}
        quoteCurrencyCode={quoteCurrencyCode}
        latestDecision={latestDecision}
      />

      <StrategyUnderstandingPanel
        state={state}
        currentNet={currentNet}
        quoteCurrencyCode={quoteCurrencyCode}
        timezone={timezone}
      />

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
              label={t('netGrid.summary.nextGridDistance')}
              value={formatPips(state?.effective_next_grid_distance_pips)}
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
              label={t('netGrid.summary.favorableMove')}
              value={formatPips(state?.current_favorable_pips)}
            />
            <SummaryItem
              label={t('netGrid.summary.profitProtection')}
              value={
                state?.profit_protection_active
                  ? t('netGrid.profitProtection.active')
                  : t('netGrid.profitProtection.inactive')
              }
            />
            <SummaryItem
              label={t('netGrid.summary.profitPeak')}
              value={formatPips(state?.profit_peak_pips)}
            />
            <SummaryItem
              label={t('netGrid.summary.trailingStop')}
              value={formatPrice(state?.profit_trailing_stop_price)}
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
              label={t('netGrid.summary.autoTrendRequired')}
              value={formatPips(state?.auto_direction_required_trend_pips)}
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
              label={t('netGrid.summary.adverseTrend')}
              value={t(
                `netGrid.adverseTrend.${state?.adverse_trend_status ?? 'ok'}`,
                {
                  defaultValue: state?.adverse_trend_status ?? '-',
                }
              )}
            />
            <SummaryItem
              label={t('netGrid.summary.adverseTrendTicks')}
              value={formatAppNumber(state?.adverse_trend_ticks ?? 0, {
                maximumFractionDigits: 0,
              })}
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
            <RiskProgress
              label={t('netGrid.risk.projectedDrawdown')}
              value={Number(state?.projected_loss_after_next_add ?? 0)}
              max={Number(state?.drawdown_budget_quote ?? 0) || null}
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
                  label={t('netGrid.preview.nextGridDistance')}
                  value={formatPips(state?.effective_next_grid_distance_pips)}
                />
                <SummaryItem
                  label={t('netGrid.preview.takeProfitPrice')}
                  value={formatPrice(state?.net_take_profit_price)}
                />
                <SummaryItem
                  label={t('netGrid.preview.trailingStop')}
                  value={formatPrice(state?.profit_trailing_stop_price)}
                />
                <SummaryItem
                  label={t('netGrid.preview.riskExitPrice')}
                  value={formatPrice(state?.risk_exit_price)}
                />
                <SummaryItem
                  label={t('netGrid.preview.projectedDrawdown')}
                  value={formatSignedAmountWithCurrency(
                    state?.projected_loss_after_next_add,
                    quoteCurrencyCode
                  )}
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

function StrategyLogicMap({
  state,
  currentNet,
  quoteCurrencyCode,
  latestDecision,
}: {
  state?: NetGridStrategyState | null;
  currentNet: number;
  quoteCurrencyCode: string | null;
  latestDecision?: NetGridDecision | null;
}) {
  const { t } = useTranslation('strategy');
  const trendBias = trendBiasKey(state);
  const relation = trendRelationKey(state, currentNet);
  const currentPrice = currentDisplayPrice(state);
  const priceLevels = [
    {
      key: 'riskExit',
      label: t('netGrid.logic.levels.riskExit'),
      value: numericPrice(state?.risk_exit_price),
      color: '#616161',
    },
    {
      key: 'nextAdd',
      label: t('netGrid.logic.levels.nextAdd'),
      value: numericPrice(state?.next_grid_price),
      color: '#d32f2f',
    },
    {
      key: 'average',
      label: t('netGrid.logic.levels.average'),
      value: numericPrice(state?.average_entry_price),
      color: '#1976d2',
    },
    {
      key: 'current',
      label: t('netGrid.logic.levels.current'),
      value: numericPrice(currentPrice),
      color: '#111827',
    },
    {
      key: 'takeProfit',
      label: t('netGrid.logic.levels.takeProfit'),
      value: numericPrice(state?.net_take_profit_price),
      color: '#2e7d32',
    },
    {
      key: 'trailingStop',
      label: t('netGrid.logic.levels.trailingStop'),
      value: numericPrice(state?.profit_trailing_stop_price),
      color: '#00897b',
    },
  ].filter((level) => level.value != null) as Array<{
    key: string;
    label: string;
    value: number;
    color: string;
  }>;
  const levelValues = priceLevels.map((level) => level.value);
  const minPrice = levelValues.length > 0 ? Math.min(...levelValues) : 0;
  const maxPrice = levelValues.length > 0 ? Math.max(...levelValues) : 1;
  const rangePad = Math.max((maxPrice - minPrice) * 0.12, 0.0001);
  const railMin = levelValues.length > 1 ? minPrice - rangePad : minPrice - 1;
  const railMax = levelValues.length > 1 ? maxPrice + rangePad : maxPrice + 1;
  const decisionReason = latestDecision?.reason
    ? t(`netGrid.ledger.reasons.${latestDecision.reason}`, {
        defaultValue: latestDecision.reason,
      })
    : t('netGrid.logic.waitingForPrice');

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack spacing={1.5}>
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          spacing={1}
          sx={{ justifyContent: 'space-between', alignItems: 'flex-start' }}
        >
          <Box>
            <Typography variant="h6">{t('netGrid.logic.title')}</Typography>
            <Typography variant="body2" color="text.secondary">
              {t(`netGrid.logic.${aimKey(state, currentNet)}`)}
            </Typography>
          </Box>
          <Chip
            size="small"
            color={
              relation === 'aligned'
                ? 'success'
                : relation === 'counter'
                  ? 'warning'
                  : 'default'
            }
            variant="outlined"
            label={t(`netGrid.logic.trendRelation.${relation}`)}
          />
        </Stack>

        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              lg: 'minmax(0, 0.85fr) minmax(0, 1.15fr)',
            },
            gap: 1.5,
          }}
        >
          <Box
            sx={{
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              p: 1.5,
              minWidth: 0,
            }}
          >
            <Stack spacing={1.25}>
              <Stack
                direction="row"
                spacing={1}
                sx={{ alignItems: 'center', justifyContent: 'space-between' }}
              >
                <Typography variant="subtitle2">
                  {t('netGrid.logic.trendTitle')}
                </Typography>
                <Chip
                  size="small"
                  label={t(`netGrid.logic.trendBias.${trendBias}`)}
                  color={
                    trendBias === 'up'
                      ? 'success'
                      : trendBias === 'down'
                        ? 'error'
                        : 'default'
                  }
                  variant="outlined"
                />
              </Stack>
              <Box
                sx={{
                  position: 'relative',
                  height: 26,
                  borderRadius: 1,
                  overflow: 'hidden',
                  background:
                    'linear-gradient(90deg, rgba(211,47,47,0.20), rgba(117,117,117,0.14) 50%, rgba(46,125,50,0.20))',
                  border: '1px solid',
                  borderColor: 'divider',
                }}
              >
                <Box
                  sx={{
                    position: 'absolute',
                    left: `${trendMarkerPercent(state)}%`,
                    top: 3,
                    bottom: 3,
                    width: 3,
                    bgcolor: 'text.primary',
                    borderRadius: 1,
                  }}
                />
              </Box>
              <Stack
                direction="row"
                spacing={1}
                sx={{ justifyContent: 'space-between' }}
              >
                <Typography variant="caption" color="text.secondary">
                  {t('netGrid.logic.trendDown')}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {t('netGrid.logic.trendUp')}
                </Typography>
              </Stack>
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                  gap: 1,
                }}
              >
                <SummaryItem
                  label={t('netGrid.logic.trendScore')}
                  value={formatPips(state?.trend_score_pips)}
                />
                <SummaryItem
                  label={t('netGrid.logic.requiredTrend')}
                  value={formatPips(state?.auto_direction_required_trend_pips)}
                />
              </Box>
            </Stack>
          </Box>

          <Box
            sx={{
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              p: 1.5,
              minWidth: 0,
            }}
          >
            <Stack spacing={1.25}>
              <Stack
                direction="row"
                spacing={1}
                sx={{ alignItems: 'center', justifyContent: 'space-between' }}
              >
                <Typography variant="subtitle2">
                  {t('netGrid.logic.priceMapTitle')}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {appendCurrencyUnit(
                    formatPrice(currentPrice),
                    quoteCurrencyCode
                  )}
                </Typography>
              </Stack>
              <Box sx={{ position: 'relative', height: 64, px: 1 }}>
                <Box
                  sx={{
                    position: 'absolute',
                    left: 8,
                    right: 8,
                    top: 30,
                    height: 6,
                    borderRadius: 1,
                    background:
                      'linear-gradient(90deg, rgba(211,47,47,0.18), rgba(245,124,0,0.18), rgba(46,125,50,0.18))',
                  }}
                />
                {priceLevels.map((level) => (
                  <Tooltip
                    key={level.key}
                    title={`${level.label}: ${appendCurrencyUnit(
                      formatPrice(String(level.value)),
                      quoteCurrencyCode
                    )}`}
                  >
                    <Box
                      sx={{
                        position: 'absolute',
                        left: `calc(${levelPercent(level.value, railMin, railMax)}% - 5px)`,
                        top: level.key === 'current' ? 20 : 24,
                        width: level.key === 'current' ? 14 : 10,
                        height: level.key === 'current' ? 14 : 10,
                        borderRadius: '50%',
                        bgcolor: level.color,
                        border: '2px solid',
                        borderColor: 'background.paper',
                        boxShadow: 1,
                      }}
                    />
                  </Tooltip>
                ))}
              </Box>
              <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap' }}>
                {priceLevels.map((level) => (
                  <Chip
                    key={level.key}
                    size="small"
                    variant={level.key === 'current' ? 'filled' : 'outlined'}
                    label={`${level.label} ${formatPrice(String(level.value))}`}
                    sx={{ borderColor: level.color }}
                  />
                ))}
              </Stack>
            </Stack>
          </Box>
        </Box>

        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              md: 'repeat(3, minmax(0, 1fr))',
            },
            gap: 1,
          }}
        >
          <LogicStep
            label={t('netGrid.logic.addPlan')}
            value={
              state?.next_grid_price
                ? t('netGrid.logic.addPlanValue', {
                    price: formatPrice(state.next_grid_price),
                    units:
                      state.next_order_units == null
                        ? '-'
                        : formatUnits(state.next_order_units),
                    distance: formatPips(
                      state.effective_next_grid_distance_pips
                    ),
                  })
                : t('netGrid.logic.noAddPlan')
            }
          />
          <LogicStep
            label={t('netGrid.logic.exitPlan')}
            value={t('netGrid.logic.exitPlanValue', {
              tp: formatPrice(state?.net_take_profit_price),
              trail: formatPrice(state?.profit_trailing_stop_price),
            })}
          />
          <LogicStep
            label={t('netGrid.logic.guardPlan')}
            value={t('netGrid.logic.guardPlanValue', {
              risk: formatPrice(state?.risk_exit_price),
              decision: decisionReason,
            })}
          />
        </Box>
      </Stack>
    </Paper>
  );
}

function LogicStep({ label, value }: { label: string; value: string }) {
  return (
    <Box
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        p: 1.25,
        minWidth: 0,
        bgcolor: 'action.hover',
      }}
    >
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="body2" sx={{ mt: 0.5, overflowWrap: 'anywhere' }}>
        {value}
      </Typography>
    </Box>
  );
}

function StrategyUnderstandingPanel({
  state,
  currentNet,
  quoteCurrencyCode,
  timezone,
}: {
  state?: NetGridStrategyState | null;
  currentNet: number;
  quoteCurrencyCode: string | null;
  timezone: string;
}) {
  const { t } = useTranslation('strategy');
  const decisionHistory = [...(state?.decision_history ?? [])]
    .slice(-10)
    .reverse();
  const scenarioMoves = [-20, -10, 10, 20];
  const ladderRows = [
    {
      key: 'current',
      label: t('netGrid.levelLadder.current'),
      price: currentDisplayPrice(state),
      intent: t('netGrid.levelLadder.intent.current'),
    },
    {
      key: 'nextAdd',
      label: t('netGrid.levelLadder.nextAdd'),
      price: state?.next_grid_price,
      intent: t('netGrid.levelLadder.intent.nextAdd'),
    },
    {
      key: 'average',
      label: t('netGrid.levelLadder.average'),
      price: state?.average_entry_price,
      intent: t('netGrid.levelLadder.intent.average'),
    },
    {
      key: 'takeProfit',
      label: t('netGrid.levelLadder.takeProfit'),
      price: state?.net_take_profit_price,
      intent: t('netGrid.levelLadder.intent.takeProfit'),
    },
    {
      key: 'trailingStop',
      label: t('netGrid.levelLadder.trailingStop'),
      price: state?.profit_trailing_stop_price,
      intent: t('netGrid.levelLadder.intent.trailingStop'),
    },
    {
      key: 'riskExit',
      label: t('netGrid.levelLadder.riskExit'),
      price: state?.risk_exit_price,
      intent: t('netGrid.levelLadder.intent.riskExit'),
    },
  ].filter((row) => row.price);
  const currentPrice = numericPrice(currentDisplayPrice(state));
  const pipSize = inferPipSize(state);
  const blockers = [
    state?.latest_decision?.action === 'hold'
      ? t(`netGrid.blockers.${state.latest_decision.reason}`, {
          defaultValue: t('netGrid.blockers.generic', {
            reason: state.latest_decision.reason,
          }),
        })
      : null,
    state?.regime_status && state.regime_status !== 'ok'
      ? t(`netGrid.regime.${state.regime_status}`, {
          defaultValue: state.regime_status,
        })
      : null,
    state?.adverse_trend_status && state.adverse_trend_status !== 'ok'
      ? t(`netGrid.adverseTrend.${state.adverse_trend_status}`, {
          defaultValue: state.adverse_trend_status,
        })
      : null,
  ].filter(Boolean);

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack spacing={1.5}>
        <Typography variant="h6">{t('netGrid.understanding.title')}</Typography>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              lg: 'repeat(2, minmax(0, 1fr))',
            },
            gap: 1.5,
          }}
        >
          <Box
            sx={{
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              p: 1.5,
            }}
          >
            <Stack spacing={1}>
              <Typography variant="subtitle2">
                {t('netGrid.decisionTimeline.title')}
              </Typography>
              {decisionHistory.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  {t('netGrid.decisionTimeline.empty')}
                </Typography>
              ) : (
                <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap' }}>
                  {decisionHistory.map((decision, index) => (
                    <Tooltip
                      key={`${decision.timestamp ?? index}-${decision.action}-${index}`}
                      title={`${formatTimestamp(decision.timestamp, timezone)} - ${t(
                        `netGrid.ledger.reasons.${decision.reason}`,
                        { defaultValue: decision.reason }
                      )}`}
                    >
                      <Chip
                        size="small"
                        variant={index === 0 ? 'filled' : 'outlined'}
                        color={
                          decision.action === 'risk_exit'
                            ? 'error'
                            : decision.action === 'add'
                              ? 'warning'
                              : decision.action === 'take_profit' ||
                                  decision.action === 'partial_derisk'
                                ? 'success'
                                : 'default'
                        }
                        label={t(`netGrid.decisionActions.${decision.action}`, {
                          defaultValue: decision.action,
                        })}
                      />
                    </Tooltip>
                  ))}
                </Stack>
              )}
            </Stack>
          </Box>

          <Box
            sx={{
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              p: 1.5,
            }}
          >
            <Stack spacing={1}>
              <Typography variant="subtitle2">
                {t('netGrid.scenarioPreview.title')}
              </Typography>
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                  gap: 1,
                }}
              >
                {scenarioMoves.map((move) => {
                  const decision = scenarioDecision(state, currentNet, move);
                  return (
                    <SummaryItem
                      key={move}
                      label={t('netGrid.scenarioPreview.move', {
                        move: formatPips(String(move)),
                      })}
                      value={t(`netGrid.scenarioPreview.decisions.${decision}`)}
                    />
                  );
                })}
              </Box>
            </Stack>
          </Box>
        </Box>

        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              lg: 'minmax(0, 1.2fr) minmax(0, 0.8fr)',
            },
            gap: 1.5,
          }}
        >
          <Box
            sx={{
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              overflow: 'hidden',
            }}
          >
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t('netGrid.levelLadder.level')}</TableCell>
                    <TableCell align="right">
                      {t('netGrid.levelLadder.price')}
                    </TableCell>
                    <TableCell align="right">
                      {t('netGrid.levelLadder.distance')}
                    </TableCell>
                    <TableCell>
                      {t('netGrid.levelLadder.intentColumn')}
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {ladderRows.map((row) => {
                    const price = numericPrice(row.price);
                    const distance =
                      currentPrice != null && price != null && pipSize > 0
                        ? (price - currentPrice) / pipSize
                        : null;
                    return (
                      <TableRow key={row.key}>
                        <TableCell>{row.label}</TableCell>
                        <TableCell align="right">
                          {appendCurrencyUnit(
                            formatPrice(row.price),
                            quoteCurrencyCode
                          )}
                        </TableCell>
                        <TableCell align="right">
                          {distance == null
                            ? '-'
                            : formatPips(String(distance))}
                        </TableCell>
                        <TableCell>{row.intent}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>

          <Stack spacing={1.5}>
            <Box
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                p: 1.5,
              }}
            >
              <Stack spacing={1}>
                <Typography variant="subtitle2">
                  {t('netGrid.blockers.title')}
                </Typography>
                {blockers.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    {t('netGrid.blockers.none')}
                  </Typography>
                ) : (
                  <Stack spacing={0.75}>
                    {blockers.map((blocker, index) => (
                      <Alert key={`${blocker}-${index}`} severity="warning">
                        {blocker}
                      </Alert>
                    ))}
                  </Stack>
                )}
              </Stack>
            </Box>
            <TrendRelationSparkline state={state} />
          </Stack>
        </Box>
      </Stack>
    </Paper>
  );
}

function TrendRelationSparkline({
  state,
}: {
  state?: NetGridStrategyState | null;
}) {
  const { t } = useTranslation('strategy');
  const points = [...(state?.trend_relation_history ?? [])].slice(-24);
  return (
    <Box
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        p: 1.5,
      }}
    >
      <Stack spacing={1}>
        <Typography variant="subtitle2">
          {t('netGrid.trendHistory.title')}
        </Typography>
        {points.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            {t('netGrid.trendHistory.empty')}
          </Typography>
        ) : (
          <Stack direction="row" spacing={0.5} sx={{ alignItems: 'flex-end' }}>
            {points.map((point, index) => {
              const relation = point.relation ?? 'neutral';
              const trend = Math.min(
                Math.abs(numericStateValue(point.trend_score_pips) ?? 0),
                20
              );
              return (
                <Tooltip
                  key={`${point.timestamp ?? index}-${index}`}
                  title={t(`netGrid.logic.trendRelation.${relation}`, {
                    defaultValue: relation,
                  })}
                >
                  <Box
                    sx={{
                      width: 8,
                      height: Math.max(8, 8 + trend * 2),
                      borderRadius: 0.75,
                      bgcolor:
                        relation === 'aligned'
                          ? 'success.main'
                          : relation === 'counter'
                            ? 'warning.main'
                            : 'text.disabled',
                    }}
                  />
                </Tooltip>
              );
            })}
          </Stack>
        )}
      </Stack>
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
