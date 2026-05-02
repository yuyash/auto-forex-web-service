import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MutableRefObject,
} from 'react';
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  FormControl,
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
import TimelineIcon from '@mui/icons-material/Timeline';
import type { CanvasRenderingTarget2D } from 'fancy-canvas';
import {
  CandlestickSeries,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type CandlestickData,
  type IChartApi,
  type IPrimitivePaneRenderer,
  type IPrimitivePaneView,
  type ISeriesApi,
  type ISeriesPrimitive,
  type SeriesAttachedParameter,
  type Time,
  type WhitespaceData,
} from 'lightweight-charts';
import { LineChart } from '@mui/x-charts/LineChart';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
import { useSnowballNetChart } from '../../../../hooks/useStrategyData';
import type { TaskType } from '../../../../types/common';
import type {
  SnowballNetChartResponse,
  SnowballNetLineSeries,
  SnowballNetMarker,
} from '../../../../types/strategyVisualization';
import {
  AdaptiveTimeScale,
  createSuppressedTickMarkFormatter,
  createTooltipTimeFormatter,
} from '../../../../utils/adaptiveTimeScalePlugin';
import { getCandleColors } from '../../../../utils/candleColors';
import { SequencePositionLine } from '../../../../utils/SequencePositionLine';
import {
  formatAppNumber,
  formatAppPercent,
} from '../../../../utils/numberFormat';

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

interface NoDataRegion {
  from: number;
  to: number;
}

interface NoDataRegionStyle {
  fill: string;
  stroke: string;
  text: string;
}

interface CandleBucketRange {
  step: number;
  firstBucket: number;
  lastBucket: number;
}

function toNumber(value: unknown): number | null {
  if (value == null || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function isoFromSeconds(value: number): string {
  return new Date(value * 1000).toISOString();
}

function markerColor(marker: SnowballNetMarker): string {
  return marker.action === 'open' ? '#16a34a' : '#dc2626';
}

function markerText(marker: SnowballNetMarker): string {
  const base = marker.action === 'open' ? 'Add' : 'Close';
  return marker.count > 1 ? `${base} x${marker.count}` : base;
}

function buildMarkerData(markers: SnowballNetMarker[]) {
  return markers.map((marker) => ({
    time: marker.time as Time,
    position:
      marker.action === 'open' ? ('belowBar' as const) : ('aboveBar' as const),
    color: markerColor(marker),
    shape:
      marker.action === 'open' ? ('arrowUp' as const) : ('arrowDown' as const),
    text: markerText(marker),
  }));
}

function lineLabel(line: SnowballNetLineSeries): string {
  return line.label ?? line.id.replace(/_/g, ' ');
}

function toUnixSeconds(value: string | null | undefined): number | null {
  if (!value) return null;
  const ms = new Date(value).getTime();
  return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
}

function positiveModulo(value: number, divisor: number): number {
  return ((value % divisor) + divisor) % divisor;
}

function candleBucketRange(
  data: SnowballNetChartResponse
): CandleBucketRange | null {
  const step = data.window.granularity_seconds;
  const since = toUnixSeconds(data.window.since);
  const until = toUnixSeconds(data.window.until);
  if (!step || since == null || until == null || since > until) return null;

  const anchor =
    data.candles.length > 0 ? positiveModulo(data.candles[0].time, step) : 0;
  return {
    step,
    firstBucket: Math.floor((since - anchor) / step) * step + anchor,
    lastBucket: Math.floor((until - anchor) / step) * step + anchor,
  };
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

  const byTime = new Map(data.candles.map((candle) => [candle.time, candle]));
  const result: Array<CandlestickData<Time> | WhitespaceData<Time>> = [];
  for (
    let time = bucketRange.firstBucket;
    time <= bucketRange.lastBucket;
    time += bucketRange.step
  ) {
    const candle = byTime.get(time);
    if (candle) {
      result.push({
        time: time as Time,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      });
    } else {
      result.push({ time: time as Time });
    }
  }
  return result;
}

function buildNoDataRegions(data: SnowballNetChartResponse): NoDataRegion[] {
  const bucketRange = candleBucketRange(data);
  if (!bucketRange) return [];

  const candleTimes = new Set(data.candles.map((candle) => candle.time));
  const regions: NoDataRegion[] = [];
  let missingStart: number | null = null;
  let missingCount = 0;
  let lastMissing = bucketRange.firstBucket;

  const flush = (nextTime: number) => {
    if (missingStart == null) return;
    if (missingCount >= MIN_NO_DATA_BUCKETS) {
      regions.push({
        from: missingStart,
        to: nextTime <= bucketRange.lastBucket ? nextTime : lastMissing,
      });
    }
    missingStart = null;
    missingCount = 0;
  };

  for (
    let time = bucketRange.firstBucket;
    time <= bucketRange.lastBucket;
    time += bucketRange.step
  ) {
    if (!candleTimes.has(time)) {
      if (missingStart == null) {
        missingStart = time;
      }
      missingCount += 1;
      lastMissing = time;
      continue;
    }
    flush(time);
  }
  flush(bucketRange.lastBucket + bucketRange.step);
  return regions.filter((region) => region.to > region.from);
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
        ctx.fillText('No Data', left + width / 2, height * 0.5);

        const subFont = Math.round(9 * ratio);
        ctx.font = `500 ${subFont}px sans-serif`;
        ctx.fillText(
          'market closed',
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

  constructor(private readonly style: NoDataRegionStyle) {}

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
  const { t } = useTranslation('common');
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const priceLineRefs = useRef<Map<string, ISeriesApi<'Line'>>>(new Map());
  const markersRef = useRef<ReturnType<
    typeof createSeriesMarkers<Time>
  > | null>(null);
  const observerRef = useRef<ResizeObserver | null>(null);
  const sequenceLineRef = useRef<SequencePositionLine | null>(null);
  const noDataRegionsRef = useRef<NoDataRegionsOverlay | null>(null);
  const programmaticRangeRef = useRef(false);
  const [granularity, setGranularity] = useState<string>(DEFAULT_GRANULARITY);
  const [follow, setFollow] = useState(true);
  const [mergeMarkers, setMergeMarkers] = useState(true);
  const [refreshSeconds, setRefreshSeconds] = useState<number>(15);
  const [viewRange, setViewRange] = useState<{
    from: number;
    to: number;
  } | null>(null);

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

  const destroyChart = useCallback(() => {
    observerRef.current?.disconnect();
    observerRef.current = null;
    sequenceLineRef.current?.clear();
    sequenceLineRef.current = null;
    noDataRegionsRef.current?.clear();
    if (noDataRegionsRef.current && candleSeriesRef.current) {
      candleSeriesRef.current.detachPrimitive(noDataRegionsRef.current);
    }
    noDataRegionsRef.current = null;
    markersRef.current?.detach();
    markersRef.current = null;
    priceLineRefs.current.clear();
    chartRef.current?.remove();
    chartRef.current = null;
    candleSeriesRef.current = null;
  }, []);

  useEffect(() => destroyChart, [destroyChart]);

  useEffect(() => {
    destroyChart();
  }, [destroyChart, isDark]);

  useEffect(() => {
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
        height: 460,
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
      const noDataRegions = new NoDataRegionsOverlay({
        fill: isDark ? 'rgba(148, 163, 184, 0.12)' : 'rgba(100, 116, 139, 0.1)',
        stroke: isDark
          ? 'rgba(148, 163, 184, 0.34)'
          : 'rgba(100, 116, 139, 0.28)',
        text: isDark ? 'rgba(226, 232, 240, 0.72)' : 'rgba(71, 85, 105, 0.72)',
      });
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
        setFollow(false);
        setViewRange({ from: Number(range.from), to: Number(range.to) });
      });

      const observer = new ResizeObserver(() => {
        const width = Math.floor(host.clientWidth);
        if (width > 0) chart.applyOptions({ width });
      });
      observer.observe(host);
      observerRef.current = observer;
    }

    candleSeriesRef.current?.setData(buildContinuousCandleData(data));
    noDataRegionsRef.current?.setRegions(buildNoDataRegions(data));
    markersRef.current?.setMarkers(buildMarkerData(data.markers));

    for (const [id, series] of priceLineRefs.current.entries()) {
      if (!data.price_lines.some((line) => line.id === id)) {
        chartRef.current?.removeSeries(series);
        priceLineRefs.current.delete(id);
      }
    }
    for (const line of data.price_lines) {
      let series = priceLineRefs.current.get(line.id);
      if (!series) {
        series = chartRef.current!.addSeries(LineSeries, {
          color: line.color,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        priceLineRefs.current.set(line.id, series);
      }
      series.setData(
        line.points.map((point) => ({
          time: point.time as Time,
          value: point.value,
        }))
      );
    }

    const currentTimestamp = String(
      data.current.timestamp ?? data.window.center ?? ''
    );
    const currentPrice = toNumber(
      data.current.current_price ?? data.current.mid
    );
    if (currentTimestamp) {
      sequenceLineRef.current?.setPosition(currentTimestamp, currentPrice);
    } else {
      sequenceLineRef.current?.clear();
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
  }, [data, destroyChart, follow, isDark, timezone]);

  const handleFollow = useCallback(() => {
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
          title={follow ? 'Following current tick' : 'Follow current tick'}
        >
          <IconButton
            onClick={handleFollow}
            size="small"
            color={follow ? 'primary' : 'default'}
            aria-label="Follow current tick"
          >
            <CenterFocusStrongIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title={mergeMarkers ? 'Merged markers' : 'Raw markers'}>
          <IconButton
            onClick={() => setMergeMarkers((value) => !value)}
            size="small"
            color={mergeMarkers ? 'primary' : 'default'}
            aria-label="Merge markers"
          >
            <MergeIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Refresh">
          <IconButton onClick={handleRefresh} size="small" aria-label="Refresh">
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel id="snowball-net-refresh-label">Refresh</InputLabel>
          <Select
            labelId="snowball-net-refresh-label"
            value={String(refreshSeconds)}
            label="Refresh"
            onChange={(event) => setRefreshSeconds(Number(event.target.value))}
          >
            {REFRESH_OPTIONS.map((seconds) => (
              <MenuItem key={seconds} value={String(seconds)}>
                {seconds === 0 ? 'Off' : `${seconds}s`}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <CurrentChips data={data} instrument={instrument} />
      </Stack>

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
          <Box ref={containerRef} sx={{ width: '100%', minHeight: 460 }} />
        ) : (
          <Alert severity="info">{t('metrics.noData')}</Alert>
        )}
      </Paper>

      {data ? <OscillatorCharts lines={data.oscillator_lines} /> : null}
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
  if (!data) return null;
  const current = data.current;
  const units = toNumber(current.net_units);
  const avg = toNumber(current.average_price);
  const pips = toNumber(current.pips_from_average);
  const margin = toNumber(current.margin_ratio_pct);
  const price = toNumber(current.current_price ?? current.mid);
  const suffix = instrument ? ` ${instrument.split('_')[0] ?? ''}` : '';
  return (
    <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap">
      <Chip
        size="small"
        label={`Net ${formatAppNumber(units ?? 0)}${suffix}`}
      />
      <Chip
        size="small"
        label={`Avg ${avg != null ? formatAppNumber(avg, { maximumFractionDigits: 5 }) : '-'}`}
      />
      <Chip
        size="small"
        label={`Price ${price != null ? formatAppNumber(price, { maximumFractionDigits: 5 }) : '-'}`}
      />
      <Chip
        size="small"
        color={pips != null && pips >= 0 ? 'success' : 'warning'}
        label={`Pips ${pips != null ? formatAppNumber(pips, { maximumFractionDigits: 1 }) : '-'}`}
      />
      <Chip
        size="small"
        color={margin != null && margin >= 70 ? 'warning' : 'default'}
        label={`Margin ${margin != null ? formatAppPercent(margin, 1) : '-'}`}
      />
    </Stack>
  );
}

function OscillatorCharts({ lines }: { lines: SnowballNetLineSeries[] }) {
  const visible = lines.filter((line) => line.points.length >= 2);
  if (visible.length === 0) return null;
  return (
    <Stack
      direction={{ xs: 'column', lg: 'row' }}
      spacing={1.5}
      sx={{ mt: 1.5 }}
    >
      {visible.map((line) => {
        const x = line.points.map((point) => new Date(point.time * 1000));
        const y = line.points.map((point) => point.value);
        return (
          <Paper
            key={line.id}
            variant="outlined"
            sx={{ p: 1, flex: 1, minWidth: 0, height: 190 }}
          >
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
              {lineLabel(line)}
            </Typography>
            <LineChart
              xAxis={[
                {
                  data: x,
                  scaleType: 'time',
                  tickLabelStyle: { fontSize: 10 },
                },
              ]}
              yAxis={[{ position: 'right', tickLabelStyle: { fontSize: 10 } }]}
              series={[
                {
                  data: y,
                  color: line.color,
                  showMark: false,
                },
              ]}
              height={145}
              margin={{ left: 8, right: 48, top: 4, bottom: 22 }}
              grid={{ vertical: true, horizontal: true }}
              hideLegend
            />
          </Paper>
        );
      })}
    </Stack>
  );
}

export default SnowballNetStrategyTab;
