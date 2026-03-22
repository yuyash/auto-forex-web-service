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
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type UTCTimestamp,
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
  DEFAULT_OVERLAY_SETTINGS,
  type OverlaySettings,
} from './chartOverlaySettings';
import { useWindowedCandles } from '../../hooks/useWindowedCandles';
import { useMarketChartOverlays } from './useMarketChartOverlays';
import { useMarketChartViewportLoading } from './useMarketChartViewportLoading';

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
  const { applyOverlays, clear: clearOverlays } =
    useMarketChartOverlays(containerRef);
  const {
    candles,
    isInitialLoading,
    isRefreshing,
    loadingOlder,
    loadingNewer,
    error,
    dataRanges,
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

  const maybeFetchEdgeData = useMarketChartViewportLoading({
    chartRef,
    seriesRef,
    candlesRef,
    ensureRange,
  });

  // Re-apply overlays when toggle changes
  useEffect(() => {
    applyOverlays(
      chartRef.current,
      seriesRef.current,
      candlesRef.current,
      overlays
    );
  }, [applyOverlays, overlays]);

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
      applyOverlays(chart, series, candlesRef.current, overlays);
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
      clearOverlays();
    };
  }, [
    height,
    fillHeight,
    granularity,
    timezone,
    isDark,
    maybeFetchEdgeData,
    applyOverlays,
    overlays,
    clearOverlays,
  ]);

  useEffect(() => {
    if (!seriesRef.current) return;

    const savedLogicalRange = initialLoadDoneRef.current
      ? chartRef.current?.timeScale().getVisibleLogicalRange()
      : null;

    seriesRef.current.setData(candlesRef.current);
    const times = candlesRef.current.map((c) => Number(c.time));
    if (highlightRef.current) {
      highlightRef.current.setGaps(
        detectMarketGaps(times, granularity, dataRanges, timezone)
      );
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
    applyOverlays(
      chartRef.current,
      seriesRef.current,
      candlesRef.current,
      overlays
    );
  }, [
    candles,
    granularity,
    dataRanges,
    timezone,
    applyOverlays,
    overlays,
    restoreVisibleLogicalRange,
  ]);

  useEffect(() => {
    initialLoadDoneRef.current = false;
  }, [instrument, granularity]);

  useEffect(() => {
    if (!autoRefresh) return;
    void refreshTail();
  }, [autoRefresh, refreshTail]);

  if (error && candles.length === 0) {
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
