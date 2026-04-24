import { useEffect, type RefObject } from 'react';
import type {
  IChartApi,
  ISeriesApi,
  Time,
  UTCTimestamp,
} from 'lightweight-charts';
import type { OverlaySettings } from './chartOverlaySettings';
import { detectMarketGaps } from '../../utils/marketClosedMarkers';
import type { MarketClosedHighlight } from '../../utils/MarketClosedHighlight';

interface CandlePoint {
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface UseMarketChartDataSyncOptions {
  chartRef: RefObject<IChartApi | null>;
  seriesRef: RefObject<ISeriesApi<'Candlestick', Time> | null>;
  highlightRef: RefObject<MarketClosedHighlight | null>;
  candlesRef: RefObject<CandlePoint[]>;
  dataRanges: Array<{ from: number; to: number }>;
  granularity: string;
  timezone: string;
  overlays: OverlaySettings;
  applyOverlays: (
    chart: IChartApi | null,
    series: ISeriesApi<'Candlestick', Time> | null,
    candles: CandlePoint[],
    overlays: OverlaySettings
  ) => void;
  initialLoadDoneRef: RefObject<boolean>;
  previousFirstCandleTimeRef: RefObject<number | null>;
  restoreVisibleLogicalRange: (
    saved: { from: number; to: number } | null,
    prependCount?: number
  ) => void;
}

export function useMarketChartDataSync({
  chartRef,
  seriesRef,
  highlightRef,
  candlesRef,
  dataRanges,
  granularity,
  timezone,
  overlays,
  applyOverlays,
  initialLoadDoneRef,
  previousFirstCandleTimeRef,
  restoreVisibleLogicalRange,
}: UseMarketChartDataSyncOptions) {
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
    candlesRef,
    chartRef,
    dataRanges,
    granularity,
    highlightRef,
    initialLoadDoneRef,
    overlays,
    previousFirstCandleTimeRef,
    restoreVisibleLogicalRange,
    seriesRef,
    timezone,
  ]);
}
