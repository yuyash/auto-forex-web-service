import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Box,
  Chip,
  CircularProgress,
  LinearProgress,
  Typography,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import type {
  IChartApi,
  ISeriesApi,
  Time,
  UTCTimestamp,
} from 'lightweight-charts';
import { useAuth } from '../../contexts/AuthContext';
import { useWindowedCandles } from '../../hooks/useWindowedCandles';
import type { Granularity } from '../../types/chart';
import { AdaptiveTimeScale } from '../../utils/adaptiveTimeScalePlugin';
import { getTimezoneAbbr } from '../../utils/chartTimezone';
import { MarketClosedHighlight } from '../../utils/MarketClosedHighlight';
import { detectMarketGaps } from '../../utils/marketClosedMarkers';
import { MarketChartTooltip } from './MarketChartTooltip';
import {
  DEFAULT_OVERLAY_SETTINGS,
  type OverlaySettings,
} from './chartOverlaySettings';
import { useMarketChartLifecycle } from './useMarketChartLifecycle';
import { useMarketChartOverlays } from './useMarketChartOverlays';
import { useMarketChartTooltip } from './useMarketChartTooltip';
import { useMarketChartViewportLoading } from './useMarketChartViewportLoading';

interface MarketChartProps {
  instrument: string;
  granularity: Granularity;
  accountId?: string;
  height?: number;
  fillHeight?: boolean;
  autoRefresh?: boolean;
  refreshInterval?: number;
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
  const previousFirstCandleTimeRef = useRef<number | null>(null);
  const [overlaysInternal, setOverlaysInternal] = useState<OverlaySettings>(
    DEFAULT_OVERLAY_SETTINGS
  );
  const overlays = overlaysProp ?? overlaysInternal;

  void setOverlaysInternal;

  const { user } = useAuth();
  const muiTheme = useTheme();
  const isDark = muiTheme.palette.mode === 'dark';
  const timezone = user?.timezone || 'UTC';
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
    candlesRef.current = candles.map((candle) => ({
      ...candle,
      time: candle.time as UTCTimestamp,
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

  useEffect(() => {
    applyOverlays(
      chartRef.current,
      seriesRef.current,
      candlesRef.current,
      overlays
    );
  }, [applyOverlays, overlays]);

  useMarketChartLifecycle({
    containerRef,
    chartRef,
    seriesRef,
    highlightRef,
    adaptiveRef,
    candlesRef,
    granularity,
    timezone,
    isDark,
    height,
    fillHeight,
    overlays,
    applyOverlays,
    clearOverlays,
    onVisibleRangeChange: maybeFetchEdgeData,
  });

  useMarketChartTooltip({
    chartRef,
    seriesRef,
    tooltipRef,
    candlesRef,
  });

  useEffect(() => {
    if (!seriesRef.current) return;

    const savedLogicalRange = initialLoadDoneRef.current
      ? chartRef.current?.timeScale().getVisibleLogicalRange()
      : null;

    seriesRef.current.setData(candlesRef.current);
    const times = candlesRef.current.map((candle) => Number(candle.time));
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
          ? candlesRef.current.filter(
              (candle) => Number(candle.time) < previousFirst
            ).length
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
    applyOverlays,
    candles,
    dataRanges,
    granularity,
    overlays,
    restoreVisibleLogicalRange,
    timezone,
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
      <MarketChartTooltip isDark={isDark} tooltipRef={tooltipRef} />

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
