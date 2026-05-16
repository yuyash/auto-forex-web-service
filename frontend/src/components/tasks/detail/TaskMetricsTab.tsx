/**
 * TaskMetricsTab - Time-series metrics dashboard for backtest/trading tasks.
 *
 * Renders a grid of line charts, one per metric key, using @mui/x-charts.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentProps,
  type ReactNode,
} from 'react';
import {
  Alert,
  Box,
  CircularProgress,
  Grid,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import { LineChart } from '@mui/x-charts/LineChart';
import { BarChart } from '@mui/x-charts/BarChart';
import { ChartsReferenceLine } from '@mui/x-charts/ChartsReferenceLine';
import { useTranslation } from 'react-i18next';
import type { LossCutEvent, MetricPoint } from '../../../utils/fetchMetrics';
import { MetricsToolbar } from './MetricsToolbar';
import { MetricsOhlcChart } from './MetricsOhlcChart';
import { ChartPanel } from './ChartPanel';
import {
  MetricsChartOrderDialog,
  type MetricsChartOrderItem,
} from './MetricsChartOrderDialog';
import { useMetricsOrder } from '../../../hooks/useMetricsOrder';
import { spacingTokens } from '../../../theme/density';
import { useAppSettings } from '../../../hooks/useAppSettings';
import type { MoneyAmountLike } from '../../../types/money';
import {
  formatDateInTimezone,
  formatDateTimeInTimezone,
  type DateTimeFormatOptions,
} from '../../../utils/timezone';
import {
  formatAppNumber,
  formatAppPercent,
  formatMoneyAmount,
} from '../../../utils/numberFormat';
import { measureContainer } from '../../../utils/measureContainer';

interface TaskMetricsTabProps {
  data: MetricPoint[];
  isLoading: boolean;
  error: Error | null;
  currency?: string;
  dataSource?: string;
  resumeCursorTimestamp?: string | null;
  consistencyWarnings?: Array<Record<string, unknown>>;
  interval: number;
  since: string;
  until: string;
  onIntervalChange: (interval: number) => void;
  onSinceChange: (since: string) => void;
  onUntilChange: (until: string) => void;
  onRefresh: () => void | Promise<void>;
  /** Instrument identifier for the OHLC chart (e.g. "USD_JPY") */
  instrument?: string;
  /** ISO start time for the OHLC chart range */
  startTime?: string;
  /** ISO end time for the OHLC chart range */
  endTime?: string | null;
  /** Current tick timestamp for the sequence position line */
  currentTickTimestamp?: string | null;
  /** Current tick price for the sequence position line */
  currentTickPrice?: number | null;
  timezone?: string;
  strategyType?: string;
  /** Loss-cut events to overlay as vertical reference lines on charts. */
  lossCutEvents?: LossCutEvent[];
  /** Whether to show loss-cut markers on charts. */
  showLossCutMarkers?: boolean;
  /** Callback to toggle loss-cut marker visibility. */
  onToggleLossCutMarkers?: (next: boolean) => void;
}

type MetricFormat = 'pct' | 'int' | 'currency' | 'rate';

type ChartMetric = {
  key: string;
  color: string;
  format?: MetricFormat;
};

type MetricChartDefinition = ChartMetric & {
  series?: ChartMetric[];
  valueKey?: string;
};

type ReturnPeriod = 'day' | 'week' | 'month' | 'year';

type ReturnBarChartDefinition = {
  key: string;
  period: ReturnPeriod;
  color: string;
};

/** Metrics to chart and their display order */
const CHART_METRICS: MetricChartDefinition[] = [
  { key: 'current_balance', color: '#1976d2', format: 'currency' },
  { key: 'total_pnl', color: '#2e7d32', format: 'currency' },
  { key: 'realized_pnl', color: '#388e3c', format: 'currency' },
  { key: 'unrealized_pnl', color: '#f57c00', format: 'currency' },
  { key: 'total_return', color: '#7b1fa2', format: 'pct' },
  { key: 'margin_ratio', color: '#d32f2f', format: 'pct' },
  {
    key: 'live_tick_latency_seconds',
    color: '#00897b',
    valueKey: 'trading_tick_receive_latency_seconds',
    series: [
      { key: 'oanda_tick_publish_latency_seconds', color: '#00897b' },
      { key: 'trading_tick_receive_latency_seconds', color: '#c2185b' },
    ],
  },
  { key: 'open_positions', color: '#0288d1', format: 'int' },
  { key: 'closed_positions', color: '#455a64', format: 'int' },
  { key: 'total_trades', color: '#5d4037', format: 'int' },
  { key: 'win_rate', color: '#00796b', format: 'pct' },
  { key: 'winning_trades', color: '#2e7d32', format: 'int' },
  { key: 'losing_trades', color: '#c62828', format: 'int' },
  { key: 'ticks_processed', color: '#546e7a', format: 'int' },
  { key: 'ticks_per_second', color: '#00695c', format: 'rate' },
];

const SNOWBALL_NET_CHART_METRICS: MetricChartDefinition[] = [
  { key: 'current_balance', color: '#1976d2', format: 'currency' },
  { key: 'total_pnl', color: '#2e7d32', format: 'currency' },
  { key: 'realized_pnl', color: '#388e3c', format: 'currency' },
  { key: 'unrealized_pnl', color: '#f57c00', format: 'currency' },
  {
    key: 'live_tick_latency_seconds',
    color: '#00897b',
    valueKey: 'trading_tick_receive_latency_seconds',
    series: [
      { key: 'oanda_tick_publish_latency_seconds', color: '#00897b' },
      { key: 'trading_tick_receive_latency_seconds', color: '#c2185b' },
    ],
  },
  { key: 'snowball_net_net_units', color: '#0288d1', format: 'int' },
  { key: 'snowball_net_average_price', color: '#2563eb' },
  {
    key: 'snowball_net_price_levels',
    color: '#0f766e',
    valueKey: 'snowball_net_current_price',
    series: [
      { key: 'snowball_net_next_add_price', color: '#dc2626' },
      { key: 'snowball_net_current_price', color: '#0f766e' },
      { key: 'snowball_net_target_price', color: '#16a34a' },
    ],
  },
  {
    key: 'snowball_net_pips_from_average',
    color: '#7c3aed',
    series: [
      { key: 'snowball_net_pips_from_average', color: '#7c3aed' },
      { key: 'snowball_net_loss_cut_threshold_pips', color: '#991b1b' },
    ],
  },
  {
    key: 'snowball_net_margin_ratio_pct',
    color: '#ea580c',
    format: 'pct',
    series: [
      { key: 'snowball_net_margin_ratio_pct', color: '#ea580c', format: 'pct' },
      {
        key: 'snowball_net_margin_reduce_threshold_pct',
        color: '#f97316',
        format: 'pct',
      },
      {
        key: 'snowball_net_margin_reduce_target_pct',
        color: '#14b8a6',
        format: 'pct',
      },
      {
        key: 'snowball_net_emergency_threshold_pct',
        color: '#b91c1c',
        format: 'pct',
      },
    ],
  },
  { key: 'snowball_net_add_count', color: '#455a64', format: 'int' },
  { key: 'snowball_net_exposure_pct', color: '#ea580c', format: 'pct' },
  { key: 'total_trades', color: '#5d4037', format: 'int' },
  { key: 'ticks_processed', color: '#546e7a', format: 'int' },
  { key: 'ticks_per_second', color: '#00695c', format: 'rate' },
];

const RETURN_BAR_CHARTS: ReturnBarChartDefinition[] = [
  { key: 'daily_return', period: 'day', color: '#2e7d32' },
  { key: 'weekly_return', period: 'week', color: '#0288d1' },
  { key: 'monthly_return', period: 'month', color: '#7b1fa2' },
  { key: 'yearly_return', period: 'year', color: '#c2185b' },
];

const RETURN_PERIOD_CHART_KEY = 'period_return';
const RETURN_PERIOD_SHORT_LABEL_KEYS: Record<ReturnPeriod, string> = {
  day: 'metrics.return_period_day',
  week: 'metrics.return_period_week',
  month: 'metrics.return_period_month',
  year: 'metrics.return_period_year',
};

/** Keys whose raw value is a ratio (0–1) that must be multiplied by 100 for display */
const RATIO_KEYS = new Set(['margin_ratio']);

/** Chart keys that should display loss-cut vertical reference lines when enabled. */
const LOSS_CUT_OVERLAY_KEYS = new Set([
  'current_balance',
  'realized_pnl',
  'total_pnl',
  'snowball_net_net_units',
  'margin_ratio',
  'snowball_net_margin_ratio_pct',
]);

type MetricChartValue = {
  value: number;
  currency?: string | null;
};

function isMoneyAmountLike(value: unknown): value is MoneyAmountLike {
  return (
    value != null &&
    typeof value === 'object' &&
    'amount' in value &&
    'currency' in value
  );
}

function metricMoney(
  metrics: Record<string, unknown>,
  key: string
): MoneyAmountLike | null {
  const displayMoney = metrics[`${key}_display_money`];
  if (isMoneyAmountLike(displayMoney) && displayMoney.amount != null) {
    return displayMoney;
  }
  const money = metrics[`${key}_money`];
  if (isMoneyAmountLike(money) && money.amount != null) return money;
  return null;
}

function metricCurrency(
  metrics: Record<string, unknown>,
  key: string,
  fallback?: string
): string | undefined {
  const money = metricMoney(metrics, key);
  if (typeof money?.currency === 'string' && money.currency) {
    return money.currency;
  }
  const explicit = metrics[`${key}_currency`];
  if (typeof explicit === 'string' && explicit) return explicit;
  if (key.endsWith('_quote') && typeof metrics.quote_currency === 'string') {
    return metrics.quote_currency;
  }
  if (
    key === 'current_balance' &&
    typeof metrics.current_balance_currency === 'string'
  ) {
    return metrics.current_balance_currency;
  }
  if (typeof metrics.pnl_currency === 'string' && metrics.pnl_currency) {
    return metrics.pnl_currency;
  }
  if (
    typeof metrics.account_currency === 'string' &&
    metrics.account_currency
  ) {
    return metrics.account_currency;
  }
  return fallback;
}

function metricChartValue(
  metrics: Record<string, unknown>,
  metric: ChartMetric,
  fallbackCurrency?: string
): MetricChartValue | null {
  if (metric.format === 'currency') {
    const money = metricMoney(metrics, metric.key);
    const amount = Number(money?.amount);
    if (Number.isFinite(amount)) {
      return { value: amount, currency: money?.currency ?? fallbackCurrency };
    }
  }

  const val = metrics[metric.key];
  if (val == null || val === '') return null;
  const num = Number(val);
  if (isNaN(num)) return null;
  const scale = RATIO_KEYS.has(metric.key) ? 100 : 1;
  return {
    value: num * scale,
    currency:
      metric.format === 'currency'
        ? metricCurrency(metrics, metric.key, fallbackCurrency)
        : undefined,
  };
}

function totalReturnValue(point: MetricPoint): number | null {
  const raw = point.metrics.total_return;
  if (raw == null || raw === '') return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function chartSeries(chart: MetricChartDefinition): ChartMetric[] {
  return chart.series ?? [chart];
}

function datePartsInTimezone(
  date: Date,
  timezone: string
): { year: number; month: number; day: number } {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date);
  const values = Object.fromEntries(
    parts
      .filter((part) => part.type !== 'literal')
      .map((part) => [part.type, part.value])
  ) as Record<string, string | undefined>;
  return {
    year: Number(values.year ?? '1970'),
    month: Number(values.month ?? '1'),
    day: Number(values.day ?? '1'),
  };
}

function periodKeyAndLabel(
  date: Date,
  period: ReturnPeriod,
  timezone: string
): { key: string; label: string } {
  const { year, month, day } = datePartsInTimezone(date, timezone);
  const monthText = String(month).padStart(2, '0');
  const dayText = String(day).padStart(2, '0');
  if (period === 'day') {
    return {
      key: `${year}-${monthText}-${dayText}`,
      label: `${monthText}/${dayText}`,
    };
  }
  if (period === 'month') {
    return {
      key: `${year}-${monthText}`,
      label: `${year}-${monthText}`,
    };
  }
  if (period === 'year') {
    return { key: String(year), label: String(year) };
  }

  const localDate = new Date(Date.UTC(year, month - 1, day));
  const weekday = localDate.getUTCDay() || 7;
  localDate.setUTCDate(localDate.getUTCDate() + 4 - weekday);
  const weekYear = localDate.getUTCFullYear();
  const yearStart = new Date(Date.UTC(weekYear, 0, 1));
  const week = Math.ceil(
    ((localDate.getTime() - yearStart.getTime()) / 86_400_000 + 1) / 7
  );
  const weekText = String(week).padStart(2, '0');
  return {
    key: `${weekYear}-W${weekText}`,
    label: `${weekYear}-W${weekText}`,
  };
}

function buildPeriodReturnData(
  points: MetricPoint[],
  period: ReturnPeriod,
  timezone: string
): { labels: string[]; values: number[]; lastValue: number } | null {
  const sorted = [...points].sort((a, b) => a.t - b.t);
  const labels: string[] = [];
  const values: number[] = [];
  let current: {
    key: string;
    label: string;
    startReference: number;
    last: number;
  } | null = null;
  let previousReturn: number | null = null;

  const flushCurrent = () => {
    if (!current) return;
    labels.push(current.label);
    values.push(current.last - current.startReference);
  };

  for (const point of sorted) {
    const value = totalReturnValue(point);
    if (value == null) continue;
    const bucket = periodKeyAndLabel(
      new Date(point.t * 1000),
      period,
      timezone
    );
    if (current && current.key !== bucket.key) {
      flushCurrent();
      current = null;
    }
    if (!current) {
      current = {
        key: bucket.key,
        label: bucket.label,
        startReference: previousReturn ?? value,
        last: value,
      };
    } else {
      current.last = value;
    }
    previousReturn = value;
  }
  flushCurrent();

  if (labels.length === 0 || values.length === 0) return null;
  return {
    labels,
    values,
    lastValue: values[values.length - 1],
  };
}

/**
 * Compute a short date/time label appropriate for the data's time span
 * and the current granularity.
 */
function formatTickLabel(
  date: Date,
  rangeMs: number,
  intervalMin: number,
  timezone: string,
  dateFormat: DateTimeFormatOptions['dateFormat']
): string {
  const DAY = 86_400_000;
  if (rangeMs <= DAY) {
    return formatShortTime(date, timezone);
  }
  if (rangeMs <= 7 * DAY) {
    // Up to ~1 week: show MM/DD HH:mm
    return `${formatMonthDay(date, timezone)} ${formatShortTime(date, timezone)}`;
  }
  if (rangeMs <= 90 * DAY) {
    // Up to ~3 months: show MM/DD
    if (intervalMin < 60) {
      return `${formatMonthDay(date, timezone)} ${formatShortTime(date, timezone)}`;
    }
    return formatMonthDay(date, timezone);
  }
  // Longer: show YYYY/MM/DD
  return formatDateInTimezone(date, timezone, undefined, { dateFormat });
}

/**
 * Format tooltip date/time based on granularity.
 */
function formatTooltipDate(
  date: Date,
  timezone: string,
  dateFormat: DateTimeFormatOptions['dateFormat']
): string {
  return formatDateTimeInTimezone(date, timezone, undefined, {
    includeSeconds: true,
    includeTimezone: true,
    dateFormat,
  });
}

function formatShortTime(date: Date, timezone: string): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date);
  const values = Object.fromEntries(
    parts
      .filter((part) => part.type !== 'literal')
      .map((part) => [part.type, part.value])
  ) as Record<string, string | undefined>;
  return `${values.hour === '24' ? '00' : values.hour}:${values.minute}`;
}

function formatMonthDay(date: Date, timezone: string): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date);
  const values = Object.fromEntries(
    parts
      .filter((part) => part.type !== 'literal')
      .map((part) => [part.type, part.value])
  ) as Record<string, string | undefined>;
  return `${values.month}/${values.day}`;
}

/**
 * Compute the pixel width needed for each metric chart's Y-axis tick labels.
 * Axis labels are intentionally compact because these cards prioritize the
 * plot area over high-precision tick text.
 *
 * MUI X Charts internally reserves `yAxis.width` for the axis region and
 * uses `axisWidth - tickSize(6) - TICK_LABEL_GAP(2)` as the maximum label
 * width.  Labels exceeding that limit are ellipsized.  We therefore need
 * `yAxis.width = maxLabelPx + 8` and `margin.right = yAxis.width`.
 *
 * We estimate text width at fontSize 10 using a conservative proportional
 * sans-serif digit width.
 */
const CHAR_WIDTH_PX = 6;
const Y_AXIS_OVERHEAD = 8; // tickSize(6) + TICK_LABEL_GAP(2)
const MIN_Y_AXIS_WIDTH = 34;

/**
 * Format a Y-axis tick value exactly as the chart's valueFormatter does.
 * This must stay in sync with the valueFormatter passed to yAxis below.
 *
 * Avoid fixed two-decimal labels; they consume too much horizontal space in
 * small chart cards and do not add useful precision for trend reading.
 */
function formatYLabel(v: number, format?: MetricFormat): string {
  if (format === 'pct') return formatAppPercent(v, 1);
  if (format === 'currency')
    return formatAppNumber(v, { maximumFractionDigits: 0 });
  if (format === 'int')
    return formatAppNumber(Math.round(v), { maximumFractionDigits: 0 });
  if (format === 'rate')
    return `${formatAppNumber(v, {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })}/s`;
  return formatAppNumber(v, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

/** Compute a suitable Y-axis tick count based on the value range. */
function computeYTickCount(yValues: number[]): number {
  if (yValues.length < 2) return 4;
  let min = yValues[0];
  let max = yValues[0];
  for (let i = 1; i < yValues.length; i += 1) {
    const value = yValues[i];
    if (value < min) min = value;
    if (value > max) max = value;
  }
  const range = max - min;
  if (range === 0) return 2;
  // Aim for 4-5 ticks for most charts
  return 5;
}

/** Compute a suitable X-axis tick count based on data point count and range. */
function computeXTickCount(dataLen: number): number {
  if (dataLen <= 10) return dataLen;
  if (dataLen <= 50) return 8;
  return 10;
}

/** Fixed height for all chart cards to ensure consistent grid layout */
const CHART_CARD_HEIGHT = 360;
const LINE_CHART_FALLBACK_HEIGHT = CHART_CARD_HEIGHT - 52;
const OHLC_KEY = '__ohlc__';
const MIN_CHART_MEASURE_PX = 1;
const LINE_CHART_LEFT_MARGIN = 8;
const LINE_CHART_RIGHT_MARGIN = 8;
const LINE_CHART_TOP_MARGIN = 4;
const LINE_CHART_BOTTOM_MARGIN = 22;

function FillLineChart({
  fallbackHeight,
  children,
  ...chartProps
}: ComponentProps<typeof LineChart> & {
  fallbackHeight: number;
  children?: ReactNode;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;

    const updateSize = () => {
      const measured = measureContainer(host);
      const nextWidth = Math.max(MIN_CHART_MEASURE_PX, measured.width);
      const nextHeight = Math.max(
        MIN_CHART_MEASURE_PX,
        measured.height > MIN_CHART_MEASURE_PX
          ? measured.height
          : fallbackHeight
      );
      setSize((current) =>
        current.width === nextWidth && current.height === nextHeight
          ? current
          : { width: nextWidth, height: nextHeight }
      );
    };

    // Safari may not have resolved flex layout yet at mount time.
    // A rAF delay gives WebKit a chance to finish layout before we
    // measure. In test environments (jsdom) where rAF fires
    // synchronously and all sizes are 0, the fallbackHeight path
    // ensures the chart still renders.
    const rafId = requestAnimationFrame(() => {
      updateSize();
    });

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', updateSize);
      return () => {
        cancelAnimationFrame(rafId);
        window.removeEventListener('resize', updateSize);
      };
    }

    const observer = new ResizeObserver(updateSize);
    observer.observe(host);
    return () => {
      cancelAnimationFrame(rafId);
      observer.disconnect();
    };
  }, [fallbackHeight]);

  // In test environments (jsdom) the container has no layout, so
  // width/height stay at 0. Use fallbackHeight and a reasonable
  // default width so the chart still renders.
  const effectiveWidth = size.width > 0 ? size.width : undefined;
  const effectiveHeight =
    size.height > MIN_CHART_MEASURE_PX ? size.height : fallbackHeight;

  return (
    <Box
      ref={hostRef}
      sx={{
        width: '100%',
        height: '100%',
        position: 'absolute',
        inset: 0,
        minWidth: 0,
        minHeight: 0,
        '& > *': {
          width: '100% !important',
          height: '100% !important',
        },
        '& > [class*="MuiChartsWrapper-root"]': {
          width: '100% !important',
          height: '100% !important',
        },
        '& svg.MuiChartsSurface-root': {
          width: '100% !important',
          height: '100% !important',
        },
      }}
    >
      <LineChart
        {...chartProps}
        {...(effectiveWidth != null ? { width: effectiveWidth } : {})}
        height={effectiveHeight}
      >
        {children}
      </LineChart>
    </Box>
  );
}

function FillBarChart({
  fallbackHeight,
  ...chartProps
}: ComponentProps<typeof BarChart> & {
  fallbackHeight: number;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;

    const updateSize = () => {
      const measured = measureContainer(host);
      const nextWidth = Math.max(MIN_CHART_MEASURE_PX, measured.width);
      const nextHeight = Math.max(
        MIN_CHART_MEASURE_PX,
        measured.height > MIN_CHART_MEASURE_PX
          ? measured.height
          : fallbackHeight
      );
      setSize((current) =>
        current.width === nextWidth && current.height === nextHeight
          ? current
          : { width: nextWidth, height: nextHeight }
      );
    };

    const rafId = requestAnimationFrame(() => {
      updateSize();
    });

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', updateSize);
      return () => {
        cancelAnimationFrame(rafId);
        window.removeEventListener('resize', updateSize);
      };
    }

    const observer = new ResizeObserver(updateSize);
    observer.observe(host);
    return () => {
      cancelAnimationFrame(rafId);
      observer.disconnect();
    };
  }, [fallbackHeight]);

  const effectiveWidth = size.width > 0 ? size.width : undefined;
  const effectiveHeight =
    size.height > MIN_CHART_MEASURE_PX ? size.height : fallbackHeight;

  return (
    <Box
      ref={hostRef}
      sx={{
        width: '100%',
        height: '100%',
        position: 'absolute',
        inset: 0,
        minWidth: 0,
        minHeight: 0,
        '& > *': {
          width: '100% !important',
          height: '100% !important',
        },
        '& > [class*="MuiChartsWrapper-root"]': {
          width: '100% !important',
          height: '100% !important',
        },
        '& svg.MuiChartsSurface-root': {
          width: '100% !important',
          height: '100% !important',
        },
      }}
    >
      <BarChart
        {...chartProps}
        {...(effectiveWidth != null ? { width: effectiveWidth } : {})}
        height={effectiveHeight}
      />
    </Box>
  );
}

export function TaskMetricsTab({
  data,
  isLoading,
  error,
  currency,
  consistencyWarnings = [],
  interval,
  since,
  until,
  onIntervalChange,
  onSinceChange,
  onUntilChange,
  onRefresh,
  instrument,
  startTime,
  endTime,
  currentTickTimestamp,
  currentTickPrice,
  timezone = 'UTC',
  strategyType,
  lossCutEvents,
  showLossCutMarkers,
  onToggleLossCutMarkers,
}: TaskMetricsTabProps) {
  const { t } = useTranslation('common');
  const { settings } = useAppSettings();
  const [ohlcRefreshToken, setOhlcRefreshToken] = useState(0);
  const [orderDialogOpen, setOrderDialogOpen] = useState(false);
  const [selectedReturnPeriod, setSelectedReturnPeriod] =
    useState<ReturnPeriod>('day');

  const hasOhlc = !!(instrument && startTime);
  const chartMetricDefinitions =
    strategyType === 'snowball_net'
      ? SNOWBALL_NET_CHART_METRICS
      : CHART_METRICS;
  const returnChartDataMap = useMemo(() => {
    const map: Record<
      string,
      { labels: string[]; values: number[]; lastValue: number }
    > = {};
    for (const chart of RETURN_BAR_CHARTS) {
      const chartData = buildPeriodReturnData(data, chart.period, timezone);
      if (chartData && chartData.labels.length > 0) {
        map[chart.key] = chartData;
      }
    }
    return map;
  }, [data, timezone]);
  const availableReturnCharts = useMemo(
    () =>
      RETURN_BAR_CHARTS.filter((chart) => {
        const chartData = returnChartDataMap[chart.key];
        return chartData && chartData.labels.length > 0;
      }),
    [returnChartDataMap]
  );

  const effectiveReturnPeriod =
    availableReturnCharts.find((chart) => chart.period === selectedReturnPeriod)
      ?.period ??
    availableReturnCharts[0]?.period ??
    selectedReturnPeriod;

  const handleRefresh = useCallback(async () => {
    setOhlcRefreshToken((value) => value + 1);
    await onRefresh();
  }, [onRefresh]);

  // Determine which charts actually have primary metric data.
  const availableCharts = useMemo(() => {
    if (data.length === 0) return [];
    const keysWithData = new Set<string>();
    for (const point of data) {
      for (const chart of chartMetricDefinitions) {
        for (const metric of chartSeries(chart)) {
          if (metricChartValue(point.metrics, metric, currency) != null) {
            keysWithData.add(metric.key);
          }
        }
      }
    }
    return chartMetricDefinitions.filter((chart) =>
      chartSeries(chart).some((series) => keysWithData.has(series.key))
    );
  }, [chartMetricDefinitions, currency, data]);

  // Build the list of all chart keys (OHLC first, then metrics) for ordering
  const allChartKeys = useMemo(() => {
    const keys: string[] = [];
    if (hasOhlc) keys.push(OHLC_KEY);
    if (availableReturnCharts.length > 0) keys.push(RETURN_PERIOD_CHART_KEY);
    for (const chart of availableCharts) keys.push(chart.key);
    return keys;
  }, [availableCharts, availableReturnCharts, hasOhlc]);

  const { orderedKeys, moveItem, setOrder, resetOrder } =
    useMetricsOrder(allChartKeys);

  // Map chart key → chart config for quick lookup
  const chartDefinitionMap = useMemo(() => {
    const map = new Map<string, MetricChartDefinition>();
    for (const chart of chartMetricDefinitions) map.set(chart.key, chart);
    return map;
  }, [chartMetricDefinitions]);
  // Compute effective interval from data range (for formatting)
  const effectiveInterval = useMemo(() => {
    if (interval > 0) return interval;
    if (data.length >= 2) {
      const rangeS = data[data.length - 1].t - data[0].t;
      const DAY = 86_400;
      if (rangeS <= 14 * DAY) return 1;
      if (rangeS <= 31 * DAY) return 5;
      if (rangeS <= 93 * DAY) return 15;
      if (rangeS <= 183 * DAY) return 60;
      if (rangeS <= 366 * DAY) return 240;
      return 1440;
    }
    return 1;
  }, [interval, data]);

  // Build chart data per chart. A SnowballNet chart can contain related
  // metrics, e.g. current price overlaid on target or next-add price.
  const chartDataMap = useMemo(() => {
    const map: Record<
      string,
      {
        x: Date[];
        series: {
          metric: ChartMetric;
          y: Array<number | null>;
          currency?: string | null;
        }[];
        yValues: number[];
        lastValue: number;
        lastCurrency?: string | null;
      }
    > = {};
    for (const chart of availableCharts) {
      const seriesMetrics = chartSeries(chart);
      const x: Date[] = [];
      const yBySeries = seriesMetrics.map(() => [] as Array<number | null>);
      const hasValueBySeries = seriesMetrics.map(() => false);
      const currencyBySeries = seriesMetrics.map(
        () => undefined as string | null | undefined
      );
      const yValues: number[] = [];
      const valueKey = chart.valueKey ?? chart.key;
      let lastValue: number | null = null;
      let lastCurrency: string | null | undefined;
      let fallbackLastValue: number | null = null;
      let fallbackLastCurrency: string | null | undefined;
      for (const point of data) {
        const values = seriesMetrics.map((metric) =>
          metricChartValue(point.metrics, metric, currency)
        );
        if (values.some((value) => value != null)) {
          x.push(new Date(point.t * 1000));
          values.forEach((value, index) => {
            yBySeries[index].push(value?.value ?? null);
            if (value != null) {
              hasValueBySeries[index] = true;
              if (value.currency && currencyBySeries[index] == null) {
                currencyBySeries[index] = value.currency;
              }
              yValues.push(value.value);
              fallbackLastValue = value.value;
              fallbackLastCurrency = value.currency;
              if (seriesMetrics[index].key === valueKey) {
                lastValue = value.value;
                lastCurrency = value.currency;
              }
            }
          });
        }
      }
      const series = seriesMetrics
        .map((metric, index) => ({
          metric,
          y: yBySeries[index],
          currency: currencyBySeries[index],
        }))
        .filter((_, index) => hasValueBySeries[index]);
      const finalLastValue = lastValue ?? fallbackLastValue;
      if (x.length > 0 && series.length > 0 && finalLastValue != null) {
        map[chart.key] = {
          x,
          series,
          yValues,
          lastValue: finalLastValue,
          lastCurrency: lastCurrency ?? fallbackLastCurrency,
        };
      }
    }
    return map;
  }, [data, availableCharts, currency]);

  // Compute per-chart Y-axis width so each chart uses only the space
  // its own labels need, avoiding wasted horizontal space.
  // A 20% padding is added to account for MUI's "nice" tick rounding that
  // may produce values slightly outside the data range.
  const yAxisWidthMap = useMemo(() => {
    const map: Record<string, number> = {};
    for (const chart of availableCharts) {
      const cd = chartDataMap[chart.key];
      if (!cd || cd.yValues.length === 0) continue;
      let maxChars = 0;
      let yMin = cd.yValues[0];
      let yMax = cd.yValues[0];
      for (let i = 1; i < cd.yValues.length; i += 1) {
        const value = cd.yValues[i];
        if (value < yMin) yMin = value;
        if (value > yMax) yMax = value;
      }
      for (const v of [yMin, yMax, yMin * 1.2, yMax * 1.2]) {
        const label = formatYLabel(v, chart.format);
        if (label.length > maxChars) maxChars = label.length;
      }
      const labelPx = maxChars * CHAR_WIDTH_PX;
      map[chart.key] = Math.max(
        MIN_Y_AXIS_WIDTH,
        Math.ceil(labelPx) + Y_AXIS_OVERHEAD
      );
    }
    return map;
  }, [availableCharts, chartDataMap]);

  // --- Drag-and-drop reorder state ---
  const dragKeyRef = useRef<string | null>(null);
  const lastDragTargetRef = useRef<string | null>(null);
  const [dragKey, setDragKey] = useState<string | null>(null);
  const [dragOverKey, setDragOverKey] = useState<string | null>(null);

  const handleDragStart = useCallback((e: React.DragEvent, key: string) => {
    dragKeyRef.current = key;
    lastDragTargetRef.current = null;
    setDragKey(key);
    setDragOverKey(null);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', key);
  }, []);

  const handleDragOver = useCallback(
    (e: React.DragEvent, targetKey: string) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      setDragOverKey(targetKey);

      const sourceKey = dragKeyRef.current;
      if (
        sourceKey &&
        sourceKey !== targetKey &&
        lastDragTargetRef.current !== targetKey
      ) {
        moveItem(sourceKey, targetKey);
        lastDragTargetRef.current = targetKey;
      }
    },
    [moveItem]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent, targetKey: string) => {
      e.preventDefault();
      const sourceKey = dragKeyRef.current;
      if (sourceKey && sourceKey !== targetKey) {
        moveItem(sourceKey, targetKey);
      }
      dragKeyRef.current = null;
      lastDragTargetRef.current = null;
      setDragKey(null);
      setDragOverKey(null);
    },
    [moveItem]
  );

  const handleDragEnd = useCallback(() => {
    dragKeyRef.current = null;
    lastDragTargetRef.current = null;
    setDragKey(null);
    setDragOverKey(null);
  }, []);

  const chartOrderItems = useMemo<MetricsChartOrderItem[]>(() => {
    const items: MetricsChartOrderItem[] = [];
    for (const key of orderedKeys) {
      if (key === OHLC_KEY) {
        items.push({
          key,
          label: instrument ?? t('metrics.ohlcChart', 'OHLC chart'),
          color: '#26a69a',
        });
        continue;
      }
      if (key === RETURN_PERIOD_CHART_KEY) {
        items.push({
          key,
          label: t('metrics.period_return', {
            defaultValue: 'Period Return',
          }),
          color: '#2e7d32',
        });
        continue;
      }
      const chart = chartDefinitionMap.get(key);
      if (!chart) continue;
      items.push({
        key,
        label: t(`metrics.${chart.key}`, {
          defaultValue: chart.key.replace(/_/g, ' '),
        }),
        color: chart.color,
      });
    }
    return items;
  }, [chartDefinitionMap, instrument, orderedKeys, t]);

  if (isLoading && data.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="error">{String(error)}</Alert>
      </Box>
    );
  }

  if (data.length === 0) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="text.secondary">{t('metrics.noData')}</Typography>
      </Box>
    );
  }

  const formatValue = (
    val: number,
    format?: MetricFormat,
    valueCurrency?: string | null
  ) => {
    if (format === 'pct') return formatAppPercent(val, 1);
    if (format === 'int')
      return formatAppNumber(Math.round(val), { maximumFractionDigits: 0 });
    if (format === 'rate')
      return `${formatAppNumber(val, {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })}/s`;
    if (format === 'currency')
      return formatMoneyAmount(val, valueCurrency ?? currency, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      });
    return formatAppNumber(val, {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    });
  };

  return (
    <Box
      data-testid="task-metrics-tab"
      sx={{
        px: { xs: 0, sm: 1 },
        py: { xs: 0.5, sm: 1 },
        minWidth: 0,
        width: '100%',
        maxWidth: '100%',
      }}
    >
      <MetricsToolbar
        interval={interval}
        since={since}
        until={until}
        onIntervalChange={onIntervalChange}
        onSinceChange={onSinceChange}
        onUntilChange={onUntilChange}
        onRefresh={handleRefresh}
        onConfigureCharts={() => setOrderDialogOpen(true)}
        isLoading={isLoading}
        showLossCutMarkers={showLossCutMarkers}
        onToggleLossCutMarkers={onToggleLossCutMarkers}
        lossCutMarkerCount={lossCutEvents?.length}
      />
      {consistencyWarnings.length > 0 ? (
        <Alert severity="warning" sx={{ mb: { xs: 0.75, sm: 1.5 } }}>
          {consistencyWarnings.length} continuity warning(s) detected after
          resume. Review the latest metric jump before trusting this run.
        </Alert>
      ) : null}
      <Grid
        container
        spacing={{ xs: 0.75, sm: 1 }}
        justifyContent="flex-start"
        alignItems="stretch"
        sx={{ mt: 0, minWidth: 0, width: '100%' }}
      >
        {orderedKeys.map((key) => {
          // OHLC chart
          if (key === OHLC_KEY) {
            return (
              <Grid
                key={OHLC_KEY}
                size={{ xs: 12, lg: 6 }}
                draggable
                onDragStart={(e) => handleDragStart(e, OHLC_KEY)}
                onDragOver={(e) => handleDragOver(e, OHLC_KEY)}
                onDrop={(e) => handleDrop(e, OHLC_KEY)}
                onDragEnd={handleDragEnd}
                sx={{
                  opacity: dragKey === OHLC_KEY ? 0.4 : 1,
                  cursor: 'grab',
                  minWidth: 0,
                  transition:
                    'opacity 120ms ease, transform 120ms ease, outline-color 120ms ease',
                  transform:
                    dragOverKey === OHLC_KEY && dragKey !== OHLC_KEY
                      ? 'translateY(-2px)'
                      : 'none',
                  outline: '2px solid',
                  outlineColor:
                    dragOverKey === OHLC_KEY && dragKey !== OHLC_KEY
                      ? 'primary.main'
                      : 'transparent',
                  outlineOffset: 3,
                  borderRadius: 1,
                }}
              >
                <MetricsOhlcChart
                  instrument={instrument!}
                  startTime={startTime!}
                  endTime={endTime ?? undefined}
                  cardHeight={CHART_CARD_HEIGHT}
                  currentTickTimestamp={currentTickTimestamp}
                  currentTickPrice={currentTickPrice}
                  refreshToken={ohlcRefreshToken}
                  timezone={timezone}
                />
              </Grid>
            );
          }

          if (key === RETURN_PERIOD_CHART_KEY) {
            const chart =
              availableReturnCharts.find(
                (candidate) => candidate.period === effectiveReturnPeriod
              ) ?? availableReturnCharts[0];
            const cd = chart ? returnChartDataMap[chart.key] : undefined;
            if (!chart || !cd || cd.labels.length === 0) return null;
            const maxChars = cd.values.reduce((max, value) => {
              const label = formatYLabel(value, 'pct');
              return Math.max(max, label.length);
            }, 0);
            const yAxisWidth = Math.max(
              MIN_Y_AXIS_WIDTH,
              maxChars * CHAR_WIDTH_PX + Y_AXIS_OVERHEAD
            );
            return (
              <Grid
                key={RETURN_PERIOD_CHART_KEY}
                size={{ xs: 12, lg: 6 }}
                draggable
                onDragStart={(e) => handleDragStart(e, RETURN_PERIOD_CHART_KEY)}
                onDragOver={(e) => handleDragOver(e, RETURN_PERIOD_CHART_KEY)}
                onDrop={(e) => handleDrop(e, RETURN_PERIOD_CHART_KEY)}
                onDragEnd={handleDragEnd}
                sx={{
                  opacity: dragKey === RETURN_PERIOD_CHART_KEY ? 0.4 : 1,
                  cursor: 'grab',
                  minWidth: 0,
                  transition:
                    'opacity 120ms ease, transform 120ms ease, outline-color 120ms ease',
                  transform:
                    dragOverKey === RETURN_PERIOD_CHART_KEY &&
                    dragKey !== RETURN_PERIOD_CHART_KEY
                      ? 'translateY(-2px)'
                      : 'none',
                  outline: '2px solid',
                  outlineColor:
                    dragOverKey === RETURN_PERIOD_CHART_KEY &&
                    dragKey !== RETURN_PERIOD_CHART_KEY
                      ? 'primary.main'
                      : 'transparent',
                  outlineOffset: 3,
                  borderRadius: 1,
                }}
              >
                <ChartPanel
                  title={t('metrics.period_return', {
                    defaultValue: 'Period Return',
                  })}
                  valueLabel={formatValue(cd.lastValue, 'pct')}
                  height={CHART_CARD_HEIGHT}
                  headerPrefix={
                    <DragIndicatorIcon
                      sx={{
                        fontSize: 16,
                        color: 'text.disabled',
                        cursor: 'grab',
                        mr: spacingTokens.xxs,
                      }}
                    />
                  }
                  headerActions={
                    <ToggleButtonGroup
                      exclusive
                      size="small"
                      value={chart.period}
                      onChange={(_, nextPeriod: ReturnPeriod | null) => {
                        if (nextPeriod) setSelectedReturnPeriod(nextPeriod);
                      }}
                      onMouseDown={(event) => event.stopPropagation()}
                      onClick={(event) => event.stopPropagation()}
                      aria-label={t('metrics.period_return', {
                        defaultValue: 'Period Return',
                      })}
                      sx={{
                        '& .MuiToggleButton-root': {
                          px: 0.75,
                          py: 0.25,
                          fontSize: '0.6875rem',
                          lineHeight: 1.2,
                        },
                      }}
                    >
                      {availableReturnCharts.map((option) => (
                        <ToggleButton
                          key={option.period}
                          value={option.period}
                          aria-label={t(`metrics.${option.key}`, {
                            defaultValue: option.key.replace(/_/g, ' '),
                          })}
                        >
                          {t(RETURN_PERIOD_SHORT_LABEL_KEYS[option.period])}
                        </ToggleButton>
                      ))}
                    </ToggleButtonGroup>
                  }
                >
                  <FillBarChart
                    fallbackHeight={LINE_CHART_FALLBACK_HEIGHT}
                    xAxis={[
                      {
                        data: cd.labels,
                        scaleType: 'band' as const,
                        tickLabelStyle: { fontSize: 10 },
                      },
                    ]}
                    yAxis={[
                      {
                        position: 'right',
                        width: yAxisWidth,
                        valueFormatter: (v: number | null) =>
                          v != null ? formatYLabel(v, 'pct') : '',
                      },
                    ]}
                    series={[
                      {
                        data: cd.values,
                        color: chart.color,
                        label: t(`metrics.${chart.key}`, {
                          defaultValue: chart.key.replace(/_/g, ' '),
                        }),
                        valueFormatter: (v: number | null) =>
                          v != null ? formatValue(v, 'pct') : '',
                      },
                    ]}
                    grid={{ horizontal: true }}
                    margin={{
                      left: LINE_CHART_LEFT_MARGIN,
                      right: LINE_CHART_RIGHT_MARGIN,
                      top: LINE_CHART_TOP_MARGIN,
                      bottom: LINE_CHART_BOTTOM_MARGIN,
                    }}
                    hideLegend
                    slotProps={{
                      axisTickLabel: {
                        style: { fontSize: 10 },
                      },
                    }}
                  />
                </ChartPanel>
              </Grid>
            );
          }

          // Metric line chart
          const chart = chartDefinitionMap.get(key);
          if (!chart) return null;
          const cd = chartDataMap[chart.key];
          if (!cd || cd.x.length < 2) return null;
          const lastVal = cd.lastValue;
          const rangeMs = cd.x[cd.x.length - 1].getTime() - cd.x[0].getTime();
          const yTickCount = computeYTickCount(cd.yValues);
          const xTickCount = computeXTickCount(cd.x.length);
          const metricYAxisWidth = yAxisWidthMap[chart.key] ?? MIN_Y_AXIS_WIDTH;
          return (
            <Grid
              key={chart.key}
              size={{ xs: 12, lg: 6 }}
              draggable
              onDragStart={(e) => handleDragStart(e, chart.key)}
              onDragOver={(e) => handleDragOver(e, chart.key)}
              onDrop={(e) => handleDrop(e, chart.key)}
              onDragEnd={handleDragEnd}
              sx={{
                opacity: dragKey === chart.key ? 0.4 : 1,
                cursor: 'grab',
                minWidth: 0,
                transition:
                  'opacity 120ms ease, transform 120ms ease, outline-color 120ms ease',
                transform:
                  dragOverKey === chart.key && dragKey !== chart.key
                    ? 'translateY(-2px)'
                    : 'none',
                outline: '2px solid',
                outlineColor:
                  dragOverKey === chart.key && dragKey !== chart.key
                    ? 'primary.main'
                    : 'transparent',
                outlineOffset: 3,
                borderRadius: 1,
              }}
            >
              <ChartPanel
                title={t(`metrics.${chart.key}`, {
                  defaultValue: chart.key.replace(/_/g, ' '),
                })}
                valueLabel={formatValue(lastVal, chart.format, cd.lastCurrency)}
                height={CHART_CARD_HEIGHT}
                headerPrefix={
                  <DragIndicatorIcon
                    sx={{
                      fontSize: 16,
                      color: 'text.disabled',
                      cursor: 'grab',
                      mr: spacingTokens.xxs,
                    }}
                  />
                }
              >
                <FillLineChart
                  fallbackHeight={LINE_CHART_FALLBACK_HEIGHT}
                  xAxis={[
                    {
                      data: cd.x,
                      scaleType: 'time' as const,
                      tickNumber: xTickCount,
                      tickLabelStyle: { fontSize: 10 },
                      valueFormatter: (
                        v: Date,
                        context: { location: string }
                      ) => {
                        if (context.location === 'tooltip') {
                          return formatTooltipDate(
                            v,
                            timezone,
                            settings.dateFormat
                          );
                        }
                        return formatTickLabel(
                          v,
                          rangeMs,
                          effectiveInterval,
                          timezone,
                          settings.dateFormat
                        );
                      },
                    },
                  ]}
                  yAxis={[
                    {
                      position: 'right',
                      width: metricYAxisWidth,
                      tickNumber: yTickCount,
                      valueFormatter: (v: number | null) =>
                        v != null ? formatYLabel(v, chart.format) : '',
                    },
                  ]}
                  series={cd.series.map(
                    ({ metric, y, currency: seriesCurrency }) => ({
                      data: y,
                      color: metric.color,
                      label: t(`metrics.${metric.key}`, {
                        defaultValue: metric.key.replace(/_/g, ' '),
                      }),
                      showMark: false,
                      valueFormatter: (v: number | null) =>
                        v != null
                          ? formatValue(v, metric.format, seriesCurrency)
                          : '',
                    })
                  )}
                  axisHighlight={{ x: 'line', y: 'none' }}
                  grid={{ vertical: true, horizontal: true }}
                  margin={{
                    left: LINE_CHART_LEFT_MARGIN,
                    right: LINE_CHART_RIGHT_MARGIN,
                    top: LINE_CHART_TOP_MARGIN,
                    bottom: LINE_CHART_BOTTOM_MARGIN,
                  }}
                  hideLegend={cd.series.length <= 1}
                  slotProps={{
                    axisTickLabel: {
                      style: { fontSize: 10 },
                    },
                  }}
                >
                  {showLossCutMarkers &&
                    LOSS_CUT_OVERLAY_KEYS.has(chart.key) &&
                    lossCutEvents?.map((event) => (
                      <ChartsReferenceLine
                        key={event.id}
                        x={new Date(event.time * 1000)}
                        lineStyle={{
                          stroke: '#dc2626',
                          strokeWidth: 1.5,
                          strokeDasharray: '4 2',
                          opacity: 0.7,
                        }}
                        label={`LC ${event.units.toLocaleString()}`}
                        labelAlign="start"
                        labelStyle={{
                          fontSize: 9,
                          fill: '#dc2626',
                          fontWeight: 500,
                        }}
                      />
                    ))}
                </FillLineChart>
              </ChartPanel>
            </Grid>
          );
        })}
      </Grid>
      <MetricsChartOrderDialog
        key={
          orderDialogOpen
            ? `open-${chartOrderItems.map((item) => item.key).join('|')}`
            : 'closed'
        }
        open={orderDialogOpen}
        items={chartOrderItems}
        onClose={() => setOrderDialogOpen(false)}
        onSave={setOrder}
        onReset={resetOrder}
      />
    </Box>
  );
}
