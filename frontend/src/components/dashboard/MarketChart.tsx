import { useEffect, useRef, useCallback, useState } from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
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
import { api } from '../../api/apiClient';
import type { Granularity } from '../../types/chart';
import { detectMarketGaps } from '../../utils/marketClosedMarkers';
import { MarketClosedHighlight } from '../../utils/MarketClosedHighlight';
import {
  AdaptiveTimeScale,
  createSuppressedTickMarkFormatter,
  createTooltipTimeFormatter,
} from '../../utils/adaptiveTimeScalePlugin';
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

function parseCandles(raw: unknown): CandlePoint[] {
  const arr = Array.isArray(raw) ? raw : [];
  const byTime = new Map<number, CandlePoint>();

  for (const c of arr) {
    if (!c || typeof c !== 'object') continue;
    const rec = c as Record<string, unknown>;
    const timeVal = rec.time;
    let ts: number;
    if (typeof timeVal === 'number') {
      ts = timeVal;
    } else if (typeof timeVal === 'string') {
      const parsed = Date.parse(timeVal);
      if (Number.isNaN(parsed)) continue;
      ts = Math.floor(parsed / 1000);
    } else {
      continue;
    }
    const open = Number(rec.open);
    const high = Number(rec.high);
    const low = Number(rec.low);
    const close = Number(rec.close);
    if ([open, high, low, close].some((v) => Number.isNaN(v))) continue;
    const volume = rec.volume !== undefined ? Number(rec.volume) : undefined;
    byTime.set(ts, {
      time: ts as UTCTimestamp,
      open,
      high,
      low,
      close,
      volume,
    });
  }

  return Array.from(byTime.values()).sort(
    (a, b) => Number(a.time) - Number(b.time)
  );
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
  const loadingMoreRef = useRef(false);
  const initialLoadDoneRef = useRef(false);
  const noMoreOlderRef = useRef(false);
  const noMoreNewerRef = useRef(false);
  const fetchMoreRef = useRef<
    ((direction: 'older' | 'newer') => Promise<void>) | null
  >(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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

  // ── Fetch additional candles when scrolling ──────────────────────
  const fetchMore = useCallback(
    async (direction: 'older' | 'newer') => {
      if (loadingMoreRef.current) return;
      const candles = candlesRef.current;
      if (candles.length === 0) return;
      if (direction === 'older' && noMoreOlderRef.current) return;
      if (direction === 'newer' && noMoreNewerRef.current) return;

      loadingMoreRef.current = true;
      try {
        const params: Record<string, string | number> = {
          instrument,
          granularity,
          count: 500,
        };
        if (accountId) params.account_id = accountId;

        if (direction === 'older') {
          // Use the earliest candle's timestamp as the "before" boundary
          params.before = Number(candles[0].time);
        } else {
          // Use the latest candle's timestamp as the "after" boundary
          params.after = Number(candles[candles.length - 1].time);
        }

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const response = await api.get<any>('/api/market/candles/', params);
        const newCandles = parseCandles(response?.candles);

        if (newCandles.length === 0) {
          if (direction === 'older') noMoreOlderRef.current = true;
          else noMoreNewerRef.current = true;
          return;
        }

        // Merge with existing candles, dedup by time
        const existing = candlesRef.current;
        const byTime = new Map<number, CandlePoint>();
        for (const c of existing) byTime.set(Number(c.time), c);
        for (const c of newCandles) byTime.set(Number(c.time), c);
        const merged = Array.from(byTime.values()).sort(
          (a, b) => Number(a.time) - Number(b.time)
        );
        candlesRef.current = merged;

        if (seriesRef.current) {
          seriesRef.current.setData(merged);
          const times = merged.map((c) => Number(c.time));
          if (highlightRef.current) {
            highlightRef.current.setGaps(detectMarketGaps(times));
          }
          applyOverlays();
        }
      } catch {
        // Silently ignore fetch-more errors to avoid disrupting the UX
      } finally {
        loadingMoreRef.current = false;
      }
    },
    [instrument, granularity, accountId, applyOverlays]
  );

  // Keep a stable ref so the chart effect doesn't need to depend on fetchMore
  fetchMoreRef.current = fetchMore;

  const fetchData = useCallback(async () => {
    noMoreOlderRef.current = false;
    noMoreNewerRef.current = false;
    const isInitial = !initialLoadDoneRef.current;
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const response = await api.get<any>('/api/market/candles/', {
        instrument,
        account_id: accountId,
        count: 500,
        granularity,
      });
      const candles = parseCandles(response?.candles);
      candlesRef.current = candles;
      if (seriesRef.current) {
        seriesRef.current.setData(candles);
        const times = candles.map((c) => Number(c.time));
        if (highlightRef.current) {
          highlightRef.current.setGaps(detectMarketGaps(times));
        }
        // Only fit content on the very first load — auto-refresh should
        // preserve the current zoom / scroll position.
        if (isInitial) {
          chartRef.current?.timeScale().fitContent();
          initialLoadDoneRef.current = true;
        }
        applyOverlays();
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load market data');
    } finally {
      setIsLoading(false);
    }
  }, [instrument, granularity, accountId, applyOverlays]);

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
        textColor: isDark ? '#d1d4dc' : '#334155',
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

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#16a34a',
      downColor: '#ef4444',
      wickUpColor: '#16a34a',
      wickDownColor: '#ef4444',
      borderUpColor: '#16a34a',
      borderDownColor: '#ef4444',
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const highlight = new MarketClosedHighlight();
    series.attachPrimitive(highlight);
    highlightRef.current = highlight;

    const adaptive = new AdaptiveTimeScale({ timezone });
    series.attachPrimitive(adaptive);
    adaptiveRef.current = adaptive;

    // ── Scroll-based lazy loading ──
    // When the user scrolls so that the visible logical range extends
    // beyond the loaded data, fetch more candles.
    const EDGE_THRESHOLD = 5; // trigger when within 5 bars of the edge
    let scrollDebounce: ReturnType<typeof setTimeout> | null = null;

    const onVisibleRangeChange = () => {
      if (scrollDebounce) clearTimeout(scrollDebounce);
      scrollDebounce = setTimeout(() => {
        const logicalRange = chart.timeScale().getVisibleLogicalRange();
        if (!logicalRange) return;
        const data = series.data();
        if (!data || data.length === 0) return;

        // logicalRange.from < EDGE_THRESHOLD means user scrolled to the left edge
        if (logicalRange.from < EDGE_THRESHOLD) {
          fetchMoreRef.current?.('older');
        }
        // logicalRange.to > data.length - EDGE_THRESHOLD means user scrolled to the right edge
        if (logicalRange.to > data.length - EDGE_THRESHOLD) {
          fetchMoreRef.current?.('newer');
        }
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
  }, [height, fillHeight, granularity, timezone, isDark]);

  // Fetch data when instrument/granularity changes
  useEffect(() => {
    initialLoadDoneRef.current = false;
    setIsLoading(true);
    fetchData();
  }, [fetchData]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh || refreshInterval <= 0) return;
    const id = setInterval(fetchData, refreshInterval * 1000);
    return () => clearInterval(id);
  }, [autoRefresh, refreshInterval, fetchData]);

  if (error && !seriesRef.current) {
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
          fontSize: '12px',
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          color: isDark ? '#d1d4dc' : '#334155',
          backgroundColor: isDark
            ? 'rgba(30,34,45,0.9)'
            : 'rgba(255,255,255,0.85)',
          padding: '4px 8px',
          borderRadius: '4px',
          pointerEvents: 'none',
          whiteSpace: 'nowrap',
        }}
      />

      {isLoading && (
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
    </Box>
  );
}
