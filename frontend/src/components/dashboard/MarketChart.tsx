import { useEffect, useRef, useCallback, useState } from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import {
  CandlestickSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import { MarketService } from '../../api/generated/services/MarketService';
import type { Granularity } from '../../types/chart';
import { detectMarketGaps } from '../../utils/marketClosedMarkers';
import { MarketClosedHighlight } from '../../utils/MarketClosedHighlight';
import {
  AdaptiveTimeScale,
  createSuppressedTickMarkFormatter,
  createTooltipTimeFormatter,
} from '../../utils/adaptiveTimeScalePlugin';
import { useAuth } from '../../contexts/AuthContext';

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
}

interface CandlePoint {
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
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
    byTime.set(ts, { time: ts as UTCTimestamp, open, high, low, close });
  }

  return Array.from(byTime.values()).sort(
    (a, b) => Number(a.time) - Number(b.time)
  );
}

export default function MarketChart({
  instrument,
  granularity,
  accountId,
  height = 500,
  fillHeight = false,
  autoRefresh = false,
  refreshInterval = 60,
}: MarketChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick', Time> | null>(null);
  const highlightRef = useRef<MarketClosedHighlight | null>(null);
  const adaptiveRef = useRef<AdaptiveTimeScale | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();
  const timezone = user?.timezone || 'UTC';

  const fetchData = useCallback(async () => {
    try {
      const response = await MarketService.getCandleData(
        instrument,
        accountId,
        undefined,
        undefined,
        200,
        undefined,
        granularity
      );
      const candles = parseCandles(response?.candles);
      if (seriesRef.current) {
        seriesRef.current.setData(candles);
        const times = candles.map((c) => Number(c.time));
        if (highlightRef.current) {
          highlightRef.current.setGaps(detectMarketGaps(times));
        }
        chartRef.current?.timeScale().fitContent();
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load market data');
    } finally {
      setIsLoading(false);
    }
  }, [instrument, granularity, accountId]);

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
        background: { color: '#ffffff' },
        textColor: '#334155',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: '#e2e8f0' },
      },
      rightPriceScale: { borderColor: '#cbd5e1' },
      timeScale: {
        borderColor: '#cbd5e1',
        timeVisible: true,
        secondsVisible: SECONDS_GRANULARITIES.has(granularity),
        tickMarkFormatter: createSuppressedTickMarkFormatter(),
      },
      localization: {
        timeFormatter: createTooltipTimeFormatter({ timezone }),
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
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      highlightRef.current = null;
      adaptiveRef.current = null;
    };
  }, [height, fillHeight, granularity, timezone]);

  // Fetch data when instrument/granularity changes
  useEffect(() => {
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
            backgroundColor: 'rgba(255,255,255,0.7)',
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
