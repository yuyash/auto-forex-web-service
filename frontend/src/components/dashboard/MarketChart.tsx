import { useEffect, useRef, useCallback, useState } from 'react';
import {
  Box,
  Chip,
  CircularProgress,
  LinearProgress,
  Typography,
} from '@mui/material';
import { getCandleColors } from '../../utils/candleColors';
import {
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type Time,
  type UTCTimestamp,
  type SeriesMarker,
} from 'lightweight-charts';
import type { Granularity } from '../../types/chart';
import { detectMarketGaps } from '../../utils/marketClosedMarkers';
import { MarketClosedHighlight } from '../../utils/MarketClosedHighlight';
import {
  AdaptiveTimeScale,
  createSuppressedTickMarkFormatter,
  createTooltipTimeFormatter,
} from '../../utils/adaptiveTimeScalePlugin';
import { getTimezoneAbbr } from '../../utils/chartTimezone';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '@mui/material/styles';
import {
  calcSMA,
  calcEMA,
  calcBollinger,
  detectSupportResistance,
} from '../../utils/technicalIndicators';
import {
  DEFAULT_OVERLAY_SETTINGS,
  type OverlaySettings,
} from './chartOverlaySettings';
import { useWindowedCandles } from '../../hooks/useWindowedCandles';

/** Granularities where showing seconds on the crosshair makes sense */
const SECONDS_GRANULARITIES = new Set<string>(['M1', 'M2', 'M4', 'M5']);

interface MarketChartProps {
  instrument: string;
  granularity: Granularity;
  accountId?: string;
  /** Fixed height in px. Ignored when `fillHeight` is true. */
  height?: number;
  /** When true the chart stretches to fill its container's height. */
  fillHeight?: boolean;
  autoRefresh?: boolean;
  refreshInterval?: number; // in seconds
  /** Overlay settings controlled by parent */
  overlays?: OverlaySettings;
}

interface CandlePoint {
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

/** Overlay series color palette */
const COLORS = {
  sma20: '#2196F3',
  sma50: '#FF9800',
  ema12: '#9C27B0',
  ema26: '#00BCD4',
  bbMiddle: '#607D8B',
  bbBand: 'rgba(96,125,139,0.18)',
  volumeUp: 'rgba(22,163,74,0.35)',
  volumeDown: 'rgba(239,68,68,0.35)',
  support: '#16a34a',
  resistance: '#ef4444',
};

/** Detect simple crossover markers between two line series */
function detectCrossovers(
  fast: { time: number; value: number }[],
  slow: { time: number; value: number }[]
): SeriesMarker<Time>[] {
  const markers: SeriesMarker<Time>[] = [];
  const slowMap = new Map(slow.map((p) => [p.time, p.value]));
  let prevDiff: number | null = null;

  for (const fp of fast) {
    const sv = slowMap.get(fp.time);
    if (sv === undefined) continue;
    const diff = fp.value - sv;
    if (prevDiff !== null) {
      if (prevDiff <= 0 && diff > 0) {
        markers.push({
          time: fp.time as UTCTimestamp as Time,
          position: 'belowBar',
          color: '#16a34a',
          shape: 'arrowUp',
          text: 'Buy',
        });
      } else if (prevDiff >= 0 && diff < 0) {
        markers.push({
          time: fp.time as UTCTimestamp as Time,
          position: 'aboveBar',
          color: '#ef4444',
          shape: 'arrowDown',
          text: 'Sell',
        });
      }
    }
    prevDiff = diff;
  }
  return markers;
}

export default function MarketChart({
  instrument,
  granularity,
  accountId,
  height = 500,
  fillHeight = false,
  autoRefresh = false,
  refreshInterval = 60,
  overlays: overlaysProp,
}: MarketChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick', Time> | null>(null);
  const highlightRef = useRef<MarketClosedHighlight | null>(null);
  const adaptiveRef = useRef<AdaptiveTimeScale | null>(null);

  // Overlay series refs
  const sma20Ref = useRef<ISeriesApi<'Line', Time> | null>(null);
  const sma50Ref = useRef<ISeriesApi<'Line', Time> | null>(null);
  const ema12Ref = useRef<ISeriesApi<'Line', Time> | null>(null);
  const ema26Ref = useRef<ISeriesApi<'Line', Time> | null>(null);
  const bbMiddleRef = useRef<ISeriesApi<'Line', Time> | null>(null);
  const bbUpperRef = useRef<ISeriesApi<'Line', Time> | null>(null);
  const bbLowerRef = useRef<ISeriesApi<'Line', Time> | null>(null);
  const volumeRef = useRef<ISeriesApi<'Histogram', Time> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const candlesRef = useRef<CandlePoint[]>([]);
  const initialLoadDoneRef = useRef(false);
  const [overlaysInternal, setOverlaysInternal] = useState<OverlaySettings>(
    DEFAULT_OVERLAY_SETTINGS
  );
  const overlays = overlaysProp ?? overlaysInternal;
  // Keep setOverlays for potential internal use; parent controls take precedence
  void setOverlaysInternal;
  const { user } = useAuth();
  const muiTheme = useTheme();
  const isDark = muiTheme.palette.mode === 'dark';
  const timezone = user?.timezone || 'UTC';
  const previousFirstCandleTimeRef = useRef<number | null>(null);
  const {
    candles,
    isInitialLoading,
    isRefreshing,
    loadingOlder,
    loadingNewer,
    error,
    ensureRange,
    refreshTail,
  } = useWindowedCandles({
    instrument,
    granularity,
    accountId,
    initialCount: 500,
    edgeCount: 500,
    autoRefresh,
    refreshIntervalSeconds: refreshInterval,
  });

  useEffect(() => {
    candlesRef.current = candles.map((c) => ({
      ...c,
      time: c.time as UTCTimestamp,
    }));
  }, [candles]);

  // ── Apply overlays whenever settings or data change ──────────────
  const applyOverlays = useCallback(() => {
    const chart = chartRef.current;
    const mainSeries = seriesRef.current;
    const candles = candlesRef.current;
    if (!chart || !mainSeries || candles.length === 0) return;

    const asTime = (pts: { time: number; value: number }[]) =>
      pts.map((p) => ({
        time: p.time as UTCTimestamp as Time,
        value: p.value,
      }));

    // ── SMA 20 ──
    if (overlays.sma20) {
      if (!sma20Ref.current) {
        sma20Ref.current = chart.addSeries(LineSeries, {
          color: COLORS.sma20,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
      }
      sma20Ref.current.setData(asTime(calcSMA(candles, 20)));
    } else if (sma20Ref.current) {
      chart.removeSeries(sma20Ref.current);
      sma20Ref.current = null;
    }

    // ── SMA 50 ──
    if (overlays.sma50) {
      if (!sma50Ref.current) {
        sma50Ref.current = chart.addSeries(LineSeries, {
          color: COLORS.sma50,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
      }
      sma50Ref.current.setData(asTime(calcSMA(candles, 50)));
    } else if (sma50Ref.current) {
      chart.removeSeries(sma50Ref.current);
      sma50Ref.current = null;
    }

    // ── EMA 12 ──
    if (overlays.ema12) {
      if (!ema12Ref.current) {
        ema12Ref.current = chart.addSeries(LineSeries, {
          color: COLORS.ema12,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
      }
      ema12Ref.current.setData(asTime(calcEMA(candles, 12)));
    } else if (ema12Ref.current) {
      chart.removeSeries(ema12Ref.current);
      ema12Ref.current = null;
    }

    // ── EMA 26 ──
    if (overlays.ema26) {
      if (!ema26Ref.current) {
        ema26Ref.current = chart.addSeries(LineSeries, {
          color: COLORS.ema26,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
      }
      ema26Ref.current.setData(asTime(calcEMA(candles, 26)));
    } else if (ema26Ref.current) {
      chart.removeSeries(ema26Ref.current);
      ema26Ref.current = null;
    }

    // ── Bollinger Bands ──
    if (overlays.bollinger) {
      const bb = calcBollinger(candles, 20, 2);
      if (!bbMiddleRef.current) {
        bbMiddleRef.current = chart.addSeries(LineSeries, {
          color: COLORS.bbMiddle,
          lineWidth: 1,
          lineStyle: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        bbUpperRef.current = chart.addSeries(LineSeries, {
          color: COLORS.bbMiddle,
          lineWidth: 1,
          lineStyle: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        bbLowerRef.current = chart.addSeries(LineSeries, {
          color: COLORS.bbMiddle,
          lineWidth: 1,
          lineStyle: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
      }
      bbMiddleRef.current.setData(asTime(bb.middle));
      bbUpperRef.current!.setData(asTime(bb.upper));
      bbLowerRef.current!.setData(asTime(bb.lower));
    } else {
      for (const ref of [bbMiddleRef, bbUpperRef, bbLowerRef]) {
        if (ref.current) {
          chart.removeSeries(ref.current);
          ref.current = null;
        }
      }
    }

    // ── Volume ──
    if (overlays.volume) {
      if (!volumeRef.current) {
        volumeRef.current = chart.addSeries(HistogramSeries, {
          priceFormat: { type: 'volume' },
          priceScaleId: 'volume',
          priceLineVisible: false,
          lastValueVisible: false,
        });
        chart.priceScale('volume').applyOptions({
          scaleMargins: { top: 0.8, bottom: 0 },
        });
      }
      volumeRef.current.setData(
        candles
          .filter((c) => c.volume !== undefined)
          .map((c) => ({
            time: c.time as Time,
            value: c.volume!,
            color: c.close >= c.open ? COLORS.volumeUp : COLORS.volumeDown,
          }))
      );
    } else if (volumeRef.current) {
      chart.removeSeries(volumeRef.current);
      volumeRef.current = null;
    }

    // ── Support / Resistance price lines ──
    // Remove old lines first (lightweight-charts doesn't expose a list, so we recreate)
    // We tag custom lines via the title field
    const existingLines = (mainSeries as unknown as { _priceLines?: unknown[] })
      ._priceLines;
    if (existingLines) {
      // Not accessible — use public API workaround: remove by reference stored in a ref
    }
    // Simpler approach: always recreate
    // We'll store references in a data attribute on the container
    const prevLines = (
      containerRef.current as unknown as {
        __srLines?: ReturnType<typeof mainSeries.createPriceLine>[];
      }
    )?.__srLines;
    if (prevLines) {
      for (const line of prevLines) {
        try {
          mainSeries.removePriceLine(line);
        } catch {
          /* already removed */
        }
      }
    }
    if (overlays.supportResistance) {
      const levels = detectSupportResistance(candles);
      const lines = levels.map((lv) =>
        mainSeries.createPriceLine({
          price: lv.price,
          color: lv.type === 'support' ? COLORS.support : COLORS.resistance,
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: lv.type === 'support' ? 'S' : 'R',
        })
      );
      if (containerRef.current) {
        (
          containerRef.current as unknown as { __srLines: typeof lines }
        ).__srLines = lines;
      }
    }

    // ── Signal markers (EMA crossover) ──
    if (overlays.markers) {
      const fast = calcEMA(candles, 12);
      const slow = calcEMA(candles, 26);
      const markers = detectCrossovers(fast, slow);
      if (!markersRef.current) {
        markersRef.current = createSeriesMarkers(mainSeries, markers);
      } else {
        markersRef.current.setMarkers(markers);
      }
    } else if (markersRef.current) {
      markersRef.current.detach();
      markersRef.current = null;
    }
  }, [overlays]);

  const restoreVisibleLogicalRange = useCallback(
    (saved: { from: number; to: number } | null, prependCount = 0) => {
      if (!saved || !chartRef.current) return;
      try {
        chartRef.current.timeScale().setVisibleLogicalRange({
          from: saved.from + prependCount,
          to: saved.to + prependCount,
        });
      } catch {
        /* no-op */
      }
    },
    []
  );

  const maybeFetchEdgeData = useCallback(async () => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series) return;
    const visibleTimeRange = chart.timeScale().getVisibleRange();
    if (
      visibleTimeRange &&
      typeof visibleTimeRange.from === 'number' &&
      typeof visibleTimeRange.to === 'number'
    ) {
      await ensureRange({
        from: Number(visibleTimeRange.from),
        to: Number(visibleTimeRange.to),
      });
    }
    const logicalRange = chart.timeScale().getVisibleLogicalRange();
    const data = series.data();
    if (!logicalRange || !data || data.length === 0) return;

    const EDGE_THRESHOLD = 5;
    const firstTime = Number(candlesRef.current[0]?.time ?? 0);
    const lastTime = Number(
      candlesRef.current[candlesRef.current.length - 1]?.time ?? 0
    );
    const spanSeconds =
      visibleTimeRange &&
      typeof visibleTimeRange.from === 'number' &&
      typeof visibleTimeRange.to === 'number'
        ? Math.max(
            60,
            Number(visibleTimeRange.to) - Number(visibleTimeRange.from)
          )
        : Math.max(60, lastTime - firstTime);

    if (logicalRange.from < EDGE_THRESHOLD) {
      await ensureRange({
        from: firstTime - spanSeconds,
        to: firstTime,
      });
      return;
    }
    if (logicalRange.to > data.length - EDGE_THRESHOLD) {
      await ensureRange({
        from: lastTime,
        to: lastTime + spanSeconds,
      });
    }
  }, [ensureRange]);

  // Re-apply overlays when toggle changes
  useEffect(() => {
    applyOverlays();
  }, [applyOverlays]);

  // Create chart once
  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    const initialHeight = fillHeight
      ? container.clientHeight || height
      : height;
    const chart = createChart(container, {
      height: initialHeight,
      layout: {
        background: { color: isDark ? '#131722' : '#ffffff' },
        textColor: isDark ? '#ffffff' : '#334155',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: isDark ? '#2a2e39' : '#e2e8f0' },
      },
      rightPriceScale: { borderColor: isDark ? '#2a2e39' : '#cbd5e1' },
      timeScale: {
        borderColor: isDark ? '#2a2e39' : '#cbd5e1',
        timeVisible: true,
        secondsVisible: SECONDS_GRANULARITIES.has(granularity),
        tickMarkFormatter: createSuppressedTickMarkFormatter(),
      },
      localization: {
        timeFormatter: createTooltipTimeFormatter({ timezone }),
      },
      crosshair: {
        vertLine: { labelVisible: true },
        horzLine: { labelVisible: true },
      },
    });

    const { upColor, downColor } = getCandleColors();
    const series = chart.addSeries(CandlestickSeries, {
      upColor,
      downColor,
      wickUpColor: upColor,
      wickDownColor: downColor,
      borderUpColor: upColor,
      borderDownColor: downColor,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const highlight = new MarketClosedHighlight();
    series.attachPrimitive(highlight);
    highlightRef.current = highlight;

    const adaptive = new AdaptiveTimeScale(
      { timezone },
      isDark ? '#ffffff' : '#334155',
      isDark ? '#2a2e39' : '#e2e8f0'
    );
    series.attachPrimitive(adaptive);
    adaptiveRef.current = adaptive;

    // Restore cached data after theme-triggered re-creation
    if (candlesRef.current.length > 0) {
      series.setData(candlesRef.current);
      applyOverlays();
    }

    let scrollDebounce: ReturnType<typeof setTimeout> | null = null;

    const onVisibleRangeChange = () => {
      if (scrollDebounce) clearTimeout(scrollDebounce);
      scrollDebounce = setTimeout(() => {
        void maybeFetchEdgeData();
      }, 300);
    };

    chart.timeScale().subscribeVisibleLogicalRangeChange(onVisibleRangeChange);

    // ── Crosshair tooltip (OHLCV legend in top-left) ──
    chart.subscribeCrosshairMove((param) => {
      const tooltip = tooltipRef.current;
      if (!tooltip) return;
      if (!param.time || !param.seriesData) {
        tooltip.style.display = 'none';
        return;
      }
      const data = param.seriesData.get(series);
      if (!data || !('open' in data)) {
        tooltip.style.display = 'none';
        return;
      }
      const d = data as {
        open: number;
        high: number;
        low: number;
        close: number;
      };
      const change = d.close - d.open;
      const changeColor = change >= 0 ? '#16a34a' : '#ef4444';
      const changeSign = change >= 0 ? '+' : '';
      // Find volume from our cached candles
      const ts = typeof param.time === 'number' ? param.time : 0;
      const candle = candlesRef.current.find((c) => Number(c.time) === ts);
      const volStr =
        candle?.volume !== undefined
          ? `  Vol: ${candle.volume.toLocaleString()}`
          : '';

      tooltip.style.display = 'block';
      tooltip.innerHTML =
        `<span style="color:#64748b">O</span> ${d.open.toFixed(5)}` +
        `  <span style="color:#64748b">H</span> ${d.high.toFixed(5)}` +
        `  <span style="color:#64748b">L</span> ${d.low.toFixed(5)}` +
        `  <span style="color:#64748b">C</span> ${d.close.toFixed(5)}` +
        `  <span style="color:${changeColor}">${changeSign}${change.toFixed(5)}</span>` +
        `<span style="color:#94a3b8">${volStr}</span>`;
    });

    // Responsive resize
    const observer = new ResizeObserver(() => {
      const width = container.clientWidth;
      if (width > 0) chart.applyOptions({ width });
      if (fillHeight) {
        const h = container.clientHeight;
        if (h > 0) chart.applyOptions({ height: h });
      }
    });
    observer.observe(container);
    chart.applyOptions({ width: container.clientWidth });
    if (fillHeight) {
      const h = container.clientHeight;
      if (h > 0) chart.applyOptions({ height: h });
    }

    return () => {
      observer.disconnect();
      chart
        .timeScale()
        .unsubscribeVisibleLogicalRangeChange(onVisibleRangeChange);
      if (scrollDebounce) clearTimeout(scrollDebounce);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      highlightRef.current = null;
      adaptiveRef.current = null;
      sma20Ref.current = null;
      sma50Ref.current = null;
      ema12Ref.current = null;
      ema26Ref.current = null;
      bbMiddleRef.current = null;
      bbUpperRef.current = null;
      bbLowerRef.current = null;
      volumeRef.current = null;
      if (markersRef.current) {
        markersRef.current.detach();
        markersRef.current = null;
      }
    };
    // applyOverlays is intentionally excluded — overlay changes are handled
    // by a dedicated useEffect to avoid recreating the chart on every toggle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [height, fillHeight, granularity, timezone, isDark, maybeFetchEdgeData]);

  useEffect(() => {
    if (!seriesRef.current) return;

    const savedLogicalRange = initialLoadDoneRef.current
      ? chartRef.current?.timeScale().getVisibleLogicalRange()
      : null;

    seriesRef.current.setData(candlesRef.current);
    const times = candlesRef.current.map((c) => Number(c.time));
    if (highlightRef.current) {
      highlightRef.current.setGaps(detectMarketGaps(times));
    }

    if (!initialLoadDoneRef.current) {
      chartRef.current?.timeScale().fitContent();
      initialLoadDoneRef.current = true;
    } else if (savedLogicalRange) {
      const previousFirst = previousFirstCandleTimeRef.current;
      const currentFirst = candlesRef.current[0]
        ? Number(candlesRef.current[0].time)
        : null;
      const prependCount =
        previousFirst != null &&
        currentFirst != null &&
        currentFirst < previousFirst
          ? candlesRef.current.filter((c) => Number(c.time) < previousFirst)
              .length
          : 0;
      restoreVisibleLogicalRange(savedLogicalRange, prependCount);
    }

    previousFirstCandleTimeRef.current = candlesRef.current[0]
      ? Number(candlesRef.current[0].time)
      : null;
    applyOverlays();
  }, [candles, applyOverlays, restoreVisibleLogicalRange]);

  useEffect(() => {
    initialLoadDoneRef.current = false;
  }, [instrument, granularity]);

  useEffect(() => {
    if (!autoRefresh) return;
    void refreshTail();
  }, [autoRefresh, refreshTail]);

  if (error && !seriesRef.current && candles.length === 0) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: fillHeight ? '100%' : height,
        }}
      >
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        position: 'relative',
        width: '100%',
        ...(fillHeight && { height: '100%' }),
      }}
    >
      {/* OHLCV tooltip legend (top-left) */}
      <div
        ref={tooltipRef}
        style={{
          position: 'absolute',
          top: 8,
          left: 8,
          zIndex: 2,
          display: 'none',
          fontSize: '11px',
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          color: isDark ? '#ffffff' : '#334155',
          backgroundColor: isDark
            ? 'rgba(30,34,45,0.9)'
            : 'rgba(255,255,255,0.85)',
          padding: '4px 8px',
          borderRadius: '4px',
          pointerEvents: 'none',
          whiteSpace: 'normal',
          maxWidth: 'calc(100% - 16px)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      />

      {(loadingOlder || loadingNewer) && (
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 3,
            display: 'flex',
            gap: 1,
            px: 1,
            pt: 0.5,
          }}
        >
          <Box
            sx={{ flex: 1, visibility: loadingOlder ? 'visible' : 'hidden' }}
          >
            <LinearProgress color="inherit" />
          </Box>
          <Box
            sx={{ flex: 1, visibility: loadingNewer ? 'visible' : 'hidden' }}
          >
            <LinearProgress color="inherit" />
          </Box>
        </Box>
      )}

      {(isRefreshing || error) && (
        <Box
          sx={{
            position: 'absolute',
            top: 8,
            right: 8,
            zIndex: 3,
            display: 'flex',
            gap: 1,
          }}
        >
          {isRefreshing && <Chip size="small" label="Syncing candles" />}
          {error && <Chip size="small" color="error" label={error} />}
        </Box>
      )}

      {isInitialLoading && (
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1,
            backgroundColor: isDark
              ? 'rgba(19,23,34,0.7)'
              : 'rgba(255,255,255,0.7)',
          }}
        >
          <CircularProgress size={32} />
        </Box>
      )}
      <div
        ref={containerRef}
        style={{ width: '100%', ...(fillHeight ? { height: '100%' } : {}) }}
      />

      {/* Timezone indicator (bottom-right) */}
      <div
        style={{
          position: 'absolute',
          bottom: 8,
          right: 8,
          zIndex: 2,
          fontSize: '11px',
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          color: isDark ? 'rgba(255,255,255,0.45)' : 'rgba(51,65,85,0.5)',
          pointerEvents: 'none',
          userSelect: 'none',
        }}
      >
        TZ: {getTimezoneAbbr(timezone)}
      </div>
    </Box>
  );
}
