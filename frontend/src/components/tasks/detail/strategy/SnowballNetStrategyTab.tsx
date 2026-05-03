import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type MutableRefObject,
  type PointerEvent as ReactPointerEvent,
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
  MenuItem,
  Paper,
  Select,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import CenterFocusStrongIcon from '@mui/icons-material/CenterFocusStrong';
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
  readStoredValue,
  writeStoredValue,
} from '../../../../utils/persistentState';

interface SnowballNetStrategyTabProps {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  instrument?: string;
  enableRealTimeUpdates?: boolean;
  timezone?: string;
}

const GRANULARITIES = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D'] as const;
const REFRESH_OPTIONS = [5, 15, 30, 60, 0] as const;
const DEFAULT_GRANULARITY = 'H1';
const DEFAULT_SIDE_BARS = 250;
const MIN_NO_DATA_BUCKETS = 2;
const SCROLL_FETCH_DEBOUNCE_MS = 450;
const EDGE_PREFETCH_RATIO = 0.2;
const MIN_EDGE_PREFETCH_BARS = 12;
const MARGIN_LINE_ID = 'margin_ratio_pct';
const LOSS_CUT_THRESHOLD_LINE_ID = 'loss_cut_threshold_pips';
const MARGIN_REDUCE_THRESHOLD_LINE_ID = 'margin_reduce_threshold_pct';
const MARGIN_REDUCE_TARGET_LINE_ID = 'margin_reduce_target_pct';
const EMERGENCY_THRESHOLD_LINE_ID = 'emergency_threshold_pct';
const CURRENT_PRICE_LINE_ID = 'current_price';
const REALIZED_PNL_LINE_ID = 'realized_pnl';
const UNREALIZED_PNL_LINE_ID = 'unrealized_pnl';
const SNOWBALL_NET_CHART_SETTINGS_KEY = 'snowball_net_strategy_chart_settings';
const OHLC_CHART_HEIGHT_KEY = 'snowball_net_strategy_ohlc_chart_height';
const DEFAULT_OHLC_CHART_HEIGHT = 460;
const MIN_OHLC_CHART_HEIGHT = 240;
const MAX_OHLC_CHART_HEIGHT = 1200;
const OHLC_CHART_RESIZE_STEP = 20;

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

function clampOhlcChartHeight(height: number): number {
  return Math.min(
    MAX_OHLC_CHART_HEIGHT,
    Math.max(MIN_OHLC_CHART_HEIGHT, Math.round(height))
  );
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

interface LoadedChartWindow extends ChartTimeRange {
  granularity: string;
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

function quoteCurrencyFromInstrument(
  instrument?: string | null
): string | null {
  if (!instrument || !instrument.includes('_')) return null;
  return normalizeCurrencyCode(instrument.split('_').at(-1));
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

function shouldFetchForVisibleRange(
  visible: ChartTimeRange,
  loaded: LoadedChartWindow | null,
  granularity: string
): boolean {
  if (!loaded || loaded.granularity !== granularity) return true;
  const span = visible.to - visible.from;
  const edgeBuffer = Math.max(
    loaded.step * MIN_EDGE_PREFETCH_BARS,
    span * EDGE_PREFETCH_RATIO
  );
  return (
    visible.from < loaded.from + edgeBuffer ||
    visible.to > loaded.to - edgeBuffer
  );
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
  enableRealTimeUpdates = false,
  timezone = 'UTC',
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
  const visibleRangeRef = useRef<ChartTimeRange | null>(null);
  const loadedWindowRef = useRef<LoadedChartWindow | null>(null);
  const lastRequestedRangeRef = useRef<ChartTimeRange | null>(null);
  const rangeFetchTimerRef = useRef<number | null>(null);
  const granularityRef = useRef(DEFAULT_GRANULARITY);
  const ohlcChartHeightRef = useRef(DEFAULT_OHLC_CHART_HEIGHT);
  const { applyOverlays: applyOhlcOverlays, clear: clearOhlcOverlays } =
    useOhlcChartOverlays(containerRef);
  const [granularity, setGranularity] = useState<string>(DEFAULT_GRANULARITY);
  const [follow, setFollow] = useState(true);
  const [mergeMarkers, setMergeMarkers] = useState(true);
  const [refreshSeconds, setRefreshSeconds] = useState<number>(15);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [chartSettings, setChartSettings] = useState<SnowballNetChartSettings>(
    () =>
      readStoredValue(
        SNOWBALL_NET_CHART_SETTINGS_KEY,
        snowballNetChartSettingsSchema,
        DEFAULT_CHART_SETTINGS
      )
  );
  const [ohlcChartHeight, setOhlcChartHeight] = useState(() =>
    readStoredValue(
      OHLC_CHART_HEIGHT_KEY,
      ohlcChartHeightSchema,
      DEFAULT_OHLC_CHART_HEIGHT
    )
  );
  const [viewRange, setViewRange] = useState<{
    from: number;
    to: number;
  } | null>(null);

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

  const queryParams = useMemo(() => {
    if (follow || !viewRange) {
      return {
        granularity,
        before_bars: DEFAULT_SIDE_BARS,
        after_bars: DEFAULT_SIDE_BARS,
        follow: 'true',
        merge_markers: mergeMarkers ? 'true' : 'false',
      };
    }
    const pad = Math.max(60, Math.floor((viewRange.to - viewRange.from) * 0.5));
    return {
      granularity,
      since: isoFromSeconds(Math.max(0, viewRange.from - pad)),
      until: isoFromSeconds(viewRange.to + pad),
      follow: 'false',
      merge_markers: mergeMarkers ? 'true' : 'false',
    };
  }, [follow, granularity, mergeMarkers, viewRange]);

  const chartQuery = useSnowballNetChart({
    taskId,
    taskType,
    executionRunId,
    params: queryParams,
    enabled: Boolean(taskId),
    refetchInterval:
      enableRealTimeUpdates && refreshSeconds > 0
        ? refreshSeconds * 1000
        : false,
  });

  const data = chartQuery.data ?? null;

  useEffect(() => {
    granularityRef.current = granularity;
    lastRequestedRangeRef.current = null;
  }, [granularity]);

  const scheduleVisibleRangeLoad = useCallback((range: ChartTimeRange) => {
    visibleRangeRef.current = range;
    setFollow(false);

    if (rangeFetchTimerRef.current !== null) {
      window.clearTimeout(rangeFetchTimerRef.current);
    }
    rangeFetchTimerRef.current = window.setTimeout(() => {
      rangeFetchTimerRef.current = null;
      const currentRange = visibleRangeRef.current;
      if (!currentRange) return;

      const loaded = loadedWindowRef.current;
      const currentGranularity = granularityRef.current;
      if (
        !shouldFetchForVisibleRange(currentRange, loaded, currentGranularity)
      ) {
        return;
      }

      const toleranceSeconds = loaded?.step ?? 1;
      if (
        rangesClose(
          currentRange,
          lastRequestedRangeRef.current,
          toleranceSeconds
        )
      ) {
        return;
      }
      lastRequestedRangeRef.current = currentRange;
      setViewRange(currentRange);
    }, SCROLL_FETCH_DEBOUNCE_MS);
  }, []);

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
      programmaticRangeRef.current = true;
    }

    if (!chartRef.current) {
      const { upColor, downColor } = getCandleColors();
      const chart = createChart(host, {
        height: ohlcChartHeightRef.current,
        width: Math.max(1, host.clientWidth),
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
          borderColor: isDark ? '#2a2e39' : '#cbd5e1',
          timeVisible: true,
          secondsVisible: false,
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

      chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
        if (!range || programmaticRangeRef.current) return;
        const normalizedRange = normalizeChartRange(range);
        if (normalizedRange) {
          scheduleVisibleRangeLoad(normalizedRange);
        }
      });

      const observer = new ResizeObserver(() => {
        const width = Math.floor(host.clientWidth);
        if (width > 0) chart.applyOptions({ width });
      });
      observer.observe(host);
      observerRef.current = observer;
    }

    chartRef.current.applyOptions({ height: ohlcChartHeightRef.current });

    const windowRange = candleBucketRange(data);
    if (windowRange) {
      loadedWindowRef.current = {
        granularity: data.window.granularity,
        step: windowRange.step,
        from: windowRange.since,
        to: windowRange.until,
      };
    }

    const rangeToRestore = !follow
      ? normalizeChartRange(chartRef.current?.timeScale().getVisibleRange())
      : null;
    if (rangeToRestore) {
      programmaticRangeRef.current = true;
      visibleRangeRef.current = rangeToRestore;
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

    if (rangeToRestore && chartRef.current) {
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
      chartRef.current.timeScale().setVisibleRange({
        from: (center - span) as Time,
        to: (center + span) as Time,
      });
      releaseProgrammaticRangeFlag(programmaticRangeRef);
    }
  }, [
    applyOhlcOverlays,
    chartSettings,
    data,
    destroyChart,
    follow,
    isDark,
    noDataRegionStyle,
    scheduleVisibleRangeLoad,
    t,
    timezone,
    updateMarginAxisLabel,
    updatePriceAxisLabels,
  ]);

  const handleFollow = useCallback(() => {
    if (rangeFetchTimerRef.current !== null) {
      window.clearTimeout(rangeFetchTimerRef.current);
      rangeFetchTimerRef.current = null;
    }
    visibleRangeRef.current = null;
    lastRequestedRangeRef.current = null;
    setFollow(true);
    setViewRange(null);
    void chartQuery.refetch();
  }, [chartQuery]);

  const handleRefresh = useCallback(() => {
    void chartQuery.refetch();
  }, [chartQuery]);

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

  return (
    <Box sx={{ p: { xs: 1, sm: 2 }, minWidth: 0 }}>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={1}
        alignItems={{ xs: 'stretch', md: 'center' }}
        sx={{ mb: 1.5 }}
      >
        <ToggleButtonGroup
          value={granularity}
          exclusive
          onChange={(_, value) => value && setGranularity(value)}
          size="small"
        >
          {GRANULARITIES.map((option) => (
            <ToggleButton
              key={option}
              value={option}
              sx={{ px: 1.2, py: 0.25 }}
            >
              {option}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
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
        <Tooltip title={t('common:actions.refresh')}>
          <IconButton
            onClick={handleRefresh}
            size="small"
            aria-label={t('common:actions.refresh')}
          >
            <RefreshIcon fontSize="small" />
          </IconButton>
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
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel id="snowball-net-refresh-label">
            {t('strategy:snowballNet.chart.controls.refreshInterval')}
          </InputLabel>
          <Select
            labelId="snowball-net-refresh-label"
            value={String(refreshSeconds)}
            label={t('strategy:snowballNet.chart.controls.refreshInterval')}
            onChange={(event) => setRefreshSeconds(Number(event.target.value))}
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
        <CurrentChips data={data} instrument={instrument} />
      </Stack>

      <SnowballNetChartSettingsDialog
        open={settingsOpen}
        settings={chartSettings}
        onClose={() => setSettingsOpen(false)}
        onChange={updateChartSettings}
      />

      {chartSettings.charts.ohlc ? (
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
                height: ohlcChartHeight,
                minHeight: MIN_OHLC_CHART_HEIGHT,
              }}
            />
          ) : (
            <Alert severity="info">{t('metrics.noData')}</Alert>
          )}
        </Paper>
      ) : null}

      {chartSettings.charts.ohlc && data ? (
        <Box
          role="separator"
          aria-label={t('strategy:snowballNet.chart.resizeOhlcChart')}
          aria-orientation="horizontal"
          aria-valuemin={MIN_OHLC_CHART_HEIGHT}
          aria-valuemax={MAX_OHLC_CHART_HEIGHT}
          aria-valuenow={ohlcChartHeight}
          tabIndex={0}
          onPointerDown={handleOhlcResizePointerDown}
          onKeyDown={handleOhlcResizeKeyDown}
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

      {data ? (
        <SnowballNetLineCharts
          data={data}
          settings={chartSettings}
          timezone={timezone}
        />
      ) : null}
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
  const suffix = instrument ? ` ${instrument.split('_')[0] ?? ''}` : '';
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

function SnowballNetLineCharts({
  data,
  settings,
  timezone,
}: {
  data: SnowballNetChartResponse;
  settings: SnowballNetChartSettings;
  timezone: string;
}) {
  const { t } = useTranslation('strategy');
  const timeDomain = chartTimeDomain(data);
  const pnlCurrency = pnlCurrencyCode(data);
  const priceCurrency = quoteCurrencyFromInstrument(data.instrument);
  const cards = [
    settings.charts.netUnits ? (
      <LineChartCard
        key="net-units"
        title={t('snowballNet.chart.netUnits')}
        lines={netUnitsChartLines(data.oscillator_lines)}
        timezone={timezone}
        timeDomain={timeDomain}
        showWhenEmpty
      />
    ) : null,
    settings.charts.pips ? (
      <LineChartCard
        key="pips"
        title={t('snowballNet.chart.pipsFromAverage')}
        lines={pipsChartLines(data.oscillator_lines)}
        timezone={timezone}
        timeDomain={timeDomain}
        showWhenEmpty
      />
    ) : null,
    settings.charts.margin ? (
      <LineChartCard
        key="margin"
        title={t('snowballNet.chart.marginRatio')}
        lines={marginChartLines(data.oscillator_lines)}
        timezone={timezone}
        timeDomain={timeDomain}
        percent
      />
    ) : null,
    settings.charts.pnl ? (
      <LineChartCard
        key="pnl"
        title={appendUnitLabel(t('snowballNet.chart.pnl'), pnlCurrency)}
        lines={pnlChartLines(data.oscillator_lines)}
        timezone={timezone}
        timeDomain={timeDomain}
        valueUnit={pnlCurrency}
        seriesLabelUnit={pnlCurrency}
      />
    ) : null,
    settings.charts.averagePrice ? (
      <LineChartCard
        key="average"
        title={appendUnitLabel(
          t('snowballNet.chart.averagePrice'),
          priceCurrency
        )}
        lines={priceChartLines(data.price_lines, 'averagePrice')}
        timezone={timezone}
        timeDomain={timeDomain}
      />
    ) : null,
    settings.charts.takeProfit ? (
      <LineChartCard
        key="take-profit"
        title={appendUnitLabel(
          t('snowballNet.chart.takeProfit'),
          priceCurrency
        )}
        lines={priceChartLines(data.price_lines, 'takeProfit')}
        timezone={timezone}
        timeDomain={timeDomain}
      />
    ) : null,
    settings.charts.nextAdd ? (
      <LineChartCard
        key="next-add"
        title={appendUnitLabel(t('snowballNet.chart.nextAdd'), priceCurrency)}
        lines={priceChartLines(data.price_lines, 'nextAdd')}
        timezone={timezone}
        timeDomain={timeDomain}
      />
    ) : null,
  ].filter(Boolean);

  if (cards.length === 0) return null;

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
      {cards}
    </Box>
  );
}

function LineChartCard({
  title,
  lines,
  timezone,
  timeDomain,
  showWhenEmpty = false,
  percent = false,
  valueUnit,
  seriesLabelUnit,
}: {
  title: string;
  lines: SnowballNetLineSeries[];
  timezone: string;
  timeDomain?: LineChartTimeDomain;
  showWhenEmpty?: boolean;
  percent?: boolean;
  valueUnit?: string | null;
  seriesLabelUnit?: string | null;
}) {
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

  return (
    <Paper variant="outlined" sx={{ p: 1, minWidth: 0, minHeight: 220 }}>
      <Stack
        direction="row"
        spacing={0.75}
        useFlexGap
        flexWrap="wrap"
        alignItems="center"
        sx={{ mb: 0.5 }}
      >
        <Typography variant="subtitle2">{title}</Typography>
        {thresholdChips.map(({ line, point }) => (
          <Chip
            key={line.id}
            size="small"
            sx={{ height: 20 }}
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
      <Box sx={{ position: 'relative' }}>
        <LineChart
          xAxis={[
            {
              data: x,
              scaleType: 'time',
              tickNumber: 6,
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
              min: isEmpty ? 0 : undefined,
              max: isEmpty ? 1 : undefined,
              tickLabelStyle: { fontSize: 10 },
              valueFormatter: (value: number) =>
                percent
                  ? `${formatAppNumber(value, { maximumFractionDigits: 1 })}%`
                  : formatNumberWithUnit(value, valueUnit, {
                      maximumFractionDigits: valueUnit ? 2 : 1,
                    }),
            },
          ]}
          series={series}
          height={170}
          margin={{ left: 8, right: valueUnit ? 76 : 52, top: 4, bottom: 34 }}
          grid={{ vertical: true, horizontal: true }}
          hideLegend={visible.length <= 1}
        />
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
  onClose,
  onChange,
}: {
  open: boolean;
  settings: SnowballNetChartSettings;
  onClose: () => void;
  onChange: (
    updater: (current: SnowballNetChartSettings) => SnowballNetChartSettings
  ) => void;
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
