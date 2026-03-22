import { useCallback, type RefObject } from 'react';
import type { IChartApi, ISeriesApi, Time } from 'lightweight-charts';

interface CandlePoint {
  time: number;
}

interface UseMarketChartViewportLoadingOptions {
  chartRef: RefObject<IChartApi | null>;
  seriesRef: RefObject<ISeriesApi<'Candlestick', Time> | null>;
  candlesRef: RefObject<CandlePoint[]>;
  ensureRange: (range: { from: number; to: number }) => Promise<void>;
}

export function useMarketChartViewportLoading({
  chartRef,
  seriesRef,
  candlesRef,
  ensureRange,
}: UseMarketChartViewportLoadingOptions) {
  return useCallback(async () => {
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

    const edgeThreshold = 5;
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

    if (logicalRange.from < edgeThreshold) {
      await ensureRange({
        from: firstTime - spanSeconds,
        to: firstTime,
      });
      return;
    }

    if (logicalRange.to > data.length - edgeThreshold) {
      await ensureRange({
        from: lastTime,
        to: lastTime + spanSeconds,
      });
    }
  }, [candlesRef, chartRef, ensureRange, seriesRef]);
}
