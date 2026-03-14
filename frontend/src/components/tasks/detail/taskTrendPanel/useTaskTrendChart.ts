import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type Time,
} from 'lightweight-charts';
import { TaskType } from '../../../../types/common';
import { detectMarketGaps } from '../../../../utils/marketClosedMarkers';
import { MarketClosedHighlight } from '../../../../utils/MarketClosedHighlight';
import {
  AdaptiveTimeScale,
  createSuppressedTickMarkFormatter,
  createTooltipTimeFormatter,
} from '../../../../utils/adaptiveTimeScalePlugin';
import { SequencePositionLine } from '../../../../utils/SequencePositionLine';
import { getCandleColors } from '../../../../utils/candleColors';
import { findGapAroundTime, type CandlePoint } from './shared';
import type { TimeRange } from '../../../../utils/windowedRanges';

interface UseTaskTrendChartParams {
  isLoading: boolean;
  chartHeight: number;
  isDark: boolean;
  timezone: string;
  candles: CandlePoint[];
  granularity: string;
  granularitySeconds: number;
  candleDataRanges: TimeRange[];
  startTimeSec: number | null;
  endTimeSec: number | null;
  currentTick: { timestamp: string; price: string | null } | null | undefined;
  currentTickSec: number | null;
  enableRealTimeUpdates: boolean;
  autoFollow: boolean;
  taskType: TaskType;
  tradesRef: React.RefObject<
    Array<{
      id: string;
      timeSec: number;
    }>
  >;
  clampTaskRange: (range: TimeRange) => TimeRange | null;
  ensureCandleRange: (range: TimeRange) => Promise<unknown>;
  ensureMarkerRange: (range: TimeRange) => Promise<unknown>;
  setAutoFollow: React.Dispatch<React.SetStateAction<boolean>>;
  onTradeMarkerClick: (tradeId: string | null) => void;
}

export function useTaskTrendChart({
  isLoading,
  chartHeight,
  isDark,
  timezone,
  candles,
  granularity,
  granularitySeconds,
  candleDataRanges,
  startTimeSec,
  endTimeSec,
  currentTick,
  currentTickSec,
  enableRealTimeUpdates,
  autoFollow,
  taskType,
  tradesRef,
  clampTaskRange,
  ensureCandleRange,
  ensureMarkerRange,
  setAutoFollow,
  onTradeMarkerClick,
}: UseTaskTrendChartParams) {
  const chartContainerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick', Time> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const highlightRef = useRef<MarketClosedHighlight | null>(null);
  const adaptiveRef = useRef<AdaptiveTimeScale | null>(null);
  const sequenceLineRef = useRef<SequencePositionLine | null>(null);
  const previousFirstCandleTimeRef = useRef<number | null>(null);
  const hasInitialFit = useRef(false);
  const savedVisibleRangeRef = useRef<{ from: number; to: number } | null>(
    null
  );
  const [chartInstance, setChartInstance] = useState<IChartApi | null>(null);
  const hasCandles = candles.length > 0;
  const AUTO_FOLLOW_CANDLES = 1000;

  const programmaticScrollCountRef = useRef(0);
  const programmaticScrollUntilRef = useRef(0);
  const PROGRAMMATIC_SCROLL_GUARD_MS = 800;
  const programmaticScrollRef = useMemo(
    () => ({
      get current() {
        return (
          programmaticScrollCountRef.current > 0 ||
          Date.now() < programmaticScrollUntilRef.current
        );
      },
      set current(value: boolean) {
        if (value) {
          programmaticScrollCountRef.current += 1;
          programmaticScrollUntilRef.current =
            Date.now() + PROGRAMMATIC_SCROLL_GUARD_MS;
        } else {
          programmaticScrollCountRef.current = 0;
          programmaticScrollUntilRef.current = 0;
        }
      },
      consume() {
        if (programmaticScrollCountRef.current > 0) {
          programmaticScrollCountRef.current -= 1;
          return true;
        }
        return Date.now() < programmaticScrollUntilRef.current;
      },
    }),
    []
  );

  const storeVisibleRange = useCallback(() => {
    const timeScale = chartRef.current?.timeScale();
    if (!timeScale) return;
    const range = timeScale.getVisibleRange();
    if (!range) return;
    savedVisibleRangeRef.current = {
      from: Number(range.from),
      to: Number(range.to),
    };
  }, []);

  const fitContent = useCallback(() => {
    programmaticScrollRef.current = true;
    chartRef.current?.timeScale().fitContent();
  }, [programmaticScrollRef]);

  const maybeFetchVisibleWindow = useCallback(async () => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series) return;

    const visibleTimeRange = chart.timeScale().getVisibleRange();
    if (
      visibleTimeRange &&
      typeof visibleTimeRange.from === 'number' &&
      typeof visibleTimeRange.to === 'number'
    ) {
      const target = clampTaskRange({
        from: Number(visibleTimeRange.from),
        to: Number(visibleTimeRange.to),
      });
      if (target) {
        await Promise.all([
          ensureCandleRange(target),
          ensureMarkerRange(target),
        ]);
      }
    }

    const logicalRange = chart.timeScale().getVisibleLogicalRange();
    const data = series.data();
    if (!logicalRange || !data || data.length === 0) return;

    const EDGE_THRESHOLD = 5;
    const firstTime = Number(candles[0]?.time ?? 0);
    const lastTime = Number(candles[candles.length - 1]?.time ?? 0);
    const spanSeconds =
      visibleTimeRange &&
      typeof visibleTimeRange.from === 'number' &&
      typeof visibleTimeRange.to === 'number'
        ? Math.max(
            granularitySeconds,
            Number(visibleTimeRange.to) - Number(visibleTimeRange.from)
          )
        : Math.max(granularitySeconds, lastTime - firstTime);

    const lowerBound = startTimeSec ?? undefined;
    const upperBound =
      enableRealTimeUpdates && taskType === TaskType.TRADING
        ? (currentTickSec ?? undefined)
        : (endTimeSec ?? currentTickSec ?? undefined);

    if (
      logicalRange.from < EDGE_THRESHOLD &&
      (lowerBound == null || firstTime > lowerBound)
    ) {
      await ensureCandleRange({
        from: Math.max(
          lowerBound ?? firstTime - spanSeconds,
          firstTime - spanSeconds
        ),
        to: firstTime,
      });
      return;
    }

    if (
      logicalRange.to > data.length - EDGE_THRESHOLD &&
      (upperBound == null || lastTime < upperBound)
    ) {
      await ensureCandleRange({
        from: lastTime,
        to: Math.min(
          upperBound ?? lastTime + spanSeconds,
          lastTime + spanSeconds
        ),
      });
    }
  }, [
    candles,
    clampTaskRange,
    currentTickSec,
    enableRealTimeUpdates,
    endTimeSec,
    ensureCandleRange,
    ensureMarkerRange,
    granularitySeconds,
    startTimeSec,
    taskType,
  ]);

  const maybeFetchVisibleWindowRef = useRef(maybeFetchVisibleWindow);
  const onTradeMarkerClickRef = useRef(onTradeMarkerClick);
  useEffect(() => {
    maybeFetchVisibleWindowRef.current = maybeFetchVisibleWindow;
  }, [maybeFetchVisibleWindow]);
  useEffect(() => {
    onTradeMarkerClickRef.current = onTradeMarkerClick;
  }, [onTradeMarkerClick]);

  useEffect(() => {
    if (isLoading || !hasCandles) return;
    if (!chartContainerRef.current || chartRef.current) return;

    const container = chartContainerRef.current;
    const chart = createChart(container, {
      height: chartHeight,
      layout: {
        background: { color: isDark ? '#131722' : '#ffffff' },
        textColor: isDark ? '#ffffff' : '#334155',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: isDark ? '#2a2e39' : '#e2e8f0' },
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        vertTouchDrag: true,
        horzTouchDrag: true,
      },
      rightPriceScale: {
        borderColor: isDark ? '#2a2e39' : '#cbd5e1',
        minimumWidth: 80,
        scaleMargins: { top: 0.02, bottom: 0.45 },
      },
      leftPriceScale: {
        borderColor: isDark ? '#2a2e39' : '#cbd5e1',
        visible: true,
        minimumWidth: 80,
        ticksVisible: true,
      },
      timeScale: {
        borderColor: isDark ? '#2a2e39' : '#cbd5e1',
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: createSuppressedTickMarkFormatter(),
      },
      localization: {
        timeFormatter: createTooltipTimeFormatter({ timezone }),
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
    const markers = createSeriesMarkers(series, []);

    chartRef.current = chart;
    seriesRef.current = series;
    markersRef.current = markers;
    setChartInstance(chart);

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

    const sequenceLine = new SequencePositionLine();
    series.attachPrimitive(sequenceLine);
    sequenceLineRef.current = sequenceLine;

    chart.subscribeClick((param) => {
      if (!param.time || tradesRef.current.length === 0) return;
      const clickedTime = Number(param.time);
      const nearestTrade = tradesRef.current.reduce((prev, curr) => {
        const prevDiff = Math.abs(Number(prev.timeSec) - clickedTime);
        const currDiff = Math.abs(Number(curr.timeSec) - clickedTime);
        return currDiff < prevDiff ? curr : prev;
      }, tradesRef.current[0]);
      onTradeMarkerClickRef.current(nearestTrade?.id ?? null);
    });

    let viewportDebounce: ReturnType<typeof setTimeout> | null = null;
    const handleViewportChange = () => {
      if (programmaticScrollRef.consume()) return;
      setAutoFollow(false);
      if (viewportDebounce) clearTimeout(viewportDebounce);
      viewportDebounce = setTimeout(() => {
        void maybeFetchVisibleWindowRef.current();
      }, 250);
    };
    chart.timeScale().subscribeVisibleLogicalRangeChange(handleViewportChange);
    chart.timeScale().subscribeVisibleTimeRangeChange(handleViewportChange);

    const observer = new ResizeObserver(() => {
      const width = container.clientWidth;
      const height = container.clientHeight;
      programmaticScrollRef.current = true;
      if (width > 0) chart.applyOptions({ width });
      if (height > 0) chart.applyOptions({ height });
    });
    observer.observe(container);
    programmaticScrollRef.current = true;
    chart.applyOptions({ width: container.clientWidth });

    return () => {
      observer.disconnect();
      if (viewportDebounce) clearTimeout(viewportDebounce);
      chart
        .timeScale()
        .unsubscribeVisibleLogicalRangeChange(handleViewportChange);
      chart.timeScale().unsubscribeVisibleTimeRangeChange(handleViewportChange);
      setChartInstance(null);
      chartRef.current = null;
      seriesRef.current = null;
      markersRef.current = null;
      highlightRef.current = null;
      adaptiveRef.current = null;
      sequenceLineRef.current = null;
      hasInitialFit.current = false;
      requestAnimationFrame(() => {
        try {
          chart.remove();
        } catch {
          /* chart already disposed */
        }
      });
    };
  }, [
    chartHeight,
    hasCandles,
    isDark,
    isLoading,
    programmaticScrollRef,
    setAutoFollow,
    timezone,
    tradesRef,
  ]);

  useEffect(() => {
    if (!enableRealTimeUpdates || currentTickSec == null) return;

    const isTrading = taskType === TaskType.TRADING;
    const leftCandles = isTrading
      ? AUTO_FOLLOW_CANDLES * 0.75
      : AUTO_FOLLOW_CANDLES / 2;
    const rightCandles = AUTO_FOLLOW_CANDLES - leftCandles;
    const target = clampTaskRange({
      from: currentTickSec - leftCandles * granularitySeconds,
      to: currentTickSec + rightCandles * granularitySeconds,
    });

    if (!target) return;
    void Promise.all([ensureCandleRange(target), ensureMarkerRange(target)]);
  }, [
    AUTO_FOLLOW_CANDLES,
    clampTaskRange,
    currentTickSec,
    enableRealTimeUpdates,
    ensureCandleRange,
    ensureMarkerRange,
    granularitySeconds,
    taskType,
  ]);

  useEffect(() => {
    const boundaryPaddingSeconds = Math.max(granularitySeconds * 8, 60 * 60);
    const requests: Array<Promise<unknown>> = [];

    if (startTimeSec != null) {
      const startRange = clampTaskRange({
        from: startTimeSec,
        to: startTimeSec + boundaryPaddingSeconds,
      });
      if (startRange) requests.push(ensureCandleRange(startRange));
    }

    if (endTimeSec != null) {
      const endRange = clampTaskRange({
        from: endTimeSec - boundaryPaddingSeconds,
        to: endTimeSec + boundaryPaddingSeconds,
      });
      if (endRange) requests.push(ensureCandleRange(endRange));
    }

    if (requests.length === 0) return;
    void Promise.all(requests);
  }, [
    clampTaskRange,
    endTimeSec,
    ensureCandleRange,
    granularitySeconds,
    startTimeSec,
  ]);

  useEffect(() => {
    if (!seriesRef.current || !markersRef.current) return;
    programmaticScrollRef.current = true;

    const savedLogicalRange = hasInitialFit.current
      ? chartRef.current?.timeScale().getVisibleLogicalRange()
      : null;

    try {
      seriesRef.current.setData(candles);
    } catch (error) {
      console.warn('Failed to set candle data:', error);
      return;
    }

    const times = candles.map((candle) => Number(candle.time));
    highlightRef.current?.setGaps(
      detectMarketGaps(times, granularity, candleDataRanges, timezone)
    );

    if (candles.length > 0 && !hasInitialFit.current) {
      programmaticScrollRef.current = true;
      const tickTs = currentTick?.timestamp
        ? Math.floor(new Date(currentTick.timestamp).getTime() / 1000)
        : null;

      if (
        enableRealTimeUpdates &&
        tickTs &&
        Number.isFinite(tickTs) &&
        seriesRef.current
      ) {
        const data = seriesRef.current.data();
        let logicalCenter = 0;
        if (data.length > 0) {
          let lo = 0;
          let hi = data.length - 1;
          while (lo < hi) {
            const mid = (lo + hi) >>> 1;
            const midSec =
              typeof data[mid].time === 'number'
                ? (data[mid].time as number)
                : new Date(data[mid].time as string).getTime() / 1000;
            if (midSec < tickTs) lo = mid + 1;
            else hi = mid;
          }
          logicalCenter = lo;
        }
        const half = AUTO_FOLLOW_CANDLES / 2;
        try {
          chartRef.current?.timeScale().setVisibleLogicalRange({
            from: logicalCenter - half,
            to: logicalCenter + half,
          });
        } catch (error) {
          console.warn('Failed to set initial visible range on tick:', error);
        }
      } else if (!enableRealTimeUpdates && startTimeSec != null) {
        const totalSpanSeconds = AUTO_FOLLOW_CANDLES * granularitySeconds;
        const gapAroundStart = findGapAroundTime(
          startTimeSec,
          times,
          granularitySeconds * 6
        );
        const initialFrom = gapAroundStart
          ? Math.max(startTimeSec, gapAroundStart.from)
          : startTimeSec;
        const requiredGapSpan = gapAroundStart
          ? gapAroundStart.to - initialFrom
          : 0;
        const initialSpanSeconds = Math.max(totalSpanSeconds, requiredGapSpan);
        try {
          chartRef.current?.timeScale().setVisibleRange({
            from: initialFrom as Time,
            to: (initialFrom + initialSpanSeconds) as Time,
          });
        } catch (error) {
          console.warn(
            'Failed to set initial visible range at task start:',
            error
          );
        }
      } else {
        try {
          chartRef.current?.timeScale().setVisibleLogicalRange({
            from: 0,
            to: AUTO_FOLLOW_CANDLES,
          });
        } catch (error) {
          console.warn('Failed to set initial visible range at start:', error);
        }
      }

      hasInitialFit.current = true;
    } else if (savedLogicalRange) {
      programmaticScrollRef.current = true;
      try {
        const previousFirst = previousFirstCandleTimeRef.current;
        const currentFirst =
          candles.length > 0 ? Number(candles[0].time) : null;
        const prependCount =
          previousFirst != null &&
          currentFirst != null &&
          currentFirst < previousFirst
            ? candles.filter((candle) => Number(candle.time) < previousFirst)
                .length
            : 0;
        chartRef.current?.timeScale().setVisibleLogicalRange({
          from: savedLogicalRange.from + prependCount,
          to: savedLogicalRange.to + prependCount,
        });
      } catch (error) {
        console.warn('Failed to restore visible range after setData:', error);
      }
    }

    if (savedVisibleRangeRef.current && chartRef.current) {
      const { from, to } = savedVisibleRangeRef.current;
      savedVisibleRangeRef.current = null;
      programmaticScrollRef.current = true;
      try {
        chartRef.current.timeScale().setVisibleRange({
          from: from as Time,
          to: to as Time,
        });
      } catch (error) {
        console.warn(
          'Failed to restore visible range after granularity change:',
          error
        );
      }
    }

    previousFirstCandleTimeRef.current =
      candles.length > 0 ? Number(candles[0].time) : null;
  }, [
    AUTO_FOLLOW_CANDLES,
    candleDataRanges,
    candles,
    currentTick?.timestamp,
    enableRealTimeUpdates,
    granularity,
    granularitySeconds,
    startTimeSec,
    timezone,
    programmaticScrollRef,
  ]);

  useEffect(() => {
    if (!sequenceLineRef.current) return;
    if (!currentTick?.timestamp) {
      sequenceLineRef.current.clear();
      return;
    }

    const price =
      currentTick.price != null ? parseFloat(currentTick.price) : null;
    sequenceLineRef.current.setPosition(currentTick.timestamp, price);

    if (autoFollow && enableRealTimeUpdates) {
      const ts = chartRef.current?.timeScale();
      const series = seriesRef.current;
      if (ts && series) {
        const centerSec = Math.floor(
          new Date(currentTick.timestamp).getTime() / 1000
        );
        if (Number.isFinite(centerSec)) {
          const data = series.data();
          let logicalCenter = data.length - 1;
          if (data.length > 0) {
            let lo = 0;
            let hi = data.length - 1;
            while (lo < hi) {
              const mid = (lo + hi) >>> 1;
              const midSec =
                typeof data[mid].time === 'number'
                  ? (data[mid].time as number)
                  : new Date(data[mid].time as string).getTime() / 1000;
              if (midSec < centerSec) lo = mid + 1;
              else hi = mid;
            }
            logicalCenter = lo;
          }

          const isTrading = taskType === TaskType.TRADING;
          const leftCandles = isTrading
            ? AUTO_FOLLOW_CANDLES * 0.75
            : AUTO_FOLLOW_CANDLES / 2;
          const rightCandles = AUTO_FOLLOW_CANDLES - leftCandles;

          programmaticScrollRef.current = true;
          try {
            ts.setVisibleLogicalRange({
              from: logicalCenter - leftCandles,
              to: logicalCenter + rightCandles,
            });
          } catch (error) {
            console.warn(
              'Failed to set visible range during auto-follow:',
              error
            );
          }
        }
      }
    }
  }, [
    AUTO_FOLLOW_CANDLES,
    autoFollow,
    currentTick?.price,
    currentTick?.timestamp,
    enableRealTimeUpdates,
    programmaticScrollRef,
    taskType,
  ]);

  return {
    chartContainerRef,
    chartInstance,
    chartRef,
    markersRef,
    programmaticScrollRef,
    storeVisibleRange,
    fitContent,
  };
}
