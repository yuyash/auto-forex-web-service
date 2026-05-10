import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentProps,
  type DragEvent as ReactDragEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type MutableRefObject,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  FormControlLabel,
  FormGroup,
  IconButton,
  InputLabel,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
  useMediaQuery,
} from '@mui/material';
import ArrowDownIcon from '@mui/icons-material/ArrowDownward';
import ArrowUpIcon from '@mui/icons-material/ArrowUpward';
import CenterFocusStrongIcon from '@mui/icons-material/CenterFocusStrong';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import MergeIcon from '@mui/icons-material/Merge';
import RefreshIcon from '@mui/icons-material/Refresh';
import SettingsIcon from '@mui/icons-material/Settings';
import TimelineIcon from '@mui/icons-material/Timeline';
import type { CanvasRenderingTarget2D } from 'fancy-canvas';
import { formatInTimeZone } from 'date-fns-tz';
import {
  CandlestickSeries,
  LineStyle,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type CandlestickData,
  type IChartApi,
  type IPrimitivePaneRenderer,
  type IPrimitivePaneView,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesPrimitive,
  type SeriesAttachedParameter,
  type Time,
  type WhitespaceData,
} from 'lightweight-charts';
import { LineChart } from '@mui/x-charts/LineChart';
import { ChartsReferenceLine } from '@mui/x-charts/ChartsReferenceLine';
import { useTheme } from '@mui/material/styles';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import { useSnowballNetChart } from '../../../../hooks/useStrategyData';
import type { TaskType } from '../../../../types/common';
import type {
  SnowballNetChartResponse,
  SnowballNetLineSeries,
  SnowballNetLinePoint,
  SnowballNetMarker,
} from '../../../../types/strategyVisualization';
import {
  DEFAULT_OHLC_OVERLAY_SETTINGS,
  useOhlcChartOverlays,
  type OhlcOverlaySettings,
} from '../../../common/ohlcChartOverlays';
import {
  AdaptiveTimeScale,
  createSuppressedTickMarkFormatter,
  createTooltipTimeFormatter,
} from '../../../../utils/adaptiveTimeScalePlugin';
import { getCandleColors } from '../../../../utils/candleColors';
import { SequencePositionLine } from '../../../../utils/SequencePositionLine';
import {
  currencySymbol,
  formatAppNumber,
  formatAppPercent,
} from '../../../../utils/numberFormat';
import {
  removeStoredValue,
  readStoredValue,
  writeStoredValue,
} from '../../../../utils/persistentState';
import {
  baseCurrencyFromInstrument,
  quoteCurrencyFromInstrument,
} from '../../../../utils/instrumentCurrency';
import {
  measureContainer,
  measureContainerWidth,
} from '../../../../utils/measureContainer';
import {
  DEFAULT_SNOWBALL_NET_GRANULARITY,
  DEFAULT_SNOWBALL_NET_SIDE_BARS,
  SNOWBALL_NET_GRANULARITY_OPTIONS,
  constrainSnowballNetGranularityForRange,
  granularityForRangeSeconds,
  isSnowballNetGranularityAllowedForRange,
  type SnowballNetGranularitySelection,
} from './snowballNetChartRange';

interface SnowballNetStrategyTabProps {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  instrument?: string;
  taskStartTime?: string | null;
  taskEndTime?: string | null;
  enableRealTimeUpdates?: boolean;
  timezone?: string;
  /** Loss-cut events to overlay as vertical reference lines on margin/PnL charts. */
  lossCutEvents?: Array<{
    id: string;
    time: number;
    units: number;
  }>;
  /** Whether to show loss-cut markers on charts. */
  showLossCutMarkers?: boolean;
}

const REFRESH_OPTIONS = [5, 15, 30, 60, 0] as const;
const DEFAULT_GRANULARITY = DEFAULT_SNOWBALL_NET_GRANULARITY;
const DEFAULT_GRANULARITY_SELECTION: SnowballNetGranularitySelection = 'Auto';
const DEFAULT_SIDE_BARS = DEFAULT_SNOWBALL_NET_SIDE_BARS;
const MIN_NO_DATA_BUCKETS = 2;
const SCROLL_FETCH_DEBOUNCE_MS = 450;
const PROGRAMMATIC_RANGE_SUPPRESS_MS = 800;
const MARGIN_LINE_ID = 'margin_ratio_pct';
const LOSS_CUT_THRESHOLD_LINE_ID = 'loss_cut_threshold_pips';
const MARGIN_REDUCE_THRESHOLD_LINE_ID = 'margin_reduce_threshold_pct';
const MARGIN_REDUCE_TARGET_LINE_ID = 'margin_reduce_target_pct';
const EMERGENCY_THRESHOLD_LINE_ID = 'emergency_threshold_pct';
const CURRENT_PRICE_LINE_ID = 'current_price';
const REALIZED_PNL_LINE_ID = 'realized_pnl';
const UNREALIZED_PNL_LINE_ID = 'unrealized_pnl';
const SNOWBALL_NET_CHART_SETTINGS_KEY = 'snowball_net_strategy_chart_settings';
const SNOWBALL_NET_CHART_ORDER_KEY = 'snowball_net_strategy_chart_order';
const OHLC_CHART_HEIGHT_KEY = 'snowball_net_strategy_ohlc_chart_height';
const DEFAULT_OHLC_CHART_HEIGHT = 460;
const MIN_OHLC_CHART_HEIGHT = 240;
const MAX_OHLC_CHART_HEIGHT = 1200;
const OHLC_CHART_RESIZE_STEP = 20;
const SNOWBALL_NET_CHART_KEYS = [
  'ohlc',
  'netUnits',
  'pips',
  'margin',
  'pnl',
  'averagePrice',
  'takeProfit',
  'nextAdd',
] as const;
const LINE_CHART_FALLBACK_HEIGHT = 170;
const LINE_CHART_CARD_HEIGHT = 240;
const MIN_CHART_MEASURE_PX = 1;
const Y_AXIS_CHAR_WIDTH_PX = 6;
const Y_AXIS_OVERHEAD_PX = 8;
const MIN_Y_AXIS_WIDTH = 34;
const LINE_CHART_LEFT_MARGIN = 8;
const LINE_CHART_RIGHT_MARGIN = 8;
const LINE_CHART_TOP_MARGIN = 4;
const LINE_CHART_BOTTOM_MARGIN = 34;
const SECOND = 1;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

const SNOWBALL_NET_RANGE_PRESETS = [
  { value: 'follow', labelKey: 'follow' },
  { value: 'full', labelKey: 'full' },
  { value: '5m', labelKey: 'last5Minutes', seconds: 5 * MINUTE },
  { value: '15m', labelKey: 'last15Minutes', seconds: 15 * MINUTE },
  { value: '1h', labelKey: 'last1Hour', seconds: HOUR },
  { value: '4h', labelKey: 'last4Hours', seconds: 4 * HOUR },
  { value: '12h', labelKey: 'last12Hours', seconds: 12 * HOUR },
  { value: '1d', labelKey: 'last1Day', seconds: DAY },
  { value: '3d', labelKey: 'last3Days', seconds: 3 * DAY },
  { value: '1w', labelKey: 'last1Week', seconds: 7 * DAY },
  { value: '2w', labelKey: 'last2Weeks', seconds: 14 * DAY },
  { value: '4w', labelKey: 'last4Weeks', seconds: 28 * DAY },
  { value: '1mo', labelKey: 'last1Month', seconds: 30 * DAY },
  { value: '3mo', labelKey: 'last3Months', seconds: 93 * DAY },
  { value: '6mo', labelKey: 'last6Months', seconds: 183 * DAY },
  { value: '1y', labelKey: 'last1Year', seconds: 365 * DAY },
  { value: 'custom', labelKey: 'custom' },
] as const;
const GRANULARITY_OPTIONS = SNOWBALL_NET_GRANULARITY_OPTIONS;

type SnowballNetChartKey = (typeof SNOWBALL_NET_CHART_KEYS)[number];
type SnowballNetRangePreset =
  (typeof SNOWBALL_NET_RANGE_PRESETS)[number]['value'];

const SNOWBALL_NET_CHART_COLORS: Record<SnowballNetChartKey, string> = {
  ohlc: '#26a69a',
  netUnits: '#0288d1',
  pips: '#7c3aed',
  margin: '#ea580c',
  pnl: '#2e7d32',
  averagePrice: '#2563eb',
  takeProfit: '#16a34a',
  nextAdd: '#dc2626',
};

const OHLC_OVERLAY_DEFAULTS: OhlcOverlaySettings = {
  ...DEFAULT_OHLC_OVERLAY_SETTINGS,
  ema12: true,
  ema26: true,
  supportResistance: false,
  markers: false,
};

const snowballNetChartSettingsSchema = z.object({
  charts: z.object({
    ohlc: z.boolean(),
    netUnits: z.boolean(),
    pips: z.boolean(),
    margin: z.boolean(),
    pnl: z.boolean(),
    averagePrice: z.boolean(),
    takeProfit: z.boolean(),
    nextAdd: z.boolean(),
  }),
  ohlc: z.object({
    tradeMarkers: z.boolean(),
    currentTick: z.boolean(),
    averagePrice: z.boolean(),
    takeProfit: z.boolean(),
    nextAdd: z.boolean(),
    marginRatio: z.boolean(),
    sma20: z.boolean(),
    sma50: z.boolean(),
    ema12: z.boolean(),
    ema26: z.boolean(),
    bollinger: z.boolean(),
    volume: z.boolean(),
    supportResistance: z.boolean(),
    markers: z.boolean(),
  }),
});

type SnowballNetChartSettings = z.infer<typeof snowballNetChartSettingsSchema>;

const ohlcChartHeightSchema = z
  .number()
  .min(MIN_OHLC_CHART_HEIGHT)
  .max(MAX_OHLC_CHART_HEIGHT);
const snowballNetChartOrderSchema = z.array(z.enum(SNOWBALL_NET_CHART_KEYS));

function clampOhlcChartHeight(height: number): number {
  return Math.min(
    MAX_OHLC_CHART_HEIGHT,
    Math.max(MIN_OHLC_CHART_HEIGHT, Math.round(height))
  );
}

function normalizeSnowballNetChartOrder(
  keys: readonly string[] | null | undefined
): SnowballNetChartKey[] {
  const validKeys = new Set<string>(SNOWBALL_NET_CHART_KEYS);
  const next: SnowballNetChartKey[] = ['ohlc'];
  for (const key of keys ?? []) {
    if (
      key !== 'ohlc' &&
      validKeys.has(key) &&
      !next.includes(key as SnowballNetChartKey)
    ) {
      next.push(key as SnowballNetChartKey);
    }
  }
  for (const key of SNOWBALL_NET_CHART_KEYS) {
    if (key !== 'ohlc' && !next.includes(key)) {
      next.push(key);
    }
  }
  return next;
}

const DEFAULT_CHART_SETTINGS: SnowballNetChartSettings = {
  charts: {
    ohlc: true,
    netUnits: true,
    pips: true,
    margin: true,
    pnl: true,
    averagePrice: true,
    takeProfit: true,
    nextAdd: true,
  },
  ohlc: {
    tradeMarkers: true,
    currentTick: true,
    averagePrice: true,
    takeProfit: true,
    nextAdd: true,
    marginRatio: false,
    ...OHLC_OVERLAY_DEFAULTS,
  },
};

interface NoDataRegion {
  from: number;
  to: number;
}

interface NoDataRegionStyle {
  fill: string;
  stroke: string;
  text: string;
  label: string;
  subLabel: string;
}

interface CandleBucketRange {
  step: number;
  since: number;
  until: number;
}

interface ChartTimeRange {
  from: number;
  to: number;
}

interface AppliedDateRange {
  sinceMs: number;
  untilMs: number;
}

interface LoadedChartWindow extends ChartTimeRange {
  step: number;
}

interface LineChartTimeDomain {
  min: Date;
  max: Date;
}

interface PriceAxisLabelSpec {
  id: string;
  title: string;
  price: number;
  color: string;
  lineStyle: LineStyle;
}

function toNumber(value: unknown): number | null {
  if (value == null || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function isoFromSeconds(value: number): string {
  return new Date(value * 1000).toISOString();
}

function millisFromIso(value?: string | null): number | null {
  if (!value) return null;
  const millis = new Date(value).getTime();
  return Number.isFinite(millis) ? millis : null;
}

function formatDateTimeLocal(value?: string | null): string {
  const millis = millisFromIso(value);
  if (millis == null) return '';
  const date = new Date(millis);
  const localMillis = date.getTime() - date.getTimezoneOffset() * 60_000;
  return new Date(localMillis).toISOString().slice(0, 16);
}

function isoFromDateTimeLocal(value: string): string | null {
  if (!value) return null;
  const millis = new Date(value).getTime();
  return Number.isFinite(millis) ? new Date(millis).toISOString() : null;
}

function customRangeFromControls(
  customSince: string,
  customUntil: string
): AppliedDateRange | null {
  const since = isoFromDateTimeLocal(customSince);
  const until = isoFromDateTimeLocal(customUntil);
  const sinceMs = millisFromIso(since);
  const untilMs = millisFromIso(until);
  if (sinceMs != null && untilMs != null && untilMs > sinceMs) {
    return { sinceMs, untilMs };
  }
  return null;
}

function rangePresetSeconds(preset: SnowballNetRangePreset): number | null {
  const option = SNOWBALL_NET_RANGE_PRESETS.find(
    (candidate) => candidate.value === preset
  );
  return option && 'seconds' in option ? option.seconds : null;
}

function chartTimeDomain(
  data: SnowballNetChartResponse
): LineChartTimeDomain | undefined {
  const min = new Date(data.window.since);
  const max = new Date(data.window.until);
  if (
    Number.isNaN(min.getTime()) ||
    Number.isNaN(max.getTime()) ||
    max <= min
  ) {
    return undefined;
  }
  return { min, max };
}

function formatLineChartXAxis(
  value: Date,
  timezone: string,
  location?: string
): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '';

  const datePart = formatInTimeZone(date, timezone, 'MM/dd');
  const timePart = formatInTimeZone(date, timezone, 'HH:mm');
  return location === 'tooltip'
    ? `${datePart} ${timePart}`
    : `${datePart}\n${timePart}`;
}

function normalizeCurrencyCode(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const normalized = value.trim().toUpperCase();
  return normalized ? normalized : null;
}

function pnlCurrencyCode(data: SnowballNetChartResponse): string | null {
  return (
    normalizeCurrencyCode(data.current.pnl_currency) ??
    normalizeCurrencyCode(data.current.quote_currency) ??
    quoteCurrencyFromInstrument(data.instrument)
  );
}

function appendUnitLabel(label: string, unit?: string | null): string {
  return unit ? `${label} (${unit})` : label;
}

function formatNumberWithUnit(
  value: number,
  unit?: string | null,
  options: Parameters<typeof formatAppNumber>[1] = {}
): string {
  if (!unit) return formatAppNumber(value, options);

  const sign = options.signed ? (value >= 0 ? '+' : '-') : value < 0 ? '-' : '';
  const formatted = formatAppNumber(Math.abs(value), {
    ...options,
    signed: false,
  });
  const symbol = currencySymbol(unit);
  return symbol && symbol !== unit
    ? `${sign}${symbol} ${formatted}`
    : `${sign}${formatted} ${unit}`;
}

function formatNullablePnl(value: number | null, unit?: string | null): string {
  return value == null
    ? '-'
    : formatNumberWithUnit(value, unit, {
        maximumFractionDigits: 2,
        signed: true,
      });
}

function snowballNetChartTitle(
  key: SnowballNetChartKey,
  t: TFunction,
  options: {
    instrument?: string | null;
    pnlCurrency?: string | null;
    priceCurrency?: string | null;
  } = {}
): string {
  switch (key) {
    case 'ohlc':
      return options.instrument
        ? options.instrument.replace('_', '/')
        : t('strategy:snowballNet.chart.settings.ohlc');
    case 'netUnits':
      return t('strategy:snowballNet.chart.netUnits');
    case 'pips':
      return t('strategy:snowballNet.chart.pipsFromAverage');
    case 'margin':
      return t('strategy:snowballNet.chart.marginRatio');
    case 'pnl':
      return appendUnitLabel(
        t('strategy:snowballNet.chart.pnl'),
        options.pnlCurrency
      );
    case 'averagePrice':
      return appendUnitLabel(
        t('strategy:snowballNet.chart.averagePrice'),
        options.priceCurrency
      );
    case 'takeProfit':
      return appendUnitLabel(
        t('strategy:snowballNet.chart.takeProfit'),
        options.priceCurrency
      );
    case 'nextAdd':
      return appendUnitLabel(
        t('strategy:snowballNet.chart.nextAdd'),
        options.priceCurrency
      );
    default:
      return key;
  }
}

function normalizeChartRange(
  range: { from: unknown; to: unknown } | null | undefined
): ChartTimeRange | null {
  if (!range) return null;
  const from = Number(range.from);
  const to = Number(range.to);
  if (!Number.isFinite(from) || !Number.isFinite(to) || to <= from) {
    return null;
  }
  return { from, to };
}

function rangesClose(
  left: ChartTimeRange | null,
  right: ChartTimeRange | null,
  toleranceSeconds: number
): boolean {
  if (!left || !right) return false;
  return (
    Math.abs(left.from - right.from) <= toleranceSeconds &&
    Math.abs(left.to - right.to) <= toleranceSeconds
  );
}

function clampChartViewportRangeToBounds(
  range: ChartTimeRange | null,
  bounds: ChartTimeRange | null
): ChartTimeRange | null {
  if (!range) return null;
  if (!bounds) return range;
  const boundsSpan = bounds.to - bounds.from;
  if (boundsSpan <= 0) return null;
  const rangeSpan = range.to - range.from;
  if (rangeSpan <= 0) return null;
  if (rangeSpan >= boundsSpan) return bounds;

  let from = range.from;
  if (from < bounds.from) {
    from = bounds.from;
  } else if (from + rangeSpan > bounds.to) {
    from = bounds.to - rangeSpan;
  }

  return {
    from,
    to: from + rangeSpan,
  };
}

function intersectChartRangeWithBounds(
  range: ChartTimeRange,
  bounds: ChartTimeRange | null
): ChartTimeRange | null {
  if (!bounds) return range;
  const bounded = {
    from: Math.max(range.from, bounds.from),
    to: Math.min(range.to, bounds.to),
  };
  return bounded.to > bounded.from ? bounded : null;
}

function clampDateRangeToBounds(
  range: AppliedDateRange | null,
  bounds: AppliedDateRange | null
): AppliedDateRange | null {
  if (!range) return null;
  if (!bounds) return range;
  const bounded = clampChartViewportRangeToBounds(
    {
      from: range.sinceMs / 1000,
      to: range.untilMs / 1000,
    },
    {
      from: bounds.sinceMs / 1000,
      to: bounds.untilMs / 1000,
    }
  );
  return bounded
    ? {
        sinceMs: Math.floor(bounded.from * 1000),
        untilMs: Math.ceil(bounded.to * 1000),
      }
    : null;
}

function chartTimeSeconds(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const ms = new Date(value).getTime();
    return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
  }
  if (value && typeof value === 'object') {
    const candidate = value as Partial<{
      year: number;
      month: number;
      day: number;
    }>;
    if (
      Number.isFinite(candidate.year) &&
      Number.isFinite(candidate.month) &&
      Number.isFinite(candidate.day)
    ) {
      return Math.floor(
        Date.UTC(candidate.year!, candidate.month! - 1, candidate.day!) / 1000
      );
    }
  }
  return null;
}

function visibleChartRangeIncludingWhitespace({
  chart,
  series,
  logicalRange,
  stepSeconds,
}: {
  chart: IChartApi;
  series: ISeriesApi<'Candlestick'>;
  logicalRange: { from: number; to: number } | null;
  stepSeconds: number;
}): ChartTimeRange | null {
  const visibleTimeRange = normalizeChartRange(
    chart.timeScale().getVisibleRange()
  );
  if (!logicalRange) return visibleTimeRange;

  const seriesData = series.data();
  if (seriesData.length === 0) return visibleTimeRange;

  const firstTime = chartTimeSeconds(seriesData[0]?.time);
  const lastTime = chartTimeSeconds(seriesData[seriesData.length - 1]?.time);
  if (firstTime == null || lastTime == null || lastTime < firstTime) {
    return visibleTimeRange;
  }

  const barsInfo = series.barsInLogicalRange(logicalRange);
  let from = visibleTimeRange?.from ?? firstTime;
  let to = visibleTimeRange?.to ?? lastTime;

  if (barsInfo) {
    if (barsInfo.barsBefore < 0) {
      from = Math.min(
        from,
        firstTime - Math.abs(barsInfo.barsBefore) * stepSeconds
      );
    }
    if (barsInfo.barsAfter < 0) {
      to = Math.max(to, lastTime + Math.abs(barsInfo.barsAfter) * stepSeconds);
    }
  }

  const normalized = {
    from: Math.max(0, Math.floor(from)),
    to: Math.ceil(to),
  };
  return normalized.to > normalized.from ? normalized : null;
}

function markerColor(marker: SnowballNetMarker): string {
  return marker.action === 'open' ? '#16a34a' : '#dc2626';
}

function markerText(marker: SnowballNetMarker, t: TFunction): string {
  const base =
    marker.action === 'open'
      ? t('strategy:snowballNet.chart.markers.add')
      : t('strategy:snowballNet.chart.markers.close');
  return marker.count > 1
    ? t('strategy:snowballNet.chart.markers.count', {
        action: base,
        count: marker.count,
      })
    : base;
}

function buildMarkerData(markers: SnowballNetMarker[], t: TFunction) {
  return markers.map((marker) => ({
    time: marker.time as Time,
    position:
      marker.action === 'open' ? ('belowBar' as const) : ('aboveBar' as const),
    color: markerColor(marker),
    shape:
      marker.action === 'open' ? ('arrowUp' as const) : ('arrowDown' as const),
    text: markerText(marker, t),
  }));
}

function normalizeStrategyLabelKey(labelKey?: string | null): string | null {
  if (!labelKey) return null;
  return labelKey.startsWith('strategy.')
    ? labelKey.slice('strategy.'.length)
    : labelKey;
}

function lineLabel(line: SnowballNetLineSeries, t?: TFunction): string {
  const fallback = line.label ?? line.id.replace(/_/g, ' ');
  if (line.id === 'next_add_price_disabled') {
    return t
      ? t('strategy:snowballNet.chart.nextAddDisabled', {
          defaultValue: fallback,
        })
      : fallback;
  }
  const labelKey = normalizeStrategyLabelKey(line.label_key);
  if (!t || !labelKey) return fallback;
  return t(`strategy:${labelKey}`, { defaultValue: fallback });
}

function lightweightLineStyle(line: SnowballNetLineSeries): LineStyle {
  if (typeof line.line_style === 'number') {
    return line.line_style;
  }
  switch (line.line_style) {
    case 'dotted':
      return LineStyle.Dotted;
    case 'dashed':
      return LineStyle.Dashed;
    case 'large_dashed':
      return LineStyle.LargeDashed;
    case 'sparse_dotted':
      return LineStyle.SparseDotted;
    default:
      return LineStyle.Solid;
  }
}

function latestLinePoint(
  line: SnowballNetLineSeries
): SnowballNetLinePoint | null {
  if (line.points.length === 0) return null;
  return line.points.reduce((latest, point) =>
    point.time >= latest.time ? point : latest
  );
}

function priceAxisLabelTitle(
  line: SnowballNetLineSeries,
  t: TFunction
): string {
  if (line.id === 'next_add_price_disabled') {
    return t('strategy:snowballNet.chart.nextAddDisabled', {
      defaultValue: line.label ?? 'Next add off',
    });
  }
  return lineLabel(line, t);
}

function buildPriceAxisLabelSpecs(
  lines: SnowballNetLineSeries[],
  t: TFunction
): PriceAxisLabelSpec[] {
  const specs: PriceAxisLabelSpec[] = [];

  for (const id of ['average_price', 'target_price'] as const) {
    const line = lines.find((candidate) => candidate.id === id);
    const point = line ? latestLinePoint(line) : null;
    if (!line || !point) continue;
    specs.push({
      id,
      title: priceAxisLabelTitle(line, t),
      price: point.value,
      color: line.color,
      lineStyle: lightweightLineStyle(line),
    });
  }

  const nextAddLine = lines
    .filter(
      (line) =>
        line.id === 'next_add_price' || line.id === 'next_add_price_disabled'
    )
    .map((line) => ({ line, point: latestLinePoint(line) }))
    .filter(
      (
        item
      ): item is { line: SnowballNetLineSeries; point: SnowballNetLinePoint } =>
        item.point !== null
    )
    .sort((left, right) => right.point.time - left.point.time)[0];
  if (nextAddLine) {
    specs.push({
      id: 'next_add_price',
      title: priceAxisLabelTitle(nextAddLine.line, t),
      price: nextAddLine.point.value,
      color: nextAddLine.line.color,
      lineStyle: lightweightLineStyle(nextAddLine.line),
    });
  }

  return specs;
}

function lineSeriesData(line: SnowballNetLineSeries) {
  return line.points.map((point) => ({
    time: point.time as Time,
    value: point.value,
  }));
}

function marginOverlayLine(
  lines: SnowballNetLineSeries[]
): SnowballNetLineSeries | null {
  return (
    lines.find(
      (line) => line.id === MARGIN_LINE_ID && line.points.length > 0
    ) ?? null
  );
}

function isPipsThresholdLine(line: SnowballNetLineSeries): boolean {
  return line.id === LOSS_CUT_THRESHOLD_LINE_ID;
}

function isMarginThresholdLine(line: SnowballNetLineSeries): boolean {
  return (
    line.id === MARGIN_REDUCE_THRESHOLD_LINE_ID ||
    line.id === MARGIN_REDUCE_TARGET_LINE_ID ||
    line.id === EMERGENCY_THRESHOLD_LINE_ID
  );
}

function isThresholdLine(line: SnowballNetLineSeries): boolean {
  return isPipsThresholdLine(line) || isMarginThresholdLine(line);
}

function pipsChartLines(lines: SnowballNetLineSeries[]) {
  return lines.filter(
    (line) => line.id === 'pips_from_average' || isPipsThresholdLine(line)
  );
}

function marginChartLines(lines: SnowballNetLineSeries[]) {
  return lines.filter(
    (line) => line.id === MARGIN_LINE_ID || isMarginThresholdLine(line)
  );
}

function pnlChartLines(lines: SnowballNetLineSeries[]) {
  return lines.filter(
    (line) =>
      line.id === REALIZED_PNL_LINE_ID || line.id === UNREALIZED_PNL_LINE_ID
  );
}

function netUnitsChartLines(lines: SnowballNetLineSeries[]) {
  return lines.filter((line) => line.id === 'net_units');
}

function priceChartLines(
  lines: SnowballNetLineSeries[],
  chartId: 'averagePrice' | 'takeProfit' | 'nextAdd'
) {
  const ids =
    chartId === 'averagePrice'
      ? new Set(['average_price', CURRENT_PRICE_LINE_ID])
      : chartId === 'takeProfit'
        ? new Set(['target_price', CURRENT_PRICE_LINE_ID])
        : new Set([
            'next_add_price',
            'next_add_price_disabled',
            CURRENT_PRICE_LINE_ID,
          ]);
  return lines.filter((line) => ids.has(line.id));
}

function ohlcPriceLineVisible(
  line: SnowballNetLineSeries,
  settings: SnowballNetChartSettings['ohlc']
): boolean {
  if (line.id === 'average_price') return settings.averagePrice;
  if (line.id === 'target_price') return settings.takeProfit;
  if (line.id === 'next_add_price' || line.id === 'next_add_price_disabled') {
    return settings.nextAdd;
  }
  if (line.id === CURRENT_PRICE_LINE_ID) return false;
  return true;
}

function ohlcCandlesForIndicators(data: SnowballNetChartResponse) {
  return sortedCandles(data).map((candle) => ({
    time: candle.time,
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
    volume: candle.volume,
  }));
}

function toUnixSeconds(value: string | null | undefined): number | null {
  if (!value) return null;
  const ms = new Date(value).getTime();
  return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
}

function candleBucketRange(
  data: SnowballNetChartResponse
): CandleBucketRange | null {
  const step = data.window.granularity_seconds;
  const since = toUnixSeconds(data.window.since);
  const until = toUnixSeconds(data.window.until);
  if (!step || since == null || until == null || since > until) return null;

  return {
    step,
    since,
    until,
  };
}

function sortedCandles(data: SnowballNetChartResponse) {
  return [...data.candles].sort((a, b) => a.time - b.time);
}

function noDataThresholdSeconds(step: number): number {
  return step >= 86400 ? step : step * MIN_NO_DATA_BUCKETS;
}

function buildContinuousCandleData(
  data: SnowballNetChartResponse
): Array<CandlestickData<Time> | WhitespaceData<Time>> {
  const bucketRange = candleBucketRange(data);
  if (!bucketRange) {
    return data.candles.map(
      (candle) =>
        ({
          time: candle.time as Time,
          open: candle.open,
          high: candle.high,
          low: candle.low,
          close: candle.close,
        }) as CandlestickData<Time>
    );
  }

  const points = new Map<
    number,
    CandlestickData<Time> | WhitespaceData<Time>
  >();
  const addWhitespace = (time: number) => {
    if (!points.has(time)) {
      points.set(time, { time: time as Time });
    }
  };
  const addWhitespaceRange = (from: number, to: number) => {
    if (to <= from) return;
    for (let time = from; time < to; time += bucketRange.step) {
      addWhitespace(time);
    }
    addWhitespace(to);
  };

  addWhitespace(bucketRange.since);
  addWhitespace(bucketRange.until);
  for (const region of buildNoDataRegions(data)) {
    addWhitespaceRange(region.from, region.to);
  }
  for (const candle of sortedCandles(data)) {
    points.set(candle.time, {
      time: candle.time as Time,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    });
  }

  return [...points.values()].sort((a, b) => Number(a.time) - Number(b.time));
}

function buildNoDataRegions(data: SnowballNetChartResponse): NoDataRegion[] {
  const bucketRange = candleBucketRange(data);
  if (!bucketRange) return [];

  const candles = sortedCandles(data);
  const threshold = noDataThresholdSeconds(bucketRange.step);
  const regions: NoDataRegion[] = [];

  const addRegion = (from: number, to: number) => {
    if (to - from >= threshold) {
      regions.push({
        from,
        to,
      });
    }
  };

  if (candles.length === 0) {
    addRegion(bucketRange.since, bucketRange.until);
    return regions;
  }

  addRegion(bucketRange.since, candles[0].time);
  for (let index = 1; index < candles.length; index += 1) {
    const previous = candles[index - 1];
    const current = candles[index];
    const expectedNext = previous.time + bucketRange.step;
    addRegion(expectedNext, current.time);
  }
  addRegion(
    candles[candles.length - 1].time + bucketRange.step,
    bucketRange.until
  );
  return regions;
}

function releaseProgrammaticRangeFlag(ref: MutableRefObject<boolean>) {
  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => {
      ref.current = false;
    });
  });
}

class NoDataRegionsRenderer implements IPrimitivePaneRenderer {
  constructor(
    private readonly regions: NoDataRegion[],
    private readonly xForTime: (time: number) => number | null,
    private readonly style: NoDataRegionStyle
  ) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const ratio = scope.horizontalPixelRatio;
      const verticalRatio = scope.verticalPixelRatio;
      const height = scope.bitmapSize.height;
      const minLabelWidth = 74 * ratio;

      for (const region of this.regions) {
        const x1 = this.xForTime(region.from);
        const x2 = this.xForTime(region.to);
        if (x1 == null || x2 == null) continue;

        const left = Math.round(Math.min(x1, x2) * ratio);
        const right = Math.round(Math.max(x1, x2) * ratio);
        const width = Math.max(1, right - left);

        ctx.fillStyle = this.style.fill;
        ctx.fillRect(left, 0, width, height);

        ctx.strokeStyle = this.style.stroke;
        ctx.lineWidth = Math.max(1, ratio);
        ctx.setLineDash([4 * ratio, 4 * ratio]);
        ctx.beginPath();
        ctx.moveTo(left + 0.5 * ratio, 0);
        ctx.lineTo(left + 0.5 * ratio, height);
        ctx.moveTo(right - 0.5 * ratio, 0);
        ctx.lineTo(right - 0.5 * ratio, height);
        ctx.stroke();
        ctx.setLineDash([]);

        if (width < minLabelWidth) continue;
        const fontSize = Math.round(11 * ratio);
        ctx.font = `600 ${fontSize}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = this.style.text;
        ctx.fillText(this.style.label, left + width / 2, height * 0.5);

        const subFont = Math.round(9 * ratio);
        ctx.font = `500 ${subFont}px sans-serif`;
        ctx.fillText(
          this.style.subLabel,
          left + width / 2,
          height * 0.5 + 15 * verticalRatio
        );
      }
    });
  }
}

class NoDataRegionsPaneView implements IPrimitivePaneView {
  constructor(private readonly source: NoDataRegionsOverlay) {}

  zOrder(): 'bottom' {
    return 'bottom';
  }

  renderer(): IPrimitivePaneRenderer | null {
    const param = this.source.getAttachedParams();
    const regions = this.source.getRegions();
    if (!param || regions.length === 0) return null;

    const timeScale = param.chart.timeScale();
    return new NoDataRegionsRenderer(
      regions,
      (time) => timeScale.timeToCoordinate(time as Time),
      this.source.getStyle()
    );
  }
}

class NoDataRegionsOverlay implements ISeriesPrimitive<Time> {
  private regions: NoDataRegion[] = [];
  private readonly views = [new NoDataRegionsPaneView(this)];
  private param: SeriesAttachedParameter<Time> | null = null;
  private rangeChangeHandler: (() => void) | null = null;

  constructor(private style: NoDataRegionStyle) {}

  attached(param: SeriesAttachedParameter<Time>): void {
    this.param = param;
    this.rangeChangeHandler = () => {
      if (this.regions.length > 0) {
        this.param?.requestUpdate();
      }
    };
    param.chart
      .timeScale()
      .subscribeVisibleLogicalRangeChange(this.rangeChangeHandler);
  }

  detached(): void {
    if (this.rangeChangeHandler && this.param) {
      this.param.chart
        .timeScale()
        .unsubscribeVisibleLogicalRangeChange(this.rangeChangeHandler);
    }
    this.rangeChangeHandler = null;
    this.param = null;
  }

  setRegions(regions: NoDataRegion[]): void {
    this.regions = regions;
    this.param?.requestUpdate();
  }

  clear(): void {
    this.regions = [];
    this.param?.requestUpdate();
  }

  getAttachedParams(): SeriesAttachedParameter<Time> | null {
    return this.param;
  }

  getRegions(): NoDataRegion[] {
    return this.regions;
  }

  getStyle(): NoDataRegionStyle {
    return this.style;
  }

  setStyle(style: NoDataRegionStyle): void {
    this.style = style;
    this.param?.requestUpdate();
  }

  updateAllViews(): void {
    // Pane view reads current regions on each render.
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }
}

export function SnowballNetStrategyTab({
  taskId,
  taskType,
  executionRunId,
  instrument,
  taskStartTime,
  taskEndTime,
  enableRealTimeUpdates = false,
  timezone = 'UTC',
  lossCutEvents,
  showLossCutMarkers,
}: SnowballNetStrategyTabProps) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const { t } = useTranslation(['common', 'strategy']);
  const noDataRegionStyle = useMemo<NoDataRegionStyle>(
    () => ({
      fill: isDark ? 'rgba(148, 163, 184, 0.12)' : 'rgba(100, 116, 139, 0.1)',
      stroke: isDark
        ? 'rgba(148, 163, 184, 0.34)'
        : 'rgba(100, 116, 139, 0.28)',
      text: isDark ? 'rgba(226, 232, 240, 0.72)' : 'rgba(71, 85, 105, 0.72)',
      label: t('strategy:snowballNet.chart.noData'),
      subLabel: t('strategy:snowballNet.chart.marketClosed'),
    }),
    [isDark, t]
  );
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const priceLineRefs = useRef<Map<string, ISeriesApi<'Line'>>>(new Map());
  const marginLineRef = useRef<ISeriesApi<'Line'> | null>(null);
  const marginAxisLabelRef = useRef<IPriceLine | null>(null);
  const priceAxisLabelRefs = useRef<Map<string, IPriceLine>>(new Map());
  const markersRef = useRef<ReturnType<
    typeof createSeriesMarkers<Time>
  > | null>(null);
  const observerRef = useRef<ResizeObserver | null>(null);
  const sequenceLineRef = useRef<SequencePositionLine | null>(null);
  const noDataRegionsRef = useRef<NoDataRegionsOverlay | null>(null);
  const programmaticRangeRef = useRef(false);
  const programmaticRangeTargetRef = useRef<ChartTimeRange | null>(null);
  const programmaticRangeSuppressUntilRef = useRef(0);
  const visibleRangeRef = useRef<ChartTimeRange | null>(null);
  const loadedWindowRef = useRef<LoadedChartWindow | null>(null);
  const backtestBoundsRef = useRef<ChartTimeRange | null>(null);
  const lastRequestedRangeRef = useRef<ChartTimeRange | null>(null);
  const rangeFetchTimerRef = useRef<number | null>(null);
  const forceWindowRangeRef = useRef(true);
  const ohlcChartHeightRef = useRef(DEFAULT_OHLC_CHART_HEIGHT);
  const chartDragKeyRef = useRef<SnowballNetChartKey | null>(null);
  const lastChartDragTargetRef = useRef<SnowballNetChartKey | null>(null);
  const { applyOverlays: applyOhlcOverlays, clear: clearOhlcOverlays } =
    useOhlcChartOverlays(containerRef);
  const [rangePreset, setRangePreset] =
    useState<SnowballNetRangePreset>('follow');
  const [queryRangePreset, setQueryRangePreset] =
    useState<SnowballNetRangePreset>('follow');
  const [granularitySelection, setGranularitySelection] =
    useState<SnowballNetGranularitySelection>(DEFAULT_GRANULARITY_SELECTION);
  const [appliedGranularitySelection, setAppliedGranularitySelection] =
    useState<SnowballNetGranularitySelection>(DEFAULT_GRANULARITY_SELECTION);
  const [customSince, setCustomSince] = useState('');
  const [customUntil, setCustomUntil] = useState('');
  const [appliedRange, setAppliedRange] = useState<AppliedDateRange | null>(
    null
  );
  const [rangeNowMs, setRangeNowMs] = useState(() => Date.now());
  const [rangeReferenceMs, setRangeReferenceMs] = useState(
    () => millisFromIso(taskEndTime) ?? Date.now()
  );
  const [follow, setFollow] = useState(true);
  const [mergeMarkers, setMergeMarkers] = useState(true);
  const [refreshSeconds, setRefreshSeconds] = useState<number>(15);
  const [appliedRefreshSeconds, setAppliedRefreshSeconds] =
    useState<number>(15);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [chartSettings, setChartSettings] = useState<SnowballNetChartSettings>(
    () =>
      readStoredValue(
        SNOWBALL_NET_CHART_SETTINGS_KEY,
        snowballNetChartSettingsSchema,
        DEFAULT_CHART_SETTINGS
      )
  );
  const [chartOrder, setChartOrder] = useState<SnowballNetChartKey[]>(() =>
    normalizeSnowballNetChartOrder(
      readStoredValue(
        SNOWBALL_NET_CHART_ORDER_KEY,
        snowballNetChartOrderSchema,
        [...SNOWBALL_NET_CHART_KEYS]
      )
    )
  );
  const [ohlcChartHeight, setOhlcChartHeight] = useState(() =>
    readStoredValue(
      OHLC_CHART_HEIGHT_KEY,
      ohlcChartHeightSchema,
      DEFAULT_OHLC_CHART_HEIGHT
    )
  );
  const [viewRange, setViewRange] = useState<ChartTimeRange | null>(null);
  const [dragChartKey, setDragChartKey] = useState<SnowballNetChartKey | null>(
    null
  );
  const [dragOverChartKey, setDragOverChartKey] =
    useState<SnowballNetChartKey | null>(null);

  useEffect(() => {
    ohlcChartHeightRef.current = ohlcChartHeight;
    chartRef.current?.applyOptions({ height: ohlcChartHeight });
  }, [ohlcChartHeight]);

  const updateChartSettings = useCallback(
    (
      updater: (current: SnowballNetChartSettings) => SnowballNetChartSettings
    ) => {
      setChartSettings((current) => {
        const next = updater(current);
        writeStoredValue(SNOWBALL_NET_CHART_SETTINGS_KEY, next);
        return next;
      });
    },
    []
  );

  const updateChartOrder = useCallback((keys: readonly string[]) => {
    const next = normalizeSnowballNetChartOrder(keys);
    setChartOrder(next);
    writeStoredValue(SNOWBALL_NET_CHART_ORDER_KEY, next);
  }, []);

  const resetChartOrder = useCallback(() => {
    const next = [...SNOWBALL_NET_CHART_KEYS];
    setChartOrder(next);
    removeStoredValue(SNOWBALL_NET_CHART_ORDER_KEY);
  }, []);

  const moveChart = useCallback(
    (sourceKey: SnowballNetChartKey, targetKey: SnowballNetChartKey) => {
      if (
        sourceKey === targetKey ||
        sourceKey === 'ohlc' ||
        targetKey === 'ohlc'
      ) {
        return;
      }
      const fromIndex = chartOrder.indexOf(sourceKey);
      const toIndex = chartOrder.indexOf(targetKey);
      if (fromIndex < 0 || toIndex < 0) return;
      const next = [...chartOrder];
      next.splice(fromIndex, 1);
      next.splice(toIndex, 0, sourceKey);
      updateChartOrder(next);
    },
    [chartOrder, updateChartOrder]
  );

  const handleChartDragStart = useCallback(
    (event: ReactDragEvent, key: SnowballNetChartKey) => {
      chartDragKeyRef.current = key;
      lastChartDragTargetRef.current = null;
      setDragChartKey(key);
      setDragOverChartKey(null);
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', key);
    },
    []
  );

  const handleChartDragOver = useCallback(
    (event: ReactDragEvent, targetKey: SnowballNetChartKey) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      setDragOverChartKey(targetKey);

      const sourceKey = chartDragKeyRef.current;
      if (
        sourceKey &&
        sourceKey !== targetKey &&
        lastChartDragTargetRef.current !== targetKey
      ) {
        moveChart(sourceKey, targetKey);
        lastChartDragTargetRef.current = targetKey;
      }
    },
    [moveChart]
  );

  const handleChartDrop = useCallback(
    (event: ReactDragEvent, targetKey: SnowballNetChartKey) => {
      event.preventDefault();
      const sourceKey = chartDragKeyRef.current;
      if (sourceKey && sourceKey !== targetKey) {
        moveChart(sourceKey, targetKey);
      }
      chartDragKeyRef.current = null;
      lastChartDragTargetRef.current = null;
      setDragChartKey(null);
      setDragOverChartKey(null);
    },
    [moveChart]
  );

  const handleChartDragEnd = useCallback(() => {
    chartDragKeyRef.current = null;
    lastChartDragTargetRef.current = null;
    setDragChartKey(null);
    setDragOverChartKey(null);
  }, []);

  const updateOhlcChartHeight = useCallback(
    (height: number, persist = true) => {
      const next = clampOhlcChartHeight(height);
      ohlcChartHeightRef.current = next;
      chartRef.current?.applyOptions({ height: next });
      setOhlcChartHeight((current) => (current === next ? current : next));
      if (persist) {
        writeStoredValue(OHLC_CHART_HEIGHT_KEY, next);
      }
    },
    []
  );

  const handleOhlcResizePointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (event.button !== 0) return;
      event.preventDefault();
      const startY = event.clientY;
      const startHeight = ohlcChartHeightRef.current;
      const previousCursor = document.body.style.cursor;
      const previousUserSelect = document.body.style.userSelect;
      document.body.style.cursor = 'row-resize';
      document.body.style.userSelect = 'none';

      const handlePointerMove = (moveEvent: PointerEvent) => {
        updateOhlcChartHeight(startHeight + moveEvent.clientY - startY, false);
      };

      const finishResize = () => {
        window.removeEventListener('pointermove', handlePointerMove);
        window.removeEventListener('pointerup', finishResize);
        window.removeEventListener('pointercancel', finishResize);
        document.body.style.cursor = previousCursor;
        document.body.style.userSelect = previousUserSelect;
        writeStoredValue(OHLC_CHART_HEIGHT_KEY, ohlcChartHeightRef.current);
      };

      window.addEventListener('pointermove', handlePointerMove);
      window.addEventListener('pointerup', finishResize, { once: true });
      window.addEventListener('pointercancel', finishResize, { once: true });
    },
    [updateOhlcChartHeight]
  );

  const handleOhlcResizeKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLDivElement>) => {
      const step = event.shiftKey
        ? OHLC_CHART_RESIZE_STEP * 4
        : OHLC_CHART_RESIZE_STEP;
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        updateOhlcChartHeight(ohlcChartHeightRef.current - step);
      } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        updateOhlcChartHeight(ohlcChartHeightRef.current + step);
      } else if (event.key === 'Home') {
        event.preventDefault();
        updateOhlcChartHeight(MIN_OHLC_CHART_HEIGHT);
      } else if (event.key === 'End') {
        event.preventDefault();
        updateOhlcChartHeight(DEFAULT_OHLC_CHART_HEIGHT);
      }
    },
    [updateOhlcChartHeight]
  );

  const taskRange = useMemo(() => {
    const startMs = millisFromIso(taskStartTime);
    const endMs = millisFromIso(taskEndTime) ?? rangeNowMs;
    if (startMs == null || endMs <= startMs) return null;
    return { startMs, endMs };
  }, [rangeNowMs, taskEndTime, taskStartTime]);

  const backtestDateBounds = useMemo<AppliedDateRange | null>(() => {
    if (taskType !== 'backtest') return null;
    const sinceMs = millisFromIso(taskStartTime);
    const untilMs = millisFromIso(taskEndTime);
    if (sinceMs == null || untilMs == null || untilMs <= sinceMs) return null;
    return { sinceMs, untilMs };
  }, [taskEndTime, taskStartTime, taskType]);

  const backtestBounds = useMemo<ChartTimeRange | null>(() => {
    if (!backtestDateBounds) return null;
    return {
      from: Math.floor(backtestDateBounds.sinceMs / 1000),
      to: Math.ceil(backtestDateBounds.untilMs / 1000),
    };
  }, [backtestDateBounds]);

  useEffect(() => {
    backtestBoundsRef.current = backtestBounds;
  }, [backtestBounds]);

  const presetReferenceMs = useMemo(() => {
    if (!taskRange) return rangeReferenceMs;
    return Math.min(
      taskRange.endMs,
      Math.max(taskRange.startMs, rangeReferenceMs)
    );
  }, [rangeReferenceMs, taskRange]);

  const customDraftRange = useMemo(
    () => customRangeFromControls(customSince, customUntil),
    [customSince, customUntil]
  );

  const selectedRange = useMemo(() => {
    if (queryRangePreset === 'follow') {
      return null;
    }
    return clampDateRangeToBounds(appliedRange, backtestDateBounds);
  }, [appliedRange, backtestDateBounds, queryRangePreset]);

  const draftSelectedRange = useMemo(() => {
    const clampDraft = (range: AppliedDateRange | null) =>
      clampDateRangeToBounds(range, backtestDateBounds);

    if (rangePreset === 'follow') {
      return null;
    }

    if (rangePreset === 'custom') {
      return clampDraft(customDraftRange);
    }

    if (!taskRange) return null;
    if (rangePreset === 'full') {
      return clampDraft({
        sinceMs: taskRange.startMs,
        untilMs: taskRange.endMs,
      });
    }

    const seconds = rangePresetSeconds(rangePreset);
    if (seconds == null) {
      return clampDraft({
        sinceMs: taskRange.startMs,
        untilMs: taskRange.endMs,
      });
    }
    const windowMs = seconds * 1000;
    return clampDraft({
      sinceMs: Math.max(taskRange.startMs, presetReferenceMs - windowMs),
      untilMs: presetReferenceMs,
    });
  }, [
    backtestDateBounds,
    customDraftRange,
    presetReferenceMs,
    rangePreset,
    taskRange,
  ]);

  const requestedRangeSeconds = useMemo(() => {
    if (follow) return null;
    if (viewRange) return Math.max(MINUTE, viewRange.to - viewRange.from);
    if (!selectedRange) return null;
    return Math.max(
      MINUTE,
      Math.floor((selectedRange.untilMs - selectedRange.sinceMs) / 1000)
    );
  }, [follow, selectedRange, viewRange]);

  const draftRequestedRangeSeconds = useMemo(() => {
    if (rangePreset === 'follow') return null;
    if (!draftSelectedRange) return null;
    return Math.max(
      MINUTE,
      Math.floor(
        (draftSelectedRange.untilMs - draftSelectedRange.sinceMs) / 1000
      )
    );
  }, [draftSelectedRange, rangePreset]);

  const autoGranularity = useMemo(() => {
    if (follow) return DEFAULT_GRANULARITY;
    if (viewRange) {
      return granularityForRangeSeconds(
        Math.max(MINUTE, Math.floor(viewRange.to - viewRange.from))
      );
    }
    if (!selectedRange) return DEFAULT_GRANULARITY;
    const seconds = Math.max(
      MINUTE,
      Math.floor((selectedRange.untilMs - selectedRange.sinceMs) / 1000)
    );
    return granularityForRangeSeconds(seconds);
  }, [follow, selectedRange, viewRange]);

  const draftAutoGranularity = useMemo(() => {
    if (rangePreset === 'follow') return DEFAULT_GRANULARITY;
    if (!draftSelectedRange) return DEFAULT_GRANULARITY;
    const seconds = Math.max(
      MINUTE,
      Math.floor(
        (draftSelectedRange.untilMs - draftSelectedRange.sinceMs) / 1000
      )
    );
    return granularityForRangeSeconds(seconds);
  }, [draftSelectedRange, rangePreset]);

  const selectedGranularityCandidate =
    appliedGranularitySelection === 'Auto'
      ? autoGranularity
      : appliedGranularitySelection;
  const selectedGranularity = constrainSnowballNetGranularityForRange(
    selectedGranularityCandidate,
    requestedRangeSeconds
  );
  const draftDisplayedGranularity =
    granularitySelection === 'Auto'
      ? 'Auto'
      : constrainSnowballNetGranularityForRange(
          granularitySelection,
          draftRequestedRangeSeconds
        );
  const displayedGranularitySelection = draftDisplayedGranularity;

  const clearPendingRangeLoad = useCallback(() => {
    if (rangeFetchTimerRef.current !== null) {
      window.clearTimeout(rangeFetchTimerRef.current);
      rangeFetchTimerRef.current = null;
    }
  }, []);

  const markProgrammaticRangeChange = useCallback((range?: ChartTimeRange) => {
    programmaticRangeRef.current = true;
    programmaticRangeTargetRef.current = range ?? null;
    programmaticRangeSuppressUntilRef.current =
      Date.now() + PROGRAMMATIC_RANGE_SUPPRESS_MS;
  }, []);

  const resetAppliedWindowState = useCallback(() => {
    clearPendingRangeLoad();
    forceWindowRangeRef.current = true;
    visibleRangeRef.current = null;
    lastRequestedRangeRef.current = null;
  }, [clearPendingRangeLoad]);

  const handleRangePresetChange = useCallback(
    (value: SnowballNetRangePreset) => {
      clearPendingRangeLoad();
      setRangePreset(value);
      if (value === 'custom' && !customSince && !customUntil && taskRange) {
        setCustomSince(
          formatDateTimeLocal(new Date(taskRange.startMs).toISOString())
        );
        setCustomUntil(
          formatDateTimeLocal(new Date(taskRange.endMs).toISOString())
        );
      }
    },
    [clearPendingRangeLoad, customSince, customUntil, taskRange]
  );

  const handleCustomSinceChange = useCallback(
    (value: string) => {
      clearPendingRangeLoad();
      setRangePreset('custom');
      setCustomSince(value);
    },
    [clearPendingRangeLoad]
  );

  const handleCustomUntilChange = useCallback(
    (value: string) => {
      clearPendingRangeLoad();
      setRangePreset('custom');
      setCustomUntil(value);
    },
    [clearPendingRangeLoad]
  );

  const handleApplyChartControls = useCallback(() => {
    if (rangePreset !== 'follow' && !draftSelectedRange) return;
    const boundedDraftRange =
      rangePreset === 'follow'
        ? null
        : clampDateRangeToBounds(draftSelectedRange, backtestDateBounds);
    if (rangePreset !== 'follow' && !boundedDraftRange) return;
    resetAppliedWindowState();
    const nextGranularitySelection =
      granularitySelection === 'Auto'
        ? 'Auto'
        : constrainSnowballNetGranularityForRange(
            granularitySelection,
            draftRequestedRangeSeconds
          );
    setGranularitySelection(nextGranularitySelection);
    setAppliedGranularitySelection(nextGranularitySelection);
    setAppliedRefreshSeconds(refreshSeconds);
    setQueryRangePreset(rangePreset);
    if (rangePreset === 'follow') {
      setFollow(true);
      setAppliedRange(null);
      setViewRange(null);
      return;
    }
    if (!taskEndTime) {
      setRangeNowMs(Date.now());
    }
    setFollow(false);
    setAppliedRange(boundedDraftRange);
    if (boundedDraftRange && rangePreset === 'custom') {
      setCustomSince(
        formatDateTimeLocal(new Date(boundedDraftRange.sinceMs).toISOString())
      );
      setCustomUntil(
        formatDateTimeLocal(new Date(boundedDraftRange.untilMs).toISOString())
      );
    }
    setViewRange(null);
  }, [
    backtestDateBounds,
    draftSelectedRange,
    draftRequestedRangeSeconds,
    granularitySelection,
    rangePreset,
    refreshSeconds,
    resetAppliedWindowState,
    taskEndTime,
  ]);

  useEffect(() => {
    if (
      !follow ||
      taskEndTime ||
      !enableRealTimeUpdates ||
      appliedRefreshSeconds <= 0
    ) {
      return;
    }
    const id = window.setInterval(
      () => setRangeNowMs(Date.now()),
      appliedRefreshSeconds * 1000
    );
    return () => window.clearInterval(id);
  }, [appliedRefreshSeconds, enableRealTimeUpdates, follow, taskEndTime]);

  const queryParams = useMemo(() => {
    if (follow) {
      return {
        granularity: selectedGranularity,
        before_bars: DEFAULT_SIDE_BARS,
        after_bars: DEFAULT_SIDE_BARS,
        follow: 'true',
        merge_markers: mergeMarkers ? 'true' : 'false',
      };
    }

    if (viewRange) {
      const pad = Math.max(
        60,
        Math.floor((viewRange.to - viewRange.from) * 0.5)
      );
      const requestRange = intersectChartRangeWithBounds(
        {
          from: Math.max(0, viewRange.from - pad),
          to: viewRange.to + pad,
        },
        backtestBounds
      );
      if (!requestRange) {
        return {
          granularity: selectedGranularity,
          before_bars: DEFAULT_SIDE_BARS,
          after_bars: DEFAULT_SIDE_BARS,
          follow: 'false',
          merge_markers: mergeMarkers ? 'true' : 'false',
        };
      }
      return {
        granularity: selectedGranularity,
        since: isoFromSeconds(requestRange.from),
        until: isoFromSeconds(requestRange.to),
        follow: 'false',
        merge_markers: mergeMarkers ? 'true' : 'false',
      };
    }

    if (!selectedRange) {
      return {
        granularity: selectedGranularity,
        before_bars: DEFAULT_SIDE_BARS,
        after_bars: DEFAULT_SIDE_BARS,
        follow: 'false',
        merge_markers: mergeMarkers ? 'true' : 'false',
      };
    }

    const requestRange = intersectChartRangeWithBounds(
      {
        from: selectedRange.sinceMs / 1000,
        to: selectedRange.untilMs / 1000,
      },
      backtestBounds
    );
    if (!requestRange) {
      return {
        granularity: selectedGranularity,
        before_bars: DEFAULT_SIDE_BARS,
        after_bars: DEFAULT_SIDE_BARS,
        follow: 'false',
        merge_markers: mergeMarkers ? 'true' : 'false',
      };
    }

    return {
      granularity: selectedGranularity,
      since: isoFromSeconds(requestRange.from),
      until: isoFromSeconds(requestRange.to),
      follow: 'false',
      merge_markers: mergeMarkers ? 'true' : 'false',
    };
  }, [
    backtestBounds,
    follow,
    mergeMarkers,
    selectedGranularity,
    selectedRange,
    viewRange,
  ]);

  const chartQuery = useSnowballNetChart({
    taskId,
    taskType,
    executionRunId,
    params: queryParams,
    enabled: Boolean(taskId),
    refetchInterval:
      follow && enableRealTimeUpdates && appliedRefreshSeconds > 0
        ? appliedRefreshSeconds * 1000
        : false,
  });

  const data = chartQuery.data ?? null;
  const latestDataTimestamp =
    typeof data?.current.timestamp === 'string'
      ? data.current.timestamp
      : data?.window.center;
  const latestDataReferenceMs = millisFromIso(latestDataTimestamp);

  useEffect(() => {
    if (latestDataReferenceMs == null) return undefined;
    const id = window.setTimeout(() => {
      setRangeReferenceMs(latestDataReferenceMs);
    }, 0);
    return () => window.clearTimeout(id);
  }, [latestDataReferenceMs]);

  const chartOrderItems = useMemo(
    () =>
      chartOrder
        .filter((key) => key !== 'ohlc')
        .map((key) => ({
          key,
          label: snowballNetChartTitle(key, t, {
            instrument: data?.instrument ?? instrument,
            pnlCurrency: data ? pnlCurrencyCode(data) : null,
            priceCurrency: quoteCurrencyFromInstrument(
              data?.instrument ?? instrument
            ),
          }),
          color: SNOWBALL_NET_CHART_COLORS[key],
        })),
    [chartOrder, data, instrument, t]
  );

  useEffect(() => {
    lastRequestedRangeRef.current = null;
  }, [selectedGranularity]);

  const scheduleVisibleRangeLoad = useCallback(
    (range: ChartTimeRange) => {
      const bounds = backtestBoundsRef.current;
      const nextRange = clampChartViewportRangeToBounds(range, bounds);
      if (!nextRange) return;

      const toleranceSeconds = loadedWindowRef.current?.step ?? 1;
      if (bounds && !rangesClose(range, nextRange, toleranceSeconds)) {
        markProgrammaticRangeChange(nextRange);
        chartRef.current?.timeScale().setVisibleRange({
          from: nextRange.from as Time,
          to: nextRange.to as Time,
        });
        releaseProgrammaticRangeFlag(programmaticRangeRef);
      }

      visibleRangeRef.current = nextRange;

      if (rangeFetchTimerRef.current !== null) {
        window.clearTimeout(rangeFetchTimerRef.current);
      }
      rangeFetchTimerRef.current = window.setTimeout(() => {
        rangeFetchTimerRef.current = null;
        const currentRange = visibleRangeRef.current;
        if (!currentRange) return;

        const loaded = loadedWindowRef.current;
        const toleranceSeconds = loaded?.step ?? 1;
        if (
          loaded &&
          rangesClose(
            currentRange,
            { from: loaded.from, to: loaded.to },
            toleranceSeconds
          )
        ) {
          return;
        }
        if (
          rangesClose(
            currentRange,
            lastRequestedRangeRef.current,
            toleranceSeconds
          )
        ) {
          return;
        }
        forceWindowRangeRef.current = false;
        lastRequestedRangeRef.current = currentRange;
        setCustomSince(formatDateTimeLocal(isoFromSeconds(currentRange.from)));
        setCustomUntil(formatDateTimeLocal(isoFromSeconds(currentRange.to)));
        setAppliedRange({
          sinceMs: currentRange.from * 1000,
          untilMs: currentRange.to * 1000,
        });
        setRangePreset('custom');
        setQueryRangePreset('custom');
        setFollow(false);
        setViewRange(currentRange);
      }, SCROLL_FETCH_DEBOUNCE_MS);
    },
    [markProgrammaticRangeChange]
  );

  const destroyChart = useCallback(() => {
    if (rangeFetchTimerRef.current !== null) {
      window.clearTimeout(rangeFetchTimerRef.current);
      rangeFetchTimerRef.current = null;
    }
    observerRef.current?.disconnect();
    observerRef.current = null;
    clearOhlcOverlays();
    sequenceLineRef.current?.clear();
    sequenceLineRef.current = null;
    noDataRegionsRef.current?.clear();
    if (noDataRegionsRef.current && candleSeriesRef.current) {
      candleSeriesRef.current.detachPrimitive(noDataRegionsRef.current);
    }
    noDataRegionsRef.current = null;
    markersRef.current?.detach();
    markersRef.current = null;
    for (const label of priceAxisLabelRefs.current.values()) {
      candleSeriesRef.current?.removePriceLine(label);
    }
    priceAxisLabelRefs.current.clear();
    priceLineRefs.current.clear();
    if (marginAxisLabelRef.current && marginLineRef.current) {
      marginLineRef.current.removePriceLine(marginAxisLabelRef.current);
      marginAxisLabelRef.current = null;
    }
    if (marginLineRef.current) {
      chartRef.current?.removeSeries(marginLineRef.current);
      marginLineRef.current = null;
    }
    visibleRangeRef.current = null;
    loadedWindowRef.current = null;
    lastRequestedRangeRef.current = null;
    chartRef.current?.remove();
    chartRef.current = null;
    candleSeriesRef.current = null;
  }, [clearOhlcOverlays]);

  const updatePriceAxisLabels = useCallback(
    (lines: SnowballNetLineSeries[]) => {
      const series = candleSeriesRef.current;
      if (!series) return;

      const specs = buildPriceAxisLabelSpecs(lines, t);
      const activeIds = new Set(specs.map((spec) => spec.id));
      for (const [id, label] of priceAxisLabelRefs.current.entries()) {
        if (!activeIds.has(id)) {
          series.removePriceLine(label);
          priceAxisLabelRefs.current.delete(id);
        }
      }

      for (const spec of specs) {
        const options = {
          price: spec.price,
          color: spec.color,
          lineWidth: 1 as const,
          lineStyle: spec.lineStyle,
          lineVisible: false,
          axisLabelVisible: true,
          title: spec.title,
          axisLabelColor: spec.color,
          axisLabelTextColor: '#ffffff',
        };
        const existing = priceAxisLabelRefs.current.get(spec.id);
        if (existing) {
          existing.applyOptions(options);
        } else {
          priceAxisLabelRefs.current.set(
            spec.id,
            series.createPriceLine(options)
          );
        }
      }
    },
    [t]
  );

  const updateMarginAxisLabel = useCallback(
    (line: SnowballNetLineSeries | null) => {
      const series = marginLineRef.current;
      if (!series || !line) {
        if (series && marginAxisLabelRef.current) {
          series.removePriceLine(marginAxisLabelRef.current);
        }
        marginAxisLabelRef.current = null;
        return;
      }

      const point = latestLinePoint(line);
      if (!point) {
        if (marginAxisLabelRef.current) {
          series.removePriceLine(marginAxisLabelRef.current);
          marginAxisLabelRef.current = null;
        }
        return;
      }

      const options = {
        price: point.value,
        color: line.color,
        lineWidth: 1 as const,
        lineStyle: lightweightLineStyle(line),
        lineVisible: false,
        axisLabelVisible: true,
        title: lineLabel(line, t),
        axisLabelColor: line.color,
        axisLabelTextColor: '#ffffff',
      };
      if (marginAxisLabelRef.current) {
        marginAxisLabelRef.current.applyOptions(options);
      } else {
        marginAxisLabelRef.current = series.createPriceLine(options);
      }
    },
    [t]
  );

  useEffect(() => destroyChart, [destroyChart]);

  useEffect(() => {
    destroyChart();
  }, [destroyChart, isDark]);

  useEffect(() => {
    if (!chartSettings.charts.ohlc) {
      destroyChart();
    }
  }, [chartSettings.charts.ohlc, destroyChart]);

  useEffect(() => {
    if (!chartSettings.charts.ohlc) return;
    const host = containerRef.current;
    if (!data) {
      destroyChart();
      return;
    }
    if (!host) return;

    if (follow) {
      markProgrammaticRangeChange();
    }

    if (!chartRef.current) {
      const { upColor, downColor } = getCandleColors();
      const chart = createChart(host, {
        height: ohlcChartHeightRef.current,
        width: Math.max(1, measureContainerWidth(host)),
        layout: {
          background: { color: isDark ? '#131722' : '#ffffff' },
          textColor: isDark ? '#d1d4dc' : '#334155',
        },
        grid: {
          vertLines: { visible: false },
          horzLines: { color: isDark ? '#2a2e39' : '#e2e8f0' },
        },
        handleScroll: { vertTouchDrag: false },
        timeScale: {
          visible: true,
          borderVisible: true,
          borderColor: isDark ? '#2a2e39' : '#cbd5e1',
          timeVisible: true,
          secondsVisible: false,
          // Native labels are intentionally suppressed because
          // AdaptiveTimeScale renders the axis; reserve its pane explicitly.
          minimumHeight: 30,
          tickMarkFormatter: createSuppressedTickMarkFormatter(),
        },
        localization: {
          timeFormatter: createTooltipTimeFormatter({ timezone }),
        },
        rightPriceScale: { borderColor: isDark ? '#2a2e39' : '#cbd5e1' },
        leftPriceScale: {
          visible: false,
          borderColor: isDark ? '#2a2e39' : '#cbd5e1',
        },
      });
      const candles = chart.addSeries(CandlestickSeries, {
        upColor,
        downColor,
        wickUpColor: upColor,
        wickDownColor: downColor,
        borderUpColor: upColor,
        borderDownColor: downColor,
      });
      candles.attachPrimitive(
        new AdaptiveTimeScale(
          { timezone },
          isDark ? '#d1d4dc' : '#334155',
          isDark ? '#2a2e39' : '#e2e8f0'
        )
      );
      const noDataRegions = new NoDataRegionsOverlay(noDataRegionStyle);
      candles.attachPrimitive(noDataRegions);
      const sequenceLine = new SequencePositionLine({
        maxExtrapolation: Infinity,
      });
      candles.attachPrimitive(sequenceLine);

      chartRef.current = chart;
      candleSeriesRef.current = candles;
      noDataRegionsRef.current = noDataRegions;
      sequenceLineRef.current = sequenceLine;
      markersRef.current = createSeriesMarkers(candles, []);

      chart.timeScale().subscribeVisibleLogicalRangeChange((logicalRange) => {
        const normalizedRange = visibleChartRangeIncludingWhitespace({
          chart,
          series: candles,
          logicalRange,
          stepSeconds:
            loadedWindowRef.current?.step ?? data.window.granularity_seconds,
        });
        if (!normalizedRange) return;
        const programmaticTarget = programmaticRangeTargetRef.current;
        const toleranceSeconds = loadedWindowRef.current?.step ?? 1;
        if (
          programmaticTarget &&
          rangesClose(normalizedRange, programmaticTarget, toleranceSeconds)
        ) {
          programmaticRangeTargetRef.current = null;
          return;
        }
        if (
          programmaticRangeRef.current ||
          Date.now() < programmaticRangeSuppressUntilRef.current
        ) {
          return;
        }
        scheduleVisibleRangeLoad(normalizedRange);
      });

      const observer = new ResizeObserver(() => {
        const width = measureContainerWidth(host);
        if (width > 0) chart.applyOptions({ width });
      });
      observer.observe(host);
      observerRef.current = observer;
    }

    chartRef.current.applyOptions({ height: ohlcChartHeightRef.current });

    const windowRange = candleBucketRange(data);
    if (windowRange) {
      loadedWindowRef.current = {
        step: windowRange.step,
        from: windowRange.since,
        to: windowRange.until,
      };
    }

    const requestedRangeToRestore =
      !follow && viewRange
        ? viewRange
        : !follow && !forceWindowRangeRef.current
          ? normalizeChartRange(chartRef.current?.timeScale().getVisibleRange())
          : null;
    const rangeToRestore = clampChartViewportRangeToBounds(
      requestedRangeToRestore,
      backtestBounds
    );
    if (rangeToRestore) {
      markProgrammaticRangeChange(rangeToRestore);
      visibleRangeRef.current = rangeToRestore;
    }

    const currentTimestamp = String(
      data.current.timestamp ?? data.window.center ?? ''
    );
    const currentPrice = toNumber(
      data.current.current_price ?? data.current.mid
    );
    if (currentTimestamp && chartSettings.ohlc.currentTick) {
      sequenceLineRef.current?.setPosition(currentTimestamp, currentPrice);
    } else {
      sequenceLineRef.current?.clear();
    }

    candleSeriesRef.current?.setData(buildContinuousCandleData(data));
    applyOhlcOverlays(
      chartRef.current,
      candleSeriesRef.current,
      ohlcCandlesForIndicators(data),
      chartSettings.ohlc
    );
    noDataRegionsRef.current?.setStyle(noDataRegionStyle);
    noDataRegionsRef.current?.setRegions(buildNoDataRegions(data));
    markersRef.current?.setMarkers(
      chartSettings.ohlc.tradeMarkers ? buildMarkerData(data.markers, t) : []
    );

    const visiblePriceLines = data.price_lines.filter((line) =>
      ohlcPriceLineVisible(line, chartSettings.ohlc)
    );
    for (const [id, series] of priceLineRefs.current.entries()) {
      if (!visiblePriceLines.some((line) => line.id === id)) {
        chartRef.current?.removeSeries(series);
        priceLineRefs.current.delete(id);
      }
    }
    for (const line of visiblePriceLines) {
      let series = priceLineRefs.current.get(line.id);
      const lineStyle = lightweightLineStyle(line);
      if (!series) {
        series = chartRef.current!.addSeries(LineSeries, {
          color: line.color,
          lineWidth: 2,
          lineStyle,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        priceLineRefs.current.set(line.id, series);
      } else {
        series.applyOptions({
          color: line.color,
          lineStyle,
        });
      }
      series.setData(lineSeriesData(line));
    }
    updatePriceAxisLabels(visiblePriceLines);

    const marginLine = chartSettings.ohlc.marginRatio
      ? marginOverlayLine(data.oscillator_lines)
      : null;
    chartRef.current.applyOptions({
      leftPriceScale: {
        visible: Boolean(marginLine),
        borderColor: isDark ? '#2a2e39' : '#cbd5e1',
      },
    });
    if (marginLine) {
      const lineStyle = lightweightLineStyle(marginLine);
      if (!marginLineRef.current) {
        marginLineRef.current = chartRef.current.addSeries(LineSeries, {
          priceScaleId: 'left',
          color: marginLine.color,
          lineWidth: 2,
          lineStyle,
          title: lineLabel(marginLine, t),
          priceFormat: { type: 'percent', precision: 1, minMove: 0.1 },
          priceLineVisible: false,
          lastValueVisible: false,
        });
      } else {
        marginLineRef.current.applyOptions({
          color: marginLine.color,
          lineStyle,
          title: lineLabel(marginLine, t),
          priceLineVisible: false,
          lastValueVisible: false,
        });
      }
      marginLineRef.current.setData(lineSeriesData(marginLine));
      updateMarginAxisLabel(marginLine);
    } else if (marginLineRef.current) {
      updateMarginAxisLabel(null);
      chartRef.current.removeSeries(marginLineRef.current);
      marginLineRef.current = null;
    }

    if (rangeToRestore && chartRef.current) {
      markProgrammaticRangeChange(rangeToRestore);
      chartRef.current.timeScale().setVisibleRange({
        from: rangeToRestore.from as Time,
        to: rangeToRestore.to as Time,
      });
      releaseProgrammaticRangeFlag(programmaticRangeRef);
      return;
    }

    if (follow && chartRef.current) {
      const center = Math.floor(new Date(data.window.center).getTime() / 1000);
      const span = data.window.granularity_seconds * DEFAULT_SIDE_BARS;
      const followRange = clampChartViewportRangeToBounds(
        {
          from: center - span,
          to: center + span,
        },
        backtestBounds
      );
      if (!followRange) {
        releaseProgrammaticRangeFlag(programmaticRangeRef);
        return;
      }
      markProgrammaticRangeChange(followRange);
      chartRef.current.timeScale().setVisibleRange({
        from: followRange.from as Time,
        to: followRange.to as Time,
      });
      releaseProgrammaticRangeFlag(programmaticRangeRef);
      return;
    }

    if (windowRange && chartRef.current) {
      const loadedRange = clampChartViewportRangeToBounds(
        {
          from: windowRange.since,
          to: windowRange.until,
        },
        backtestBounds
      );
      if (!loadedRange) {
        releaseProgrammaticRangeFlag(programmaticRangeRef);
        return;
      }
      markProgrammaticRangeChange(loadedRange);
      chartRef.current.timeScale().setVisibleRange({
        from: loadedRange.from as Time,
        to: loadedRange.to as Time,
      });
      forceWindowRangeRef.current = false;
      releaseProgrammaticRangeFlag(programmaticRangeRef);
    }
    if (follow) {
      releaseProgrammaticRangeFlag(programmaticRangeRef);
    }
  }, [
    applyOhlcOverlays,
    backtestBounds,
    chartSettings,
    data,
    destroyChart,
    follow,
    isDark,
    markProgrammaticRangeChange,
    noDataRegionStyle,
    scheduleVisibleRangeLoad,
    t,
    timezone,
    updateMarginAxisLabel,
    updatePriceAxisLabels,
    viewRange,
  ]);

  const handleRefresh = useCallback(() => {
    setRangeNowMs(Date.now());
    void chartQuery.refetch();
  }, [chartQuery]);

  const handleFollow = useCallback(() => {
    resetAppliedWindowState();
    setRangePreset('follow');
    setQueryRangePreset('follow');
    setAppliedRange(null);
    setFollow(true);
    setViewRange(null);
    void chartQuery.refetch();
  }, [chartQuery, resetAppliedWindowState]);

  if (chartQuery.isLoading && !data) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (chartQuery.error) {
    return <Alert severity="warning">{String(chartQuery.error)}</Alert>;
  }

  const controlButtons = (
    <>
      <Tooltip
        title={
          follow
            ? t('strategy:snowballNet.chart.tooltips.followingCurrentTick')
            : t('strategy:snowballNet.chart.tooltips.followCurrentTick')
        }
      >
        <IconButton
          onClick={handleFollow}
          size="small"
          color={follow ? 'primary' : 'default'}
          aria-label={t(
            'strategy:snowballNet.chart.tooltips.followCurrentTick'
          )}
        >
          <CenterFocusStrongIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip
        title={
          mergeMarkers
            ? t('strategy:snowballNet.chart.tooltips.mergedMarkers')
            : t('strategy:snowballNet.chart.tooltips.rawMarkers')
        }
      >
        <IconButton
          onClick={() => setMergeMarkers((value) => !value)}
          size="small"
          color={mergeMarkers ? 'primary' : 'default'}
          aria-label={t('strategy:snowballNet.chart.tooltips.mergeMarkers')}
        >
          <MergeIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title={t('common:metrics.refreshAllCharts')}>
        <span>
          <IconButton
            onClick={handleRefresh}
            size="small"
            disabled={chartQuery.isFetching}
            aria-label={t('common:metrics.refreshAllCharts')}
          >
            <RefreshIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <Tooltip title={t('strategy:snowballNet.chart.settings.title')}>
        <IconButton
          onClick={() => setSettingsOpen(true)}
          size="small"
          aria-label={t('strategy:snowballNet.chart.settings.title')}
        >
          <SettingsIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </>
  );

  return (
    <Box sx={{ p: { xs: 1, sm: 2 }, minWidth: 0 }}>
      <Stack spacing={{ xs: 0.75, sm: 1 }} sx={{ mb: 1.5, minWidth: 0 }}>
        {/* Desktop: icon buttons right-aligned on the same row as selectors.
            Mobile: icon buttons on their own row. */}
        <Box
          sx={{
            display: { xs: 'flex', sm: 'none' },
            gap: 0.5,
            alignItems: 'center',
            justifyContent: 'flex-end',
            minWidth: 0,
          }}
        >
          {controlButtons}
        </Box>
        <Box
          sx={{
            display: 'flex',
            gap: { xs: 0.75, sm: 1 },
            alignItems: 'center',
            flexWrap: { xs: 'wrap', sm: 'nowrap' },
            minWidth: 0,
          }}
        >
          <FormControl
            size="small"
            sx={{
              minWidth: { xs: 0, sm: 180 },
              flex: { xs: '1 1 45%', sm: '0 0 auto' },
            }}
          >
            <InputLabel id="snowball-net-range-label">
              {t('strategy:snowballNet.chart.controls.range')}
            </InputLabel>
            <Select
              labelId="snowball-net-range-label"
              value={rangePreset}
              label={t('strategy:snowballNet.chart.controls.range')}
              onChange={(event) =>
                handleRangePresetChange(
                  event.target.value as SnowballNetRangePreset
                )
              }
            >
              {SNOWBALL_NET_RANGE_PRESETS.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {t(
                    `strategy:snowballNet.chart.controls.ranges.${option.labelKey}`
                  )}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl
            size="small"
            sx={{
              minWidth: { xs: 0, sm: 130 },
              flex: { xs: '1 1 45%', sm: '0 0 auto' },
            }}
          >
            <InputLabel id="snowball-net-granularity-label">
              {t('strategy:snowballNet.chart.controls.granularityLabel')}
            </InputLabel>
            <Select
              labelId="snowball-net-granularity-label"
              value={displayedGranularitySelection}
              label={t('strategy:snowballNet.chart.controls.granularityLabel')}
              onChange={(event) => {
                const next = event.target
                  .value as SnowballNetGranularitySelection;
                if (
                  !isSnowballNetGranularityAllowedForRange(
                    next,
                    draftRequestedRangeSeconds
                  )
                ) {
                  return;
                }
                setGranularitySelection(next);
              }}
            >
              {GRANULARITY_OPTIONS.map((option) => (
                <MenuItem
                  key={option}
                  value={option}
                  disabled={
                    !isSnowballNetGranularityAllowedForRange(
                      option,
                      draftRequestedRangeSeconds
                    )
                  }
                >
                  {option === 'Auto'
                    ? t('strategy:snowballNet.chart.controls.autoGranularity', {
                        granularity: draftAutoGranularity,
                      })
                    : option}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl
            size="small"
            sx={{
              minWidth: { xs: 0, sm: 120 },
              flex: { xs: '1 1 100%', sm: '0 0 auto' },
              maxWidth: { xs: '100%', sm: 180 },
            }}
          >
            <InputLabel id="snowball-net-refresh-label">
              {t('strategy:snowballNet.chart.controls.refreshInterval')}
            </InputLabel>
            <Select
              labelId="snowball-net-refresh-label"
              value={String(refreshSeconds)}
              label={t('strategy:snowballNet.chart.controls.refreshInterval')}
              onChange={(event) =>
                setRefreshSeconds(Number(event.target.value))
              }
            >
              {REFRESH_OPTIONS.map((seconds) => (
                <MenuItem key={seconds} value={String(seconds)}>
                  {seconds === 0
                    ? t('strategy:snowballNet.chart.controls.off')
                    : t('strategy:snowballNet.chart.controls.seconds', {
                        seconds,
                      })}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {/* Custom date range fields — inline on desktop, stacked on mobile */}
          {rangePreset === 'custom' ? (
            <>
              <TextField
                label={t('strategy:snowballNet.chart.controls.customSince')}
                type="datetime-local"
                size="small"
                value={customSince}
                onChange={(event) =>
                  handleCustomSinceChange(event.target.value)
                }
                slotProps={{ inputLabel: { shrink: true } }}
                sx={{
                  minWidth: 0,
                  width: { xs: '100%', sm: 200 },
                  flex: { xs: '1 1 100%', sm: '0 0 auto' },
                }}
              />
              <TextField
                label={t('strategy:snowballNet.chart.controls.customUntil')}
                type="datetime-local"
                size="small"
                value={customUntil}
                onChange={(event) =>
                  handleCustomUntilChange(event.target.value)
                }
                slotProps={{ inputLabel: { shrink: true } }}
                sx={{
                  minWidth: 0,
                  width: { xs: '100%', sm: 200 },
                  flex: { xs: '1 1 100%', sm: '0 0 auto' },
                }}
              />
            </>
          ) : null}
          <Button
            variant="contained"
            size="small"
            onClick={handleApplyChartControls}
            disabled={rangePreset !== 'follow' && !draftSelectedRange}
            sx={{
              height: 32,
              minHeight: 0,
              boxSizing: 'border-box',
              alignSelf: 'center',
              flex: { xs: '1 1 100%', sm: '0 0 auto' },
              py: 0,
              px: 2,
            }}
          >
            {t('strategy:snowballNet.chart.controls.applyRange')}
          </Button>
          {/* Desktop only: icon buttons at the end of the selector row */}
          <Box
            sx={{
              display: { xs: 'none', sm: 'flex' },
              gap: 0.5,
              alignItems: 'center',
              ml: 'auto',
              flexShrink: 0,
            }}
          >
            {controlButtons}
          </Box>
        </Box>
        <Box sx={{ display: { xs: 'none', sm: 'block' } }}>
          <CurrentChips data={data} instrument={instrument} />
        </Box>
      </Stack>

      <SnowballNetChartSettingsDialog
        open={settingsOpen}
        settings={chartSettings}
        chartOrderItems={chartOrderItems}
        onClose={() => setSettingsOpen(false)}
        onChange={updateChartSettings}
        onOrderChange={updateChartOrder}
        onOrderReset={resetChartOrder}
      />

      <SnowballNetCharts
        data={data}
        settings={chartSettings}
        chartOrder={chartOrder}
        timezone={timezone}
        instrument={instrument}
        containerRef={containerRef}
        ohlcChartHeight={ohlcChartHeight}
        dragChartKey={dragChartKey}
        dragOverChartKey={dragOverChartKey}
        onChartDragStart={handleChartDragStart}
        onChartDragOver={handleChartDragOver}
        onChartDrop={handleChartDrop}
        onChartDragEnd={handleChartDragEnd}
        onOhlcResizePointerDown={handleOhlcResizePointerDown}
        onOhlcResizeKeyDown={handleOhlcResizeKeyDown}
        lossCutEvents={lossCutEvents}
        showLossCutMarkers={showLossCutMarkers}
      />
    </Box>
  );
}

function CurrentChips({
  data,
  instrument,
}: {
  data: SnowballNetChartResponse | null;
  instrument?: string;
}) {
  const { t } = useTranslation('strategy');
  if (!data) return null;
  const current = data.current;
  const direction = String(current.direction ?? '').toLowerCase();
  const directionLabel =
    direction === 'long'
      ? t('snapshotValues.direction.long')
      : direction === 'short'
        ? t('snapshotValues.direction.short')
        : direction === 'auto'
          ? t('snapshotValues.direction.auto')
          : null;
  const units = toNumber(current.net_units);
  const avg = toNumber(current.average_price);
  const pips = toNumber(current.pips_from_average);
  const margin = toNumber(current.margin_ratio_pct);
  const marginReduceThreshold = toNumber(current.margin_reduce_threshold_pct);
  const emergencyThreshold = toNumber(current.emergency_threshold_pct);
  const realizedPnl = toNumber(current.realized_pnl);
  const unrealizedPnl = toNumber(current.unrealized_pnl);
  const price = toNumber(current.current_price ?? current.mid);
  const pnlCurrency = pnlCurrencyCode(data);
  const baseCurrency = baseCurrencyFromInstrument(instrument);
  const suffix = baseCurrency ? ` ${baseCurrency}` : '';
  return (
    <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap">
      {directionLabel ? (
        <Chip
          size="small"
          color={
            direction === 'long'
              ? 'success'
              : direction === 'short'
                ? 'warning'
                : 'default'
          }
          label={`${t('snowballNet.chart.current.direction')} ${directionLabel}`}
        />
      ) : null}
      <Chip
        size="small"
        label={`${t('snowballNet.chart.current.net')} ${formatAppNumber(units ?? 0)}${suffix}`}
      />
      <Chip
        size="small"
        label={`${t('snowballNet.chart.current.average')} ${avg != null ? formatAppNumber(avg, { maximumFractionDigits: 5 }) : '-'}`}
      />
      <Chip
        size="small"
        label={`${t('snowballNet.chart.current.price')} ${price != null ? formatAppNumber(price, { maximumFractionDigits: 5 }) : '-'}`}
      />
      <Chip
        size="small"
        color={pips != null && pips >= 0 ? 'success' : 'warning'}
        label={`${t('snowballNet.chart.current.pips')} ${pips != null ? formatAppNumber(pips, { maximumFractionDigits: 1 }) : '-'}`}
      />
      <Chip
        size="small"
        color={
          margin != null && margin >= (marginReduceThreshold ?? 70)
            ? 'warning'
            : 'default'
        }
        label={`${t('snowballNet.chart.current.margin')} ${margin != null ? formatAppPercent(margin, 1) : '-'}`}
      />
      <Chip
        size="small"
        color={realizedPnl != null && realizedPnl >= 0 ? 'success' : 'warning'}
        label={`${t('snowballNet.chart.current.realizedPnl')} ${formatNullablePnl(realizedPnl, pnlCurrency)}`}
      />
      <Chip
        size="small"
        color={
          unrealizedPnl != null && unrealizedPnl >= 0 ? 'success' : 'warning'
        }
        label={`${t('snowballNet.chart.current.unrealizedPnl')} ${formatNullablePnl(unrealizedPnl, pnlCurrency)}`}
      />
      {marginReduceThreshold != null ? (
        <Chip
          size="small"
          label={`${t('snowballNet.chart.current.reduceThreshold')} ${formatAppPercent(marginReduceThreshold, 1)}`}
        />
      ) : null}
      {emergencyThreshold != null ? (
        <Chip
          size="small"
          color={
            margin != null && margin >= emergencyThreshold ? 'error' : 'default'
          }
          label={`${t('snowballNet.chart.current.emergencyThreshold')} ${formatAppPercent(emergencyThreshold, 1)}`}
        />
      ) : null}
    </Stack>
  );
}

function SnowballNetCharts({
  data,
  settings,
  chartOrder,
  timezone,
  instrument,
  containerRef,
  ohlcChartHeight,
  dragChartKey,
  dragOverChartKey,
  onChartDragStart,
  onChartDragOver,
  onChartDrop,
  onChartDragEnd,
  onOhlcResizePointerDown,
  onOhlcResizeKeyDown,
  lossCutEvents,
  showLossCutMarkers,
}: {
  data: SnowballNetChartResponse | null;
  settings: SnowballNetChartSettings;
  chartOrder: SnowballNetChartKey[];
  timezone: string;
  instrument?: string;
  containerRef: MutableRefObject<HTMLDivElement | null>;
  ohlcChartHeight: number;
  dragChartKey: SnowballNetChartKey | null;
  dragOverChartKey: SnowballNetChartKey | null;
  onChartDragStart: (event: ReactDragEvent, key: SnowballNetChartKey) => void;
  onChartDragOver: (event: ReactDragEvent, key: SnowballNetChartKey) => void;
  onChartDrop: (event: ReactDragEvent, key: SnowballNetChartKey) => void;
  onChartDragEnd: () => void;
  onOhlcResizePointerDown: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onOhlcResizeKeyDown: (event: ReactKeyboardEvent<HTMLDivElement>) => void;
  lossCutEvents?: Array<{ id: string; time: number; units: number }>;
  showLossCutMarkers?: boolean;
}) {
  const { t } = useTranslation(['common', 'strategy']);
  const timeDomain = data ? chartTimeDomain(data) : undefined;
  const pnlCurrency = data ? pnlCurrencyCode(data) : null;
  const priceCurrency = quoteCurrencyFromInstrument(
    data?.instrument ?? instrument
  );
  const visibleKeys = chartOrder.filter((key) => settings.charts[key]);

  if (visibleKeys.length === 0) return null;

  const renderLineChart = (key: SnowballNetChartKey) => {
    const headerPrefix = (
      <DragIndicatorIcon
        sx={{
          fontSize: 16,
          color: 'text.disabled',
          cursor: 'grab',
          mr: 0.25,
        }}
      />
    );
    switch (key) {
      case 'netUnits':
        return (
          <DeferredLineChartCard
            title={t('strategy:snowballNet.chart.netUnits')}
            lines={data ? netUnitsChartLines(data.oscillator_lines) : []}
            timezone={timezone}
            timeDomain={timeDomain}
            headerPrefix={headerPrefix}
          />
        );
      case 'pips':
        return (
          <DeferredLineChartCard
            title={t('strategy:snowballNet.chart.pipsFromAverage')}
            lines={data ? pipsChartLines(data.oscillator_lines) : []}
            timezone={timezone}
            timeDomain={timeDomain}
            headerPrefix={headerPrefix}
          />
        );
      case 'margin':
        return (
          <DeferredLineChartCard
            title={t('strategy:snowballNet.chart.marginRatio')}
            lines={data ? marginChartLines(data.oscillator_lines) : []}
            timezone={timezone}
            timeDomain={timeDomain}
            percent
            headerPrefix={headerPrefix}
            lossCutEvents={lossCutEvents}
            showLossCutMarkers={showLossCutMarkers}
          />
        );
      case 'pnl':
        return (
          <DeferredLineChartCard
            title={appendUnitLabel(
              t('strategy:snowballNet.chart.pnl'),
              pnlCurrency
            )}
            lines={data ? pnlChartLines(data.oscillator_lines) : []}
            timezone={timezone}
            timeDomain={timeDomain}
            valueUnit={pnlCurrency}
            seriesLabelUnit={pnlCurrency}
            headerPrefix={headerPrefix}
            lossCutEvents={lossCutEvents}
            showLossCutMarkers={showLossCutMarkers}
          />
        );
      case 'averagePrice':
        return (
          <DeferredLineChartCard
            title={appendUnitLabel(
              t('strategy:snowballNet.chart.averagePrice'),
              priceCurrency
            )}
            lines={
              data ? priceChartLines(data.price_lines, 'averagePrice') : []
            }
            timezone={timezone}
            timeDomain={timeDomain}
            headerPrefix={headerPrefix}
          />
        );
      case 'takeProfit':
        return (
          <DeferredLineChartCard
            title={appendUnitLabel(
              t('strategy:snowballNet.chart.takeProfit'),
              priceCurrency
            )}
            lines={data ? priceChartLines(data.price_lines, 'takeProfit') : []}
            timezone={timezone}
            timeDomain={timeDomain}
            headerPrefix={headerPrefix}
          />
        );
      case 'nextAdd':
        return (
          <DeferredLineChartCard
            title={appendUnitLabel(
              t('strategy:snowballNet.chart.nextAdd'),
              priceCurrency
            )}
            lines={data ? priceChartLines(data.price_lines, 'nextAdd') : []}
            timezone={timezone}
            timeDomain={timeDomain}
            headerPrefix={headerPrefix}
          />
        );
      default:
        return null;
    }
  };

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: {
          xs: '1fr',
          lg: 'repeat(2, minmax(0, 1fr))',
          xl: 'repeat(3, minmax(0, 1fr))',
        },
        gap: 1.5,
        mt: 1.5,
      }}
    >
      {visibleKeys.map((key) => {
        const isOhlc = key === 'ohlc';
        const content = isOhlc ? (
          <OhlcChartCard
            data={data}
            instrument={instrument}
            containerRef={containerRef}
            height={ohlcChartHeight}
            onResizePointerDown={onOhlcResizePointerDown}
            onResizeKeyDown={onOhlcResizeKeyDown}
          />
        ) : (
          renderLineChart(key)
        );
        if (!content) return null;

        return (
          <Box
            key={key}
            draggable={!isOhlc}
            onDragStart={
              isOhlc ? undefined : (event) => onChartDragStart(event, key)
            }
            onDragOver={
              isOhlc ? undefined : (event) => onChartDragOver(event, key)
            }
            onDrop={isOhlc ? undefined : (event) => onChartDrop(event, key)}
            onDragEnd={isOhlc ? undefined : onChartDragEnd}
            sx={{
              gridColumn: isOhlc ? '1 / -1' : undefined,
              opacity: !isOhlc && dragChartKey === key ? 0.4 : 1,
              cursor: isOhlc ? 'default' : 'grab',
              minWidth: 0,
              transition:
                'opacity 120ms ease, transform 120ms ease, outline-color 120ms ease',
              transform:
                !isOhlc && dragOverChartKey === key && dragChartKey !== key
                  ? 'translateY(-2px)'
                  : 'none',
              outline: '2px solid',
              outlineColor:
                !isOhlc && dragOverChartKey === key && dragChartKey !== key
                  ? 'primary.main'
                  : 'transparent',
              outlineOffset: 3,
              borderRadius: 1,
            }}
          >
            {content}
          </Box>
        );
      })}
    </Box>
  );
}

function OhlcChartCard({
  data,
  instrument,
  containerRef,
  height,
  onResizePointerDown,
  onResizeKeyDown,
}: {
  data: SnowballNetChartResponse | null;
  instrument?: string;
  containerRef: MutableRefObject<HTMLDivElement | null>;
  height: number;
  onResizePointerDown: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onResizeKeyDown: (event: ReactKeyboardEvent<HTMLDivElement>) => void;
}) {
  const { t } = useTranslation(['common', 'strategy']);
  return (
    <>
      <Paper variant="outlined" sx={{ p: 1, minWidth: 0 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.75,
            mb: 0.75,
          }}
        >
          <TimelineIcon fontSize="small" color="action" />
          <Typography variant="subtitle2">
            {instrument ? instrument.replace('_', '/') : 'SnowballNet'}
          </Typography>
        </Box>
        {data ? (
          <Box
            ref={containerRef}
            sx={{
              width: '100%',
              height,
              minHeight: MIN_OHLC_CHART_HEIGHT,
            }}
          />
        ) : (
          <Alert severity="info">{t('common:metrics.noData')}</Alert>
        )}
      </Paper>
      {data ? (
        <Box
          role="separator"
          aria-label={t('strategy:snowballNet.chart.resizeOhlcChart')}
          aria-orientation="horizontal"
          aria-valuemin={MIN_OHLC_CHART_HEIGHT}
          aria-valuemax={MAX_OHLC_CHART_HEIGHT}
          aria-valuenow={height}
          tabIndex={0}
          onPointerDown={(event) => {
            event.stopPropagation();
            onResizePointerDown(event);
          }}
          onKeyDown={onResizeKeyDown}
          sx={{
            height: 18,
            my: 0.75,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'row-resize',
            outline: 'none',
            touchAction: 'none',
            '&::before': {
              content: '""',
              width: 88,
              height: 4,
              borderRadius: 999,
              bgcolor: 'divider',
              transition: (muiTheme) =>
                muiTheme.transitions.create('background-color', {
                  duration: muiTheme.transitions.duration.shortest,
                }),
            },
            '&:hover::before, &:focus-visible::before': {
              bgcolor: 'primary.main',
            },
          }}
        />
      ) : null}
    </>
  );
}

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
        {...(size.width > 0 ? { width: size.width } : {})}
        height={
          size.height > MIN_CHART_MEASURE_PX ? size.height : fallbackHeight
        }
      >
        {children}
      </LineChart>
    </Box>
  );
}

function DeferredLineChartCard(props: ComponentProps<typeof LineChartCard>) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [shouldRender, setShouldRender] = useState(
    () => typeof IntersectionObserver === 'undefined'
  );

  useEffect(() => {
    if (shouldRender) return undefined;
    const host = hostRef.current;
    if (!host) return undefined;

    const observer = new IntersectionObserver(
      (entries) => {
        if (
          entries.some(
            (entry) => entry.isIntersecting || entry.intersectionRatio > 0
          )
        ) {
          setShouldRender(true);
          observer.disconnect();
        }
      },
      { rootMargin: '320px 0px' }
    );
    observer.observe(host);
    return () => observer.disconnect();
  }, [shouldRender]);

  return (
    <Box ref={hostRef} sx={{ minHeight: LINE_CHART_CARD_HEIGHT }}>
      {shouldRender ? (
        <LineChartCard {...props} />
      ) : (
        <Paper
          variant="outlined"
          sx={{
            height: LINE_CHART_CARD_HEIGHT,
            minWidth: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <CircularProgress size={18} />
        </Paper>
      )}
    </Box>
  );
}

function LineChartCard({
  title,
  lines,
  timezone,
  timeDomain,
  showWhenEmpty = true,
  percent = false,
  valueUnit,
  seriesLabelUnit,
  headerPrefix,
  lossCutEvents,
  showLossCutMarkers,
}: {
  title: string;
  lines: SnowballNetLineSeries[];
  timezone: string;
  timeDomain?: LineChartTimeDomain;
  showWhenEmpty?: boolean;
  percent?: boolean;
  valueUnit?: string | null;
  seriesLabelUnit?: string | null;
  headerPrefix?: ReactNode;
  lossCutEvents?: Array<{ id: string; time: number; units: number }>;
  showLossCutMarkers?: boolean;
}) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const { t } = useTranslation('strategy');
  const visible = lines.filter((line) => line.points.length >= 2);
  const isEmpty = visible.length === 0;
  if (isEmpty && !showWhenEmpty) return null;

  const times = Array.from(
    new Set(
      isEmpty && timeDomain
        ? [
            Math.floor(timeDomain.min.getTime() / 1000),
            Math.floor(timeDomain.max.getTime() / 1000),
          ]
        : visible.flatMap((line) => line.points.map((point) => point.time))
    )
  ).sort((left, right) => left - right);
  const x = times.map((time) => new Date(time * 1000));
  const series = isEmpty
    ? [
        {
          data: times.map(() => 0),
          color: 'transparent',
          showMark: false,
          label: title,
        },
      ]
    : visible.map((line) => {
        const points = new Map(
          line.points.map((point) => [point.time, point.value])
        );
        const thresholdValue = isThresholdLine(line)
          ? (latestLinePoint(line)?.value ?? null)
          : null;
        return {
          data: times.map((time) => points.get(time) ?? thresholdValue),
          color: line.color,
          connectNulls: isThresholdLine(line),
          showMark: false,
          label: appendUnitLabel(lineLabel(line, t), seriesLabelUnit),
          valueFormatter: (value: number | null) =>
            value == null
              ? ''
              : formatNumberWithUnit(value, valueUnit, {
                  maximumFractionDigits: valueUnit ? 2 : 1,
                }),
        };
      });
  const thresholdChips = visible
    .filter(isThresholdLine)
    .map((line) => ({ line, point: latestLinePoint(line) }))
    .filter(
      (
        item
      ): item is { line: SnowballNetLineSeries; point: SnowballNetLinePoint } =>
        item.point !== null
    );
  const legendItems = visible.map((line) => ({
    id: line.id,
    color: line.color,
    label: appendUnitLabel(lineLabel(line, t), seriesLabelUnit),
  }));
  const formatAxisValue = (value: number) =>
    percent
      ? `${formatAppNumber(value, { maximumFractionDigits: 1 })}%`
      : formatNumberWithUnit(value, valueUnit, {
          maximumFractionDigits: valueUnit ? 2 : 1,
        });
  const yAxisValues = isEmpty
    ? [0, 1]
    : visible.flatMap((line) => line.points.map((point) => point.value));
  const maxYAxisLabelLength = yAxisValues.reduce(
    (max, value) => Math.max(max, formatAxisValue(value).length),
    0
  );
  const yAxisWidth = Math.max(
    MIN_Y_AXIS_WIDTH,
    Math.ceil(maxYAxisLabelLength * Y_AXIS_CHAR_WIDTH_PX) + Y_AXIS_OVERHEAD_PX
  );

  return (
    <Paper
      variant="outlined"
      sx={{
        p: { xs: 0.25, sm: 1 },
        minWidth: 0,
        minHeight: 220,
        height: LINE_CHART_CARD_HEIGHT,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        mx: 'auto',
      }}
    >
      <Stack
        direction="row"
        spacing={0.75}
        useFlexGap
        flexWrap={{ xs: 'nowrap', sm: 'wrap' }}
        alignItems="center"
        sx={{
          mb: { xs: 0.25, sm: 0.5 },
          minHeight: { xs: 24, sm: 'auto' },
          overflow: 'hidden',
        }}
      >
        {headerPrefix}
        <Typography
          variant="subtitle2"
          noWrap
          sx={{ flex: { xs: '0 1 auto', sm: '0 0 auto' }, minWidth: 0 }}
        >
          {title}
        </Typography>
        <Box
          sx={{
            display: {
              xs: legendItems.length > 1 ? 'flex' : 'none',
              sm: 'none',
            },
            alignItems: 'center',
            gap: 0.75,
            flex: '1 1 auto',
            minWidth: 0,
            overflowX: 'auto',
            scrollbarWidth: 'none',
            whiteSpace: 'nowrap',
            '&::-webkit-scrollbar': { display: 'none' },
          }}
        >
          {legendItems.map((item) => (
            <Box
              key={item.id}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.4,
                flex: '0 0 auto',
                minWidth: 0,
              }}
            >
              <Box
                sx={{
                  width: 12,
                  height: 3,
                  borderRadius: 999,
                  bgcolor: item.color,
                }}
              />
              <Typography
                variant="caption"
                noWrap
                sx={{ color: 'text.secondary', fontSize: '0.7rem' }}
              >
                {item.label}
              </Typography>
            </Box>
          ))}
        </Box>
        {thresholdChips.map(({ line, point }) => (
          <Chip
            key={line.id}
            size="small"
            sx={{ display: { xs: 'none', sm: 'inline-flex' }, height: 20 }}
            label={`${lineLabel(line, t)} ${
              percent
                ? formatAppPercent(point.value, 1)
                : formatNumberWithUnit(point.value, valueUnit, {
                    maximumFractionDigits: valueUnit ? 2 : 1,
                  })
            }`}
          />
        ))}
      </Stack>
      <Box
        sx={{
          position: 'relative',
          flex: 1,
          minHeight: 0,
          minWidth: 0,
          width: '100%',
          display: 'flex',
          alignItems: 'stretch',
          '& .MuiCharts-root': {
            width: '100%',
            height: '100%',
          },
          '& [class*="MuiChartsWrapper-root"]': {
            width: '100% !important',
            height: '100% !important',
          },
          '& .MuiChartsSurface-root': {
            width: '100% !important',
            height: '100% !important',
          },
          '& svg': {
            display: 'block',
          },
        }}
      >
        <FillLineChart
          fallbackHeight={LINE_CHART_FALLBACK_HEIGHT}
          xAxis={[
            {
              data: x,
              scaleType: 'time',
              tickNumber: isMobile ? 4 : 6,
              min: timeDomain?.min,
              max: timeDomain?.max,
              tickLabelStyle: { fontSize: 10, lineHeight: 1.15 },
              valueFormatter: (value: Date, context: { location: string }) =>
                formatLineChartXAxis(value, timezone, context.location),
            },
          ]}
          yAxis={[
            {
              position: 'right',
              width: yAxisWidth,
              min: isEmpty ? 0 : undefined,
              max: isEmpty ? 1 : undefined,
              tickLabelStyle: { fontSize: 10 },
              valueFormatter: (value: number) => formatAxisValue(value),
            },
          ]}
          series={series}
          margin={{
            left: isMobile ? 0 : LINE_CHART_LEFT_MARGIN,
            right: isMobile ? 0 : LINE_CHART_RIGHT_MARGIN,
            top: isMobile ? 0 : LINE_CHART_TOP_MARGIN,
            bottom: isMobile ? 22 : LINE_CHART_BOTTOM_MARGIN,
          }}
          grid={{ vertical: true, horizontal: true }}
          hideLegend={isMobile || visible.length <= 1}
          slotProps={{
            axisTickLabel: {
              style: { fontSize: 10 },
            },
            legend: {
              direction: 'row',
              position: {
                vertical: 'top',
                horizontal: 'left',
              },
              padding: 0,
              itemMarkWidth: isMobile ? 10 : 12,
              itemMarkHeight: isMobile ? 4 : 6,
              labelStyle: { fontSize: isMobile ? 11 : 12 },
            } as Record<string, unknown>,
          }}
        >
          {showLossCutMarkers &&
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
        {isEmpty ? (
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              pointerEvents: 'none',
            }}
          >
            <Typography variant="caption" color="text.secondary">
              {t('snowballNet.chart.noData')}
            </Typography>
          </Box>
        ) : null}
      </Box>
    </Paper>
  );
}

function SnowballNetChartSettingsDialog({
  open,
  settings,
  chartOrderItems,
  onClose,
  onChange,
  onOrderChange,
  onOrderReset,
}: {
  open: boolean;
  settings: SnowballNetChartSettings;
  chartOrderItems: SnowballNetChartOrderItem[];
  onClose: () => void;
  onChange: (
    updater: (current: SnowballNetChartSettings) => SnowballNetChartSettings
  ) => void;
  onOrderChange: (keys: SnowballNetChartKey[]) => void;
  onOrderReset: () => void;
}) {
  const { t } = useTranslation(['strategy', 'dashboard']);
  const toggleChart = (key: keyof SnowballNetChartSettings['charts']) => {
    onChange((current) => ({
      ...current,
      charts: { ...current.charts, [key]: !current.charts[key] },
    }));
  };
  const toggleOhlc = (key: keyof SnowballNetChartSettings['ohlc']) => {
    onChange((current) => ({
      ...current,
      ohlc: { ...current.ohlc, [key]: !current.ohlc[key] },
    }));
  };
  const reset = () => onChange(() => DEFAULT_CHART_SETTINGS);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {t('strategy:snowballNet.chart.settings.title')}
      </DialogTitle>
      <DialogContent dividers>
        <Typography variant="subtitle2" sx={{ mb: 0.75 }}>
          {t('strategy:snowballNet.chart.settings.chartPanels')}
        </Typography>
        <FormGroup
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' },
          }}
        >
          <SettingsCheckbox
            checked={settings.charts.ohlc}
            label={t('strategy:snowballNet.chart.settings.ohlc')}
            onChange={() => toggleChart('ohlc')}
          />
          <SettingsCheckbox
            checked={settings.charts.netUnits}
            label={t('strategy:snowballNet.chart.netUnits')}
            onChange={() => toggleChart('netUnits')}
          />
          <SettingsCheckbox
            checked={settings.charts.pips}
            label={t('strategy:snowballNet.chart.pipsFromAverage')}
            onChange={() => toggleChart('pips')}
          />
          <SettingsCheckbox
            checked={settings.charts.margin}
            label={t('strategy:snowballNet.chart.marginRatio')}
            onChange={() => toggleChart('margin')}
          />
          <SettingsCheckbox
            checked={settings.charts.pnl}
            label={t('strategy:snowballNet.chart.pnl')}
            onChange={() => toggleChart('pnl')}
          />
          <SettingsCheckbox
            checked={settings.charts.averagePrice}
            label={t('strategy:snowballNet.chart.averagePrice')}
            onChange={() => toggleChart('averagePrice')}
          />
          <SettingsCheckbox
            checked={settings.charts.takeProfit}
            label={t('strategy:snowballNet.chart.takeProfit')}
            onChange={() => toggleChart('takeProfit')}
          />
          <SettingsCheckbox
            checked={settings.charts.nextAdd}
            label={t('strategy:snowballNet.chart.nextAdd')}
            onChange={() => toggleChart('nextAdd')}
          />
        </FormGroup>

        <Divider sx={{ my: 1.5 }} />

        <Typography variant="subtitle2" sx={{ mb: 0.75 }}>
          {t('strategy:snowballNet.chart.settings.chartOrder')}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {t('strategy:snowballNet.chart.settings.chartOrderDescription')}
        </Typography>
        <SnowballNetChartOrderList
          items={chartOrderItems}
          onChange={onOrderChange}
        />
        <Button
          size="small"
          color="inherit"
          onClick={onOrderReset}
          sx={{ mt: 0.75 }}
        >
          {t('strategy:snowballNet.chart.settings.resetChartOrder')}
        </Button>

        <Divider sx={{ my: 1.5 }} />

        <Typography variant="subtitle2" sx={{ mb: 0.75 }}>
          {t('strategy:snowballNet.chart.settings.ohlcItems')}
        </Typography>
        <FormGroup
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' },
          }}
        >
          <SettingsCheckbox
            checked={settings.ohlc.tradeMarkers}
            label={t('strategy:snowballNet.chart.settings.tradeMarkers')}
            onChange={() => toggleOhlc('tradeMarkers')}
          />
          <SettingsCheckbox
            checked={settings.ohlc.currentTick}
            label={t('strategy:snowballNet.chart.settings.currentTick')}
            onChange={() => toggleOhlc('currentTick')}
          />
          <SettingsCheckbox
            checked={settings.ohlc.averagePrice}
            label={t('strategy:snowballNet.chart.averagePrice')}
            onChange={() => toggleOhlc('averagePrice')}
          />
          <SettingsCheckbox
            checked={settings.ohlc.takeProfit}
            label={t('strategy:snowballNet.chart.takeProfit')}
            onChange={() => toggleOhlc('takeProfit')}
          />
          <SettingsCheckbox
            checked={settings.ohlc.nextAdd}
            label={t('strategy:snowballNet.chart.nextAdd')}
            onChange={() => toggleOhlc('nextAdd')}
          />
          <SettingsCheckbox
            checked={settings.ohlc.marginRatio}
            label={t('strategy:snowballNet.chart.settings.marginOverlay')}
            onChange={() => toggleOhlc('marginRatio')}
          />
        </FormGroup>

        <Divider sx={{ my: 1.5 }} />

        <Typography variant="subtitle2" sx={{ mb: 0.75 }}>
          {t('dashboard:overlays.indicators')}
        </Typography>
        <FormGroup
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' },
          }}
        >
          <SettingsCheckbox
            checked={settings.ohlc.sma20}
            label={t('dashboard:overlays.sma20')}
            onChange={() => toggleOhlc('sma20')}
          />
          <SettingsCheckbox
            checked={settings.ohlc.sma50}
            label={t('dashboard:overlays.sma50')}
            onChange={() => toggleOhlc('sma50')}
          />
          <SettingsCheckbox
            checked={settings.ohlc.ema12}
            label={t('dashboard:overlays.ema12')}
            onChange={() => toggleOhlc('ema12')}
          />
          <SettingsCheckbox
            checked={settings.ohlc.ema26}
            label={t('dashboard:overlays.ema26')}
            onChange={() => toggleOhlc('ema26')}
          />
          <SettingsCheckbox
            checked={settings.ohlc.bollinger}
            label={t('dashboard:overlays.bollingerBands')}
            onChange={() => toggleOhlc('bollinger')}
          />
          <SettingsCheckbox
            checked={settings.ohlc.volume}
            label={t('dashboard:overlays.volume')}
            onChange={() => toggleOhlc('volume')}
          />
        </FormGroup>
      </DialogContent>
      <DialogActions>
        <Button onClick={reset}>{t('common:columnConfig.reset')}</Button>
        <Button onClick={onClose} variant="contained">
          {t('common:actions.close')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

interface SnowballNetChartOrderItem {
  key: SnowballNetChartKey;
  label: string;
  color?: string;
}

function SnowballNetChartOrderList({
  items,
  onChange,
}: {
  items: SnowballNetChartOrderItem[];
  onChange: (keys: SnowballNetChartKey[]) => void;
}) {
  const { t } = useTranslation('common');
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  const moveItem = useCallback(
    (from: number, to: number) => {
      if (from < 0 || to < 0 || from === to || to >= items.length) {
        return;
      }
      const next = [...items];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      onChange(next.map((item) => item.key));
    },
    [items, onChange]
  );

  const handleDragStart = useCallback(
    (event: ReactDragEvent, index: number) => {
      setDragIndex(index);
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', items[index]?.key ?? '');
    },
    [items]
  );

  const handleDragOver = useCallback(
    (event: ReactDragEvent, index: number) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      if (dragIndex !== null && dragIndex !== index) {
        moveItem(dragIndex, index);
        setDragIndex(index);
      }
    },
    [dragIndex, moveItem]
  );

  const handleDragEnd = useCallback(() => setDragIndex(null), []);

  return (
    <List dense disablePadding>
      {items.map((item, index) => (
        <ListItem
          key={item.key}
          draggable
          onDragStart={(event) => handleDragStart(event, index)}
          onDragOver={(event) => handleDragOver(event, index)}
          onDragEnd={handleDragEnd}
          sx={{
            cursor: 'grab',
            bgcolor: dragIndex === index ? 'action.hover' : 'transparent',
            borderRadius: 1,
            mb: 0.5,
            '&:hover': { bgcolor: 'action.hover' },
          }}
          secondaryAction={
            <Box sx={{ display: 'flex' }}>
              <IconButton
                edge="end"
                size="small"
                onClick={() => moveItem(index, index - 1)}
                disabled={index === 0}
                aria-label={t('metrics.moveChartUp')}
              >
                <ArrowUpIcon fontSize="small" />
              </IconButton>
              <IconButton
                edge="end"
                size="small"
                onClick={() => moveItem(index, index + 1)}
                disabled={index === items.length - 1}
                aria-label={t('metrics.moveChartDown')}
              >
                <ArrowDownIcon fontSize="small" />
              </IconButton>
            </Box>
          }
        >
          <ListItemIcon sx={{ minWidth: 32 }}>
            <DragIndicatorIcon
              fontSize="small"
              sx={{ color: 'text.secondary' }}
            />
          </ListItemIcon>
          <ListItemIcon sx={{ minWidth: 28 }}>
            <Box
              sx={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                bgcolor: item.color ?? 'text.disabled',
                border: '1px solid',
                borderColor: 'divider',
              }}
            />
          </ListItemIcon>
          <ListItemText primary={item.label} />
        </ListItem>
      ))}
    </List>
  );
}

function SettingsCheckbox({
  checked,
  label,
  onChange,
}: {
  checked: boolean;
  label: string;
  onChange: () => void;
}) {
  return (
    <FormControlLabel
      sx={{ m: 0, py: 0 }}
      control={
        <Checkbox
          size="small"
          sx={{ p: 0.25 }}
          checked={checked}
          onChange={onChange}
        />
      }
      label={label}
    />
  );
}

export default SnowballNetStrategyTab;
