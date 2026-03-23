import { useEffect, type RefObject } from 'react';
import {
  CandlestickSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import { getCandleColors } from '../../utils/candleColors';
import { MarketClosedHighlight } from '../../utils/MarketClosedHighlight';
import {
  AdaptiveTimeScale,
  createSuppressedTickMarkFormatter,
  createTooltipTimeFormatter,
} from '../../utils/adaptiveTimeScalePlugin';
import type { OverlaySettings } from './chartOverlaySettings';

const SECONDS_GRANULARITIES = new Set<string>(['M1', 'M2', 'M4', 'M5']);

interface CandlePoint {
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface UseMarketChartLifecycleOptions {
  containerRef: RefObject<HTMLDivElement | null>;
  chartRef: RefObject<IChartApi | null>;
  seriesRef: RefObject<ISeriesApi<'Candlestick', Time> | null>;
  highlightRef: RefObject<MarketClosedHighlight | null>;
  adaptiveRef: RefObject<AdaptiveTimeScale | null>;
  candlesRef: RefObject<CandlePoint[]>;
  granularity: string;
  timezone: string;
  isDark: boolean;
  height: number;
  fillHeight: boolean;
  overlays: OverlaySettings;
  applyOverlays: (
    chart: IChartApi | null,
    series: ISeriesApi<'Candlestick', Time> | null,
    candles: CandlePoint[],
    overlays: OverlaySettings
  ) => void;
  clearOverlays: () => void;
  onVisibleRangeChange: () => void | Promise<void>;
}

export function useMarketChartLifecycle({
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
  onVisibleRangeChange,
}: UseMarketChartLifecycleOptions) {
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

    if (candlesRef.current.length > 0) {
      series.setData(candlesRef.current);
      applyOverlays(chart, series, candlesRef.current, overlays);
    }

    let scrollDebounce: ReturnType<typeof setTimeout> | null = null;
    const handleVisibleRangeChange = () => {
      if (scrollDebounce) clearTimeout(scrollDebounce);
      scrollDebounce = setTimeout(() => {
        void onVisibleRangeChange();
      }, 300);
    };

    chart
      .timeScale()
      .subscribeVisibleLogicalRangeChange(handleVisibleRangeChange);

    const observer = new ResizeObserver(() => {
      const width = container.clientWidth;
      if (width > 0) chart.applyOptions({ width });
      if (fillHeight) {
        const nextHeight = container.clientHeight;
        if (nextHeight > 0) chart.applyOptions({ height: nextHeight });
      }
    });

    observer.observe(container);
    chart.applyOptions({ width: container.clientWidth });
    if (fillHeight) {
      const nextHeight = container.clientHeight;
      if (nextHeight > 0) chart.applyOptions({ height: nextHeight });
    }

    return () => {
      observer.disconnect();
      chart
        .timeScale()
        .unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange);
      if (scrollDebounce) clearTimeout(scrollDebounce);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      highlightRef.current = null;
      adaptiveRef.current = null;
      clearOverlays();
    };
  }, [
    adaptiveRef,
    applyOverlays,
    candlesRef,
    chartRef,
    clearOverlays,
    containerRef,
    fillHeight,
    granularity,
    height,
    highlightRef,
    isDark,
    onVisibleRangeChange,
    overlays,
    seriesRef,
    timezone,
  ]);
}
