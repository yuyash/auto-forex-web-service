import { useCallback, useRef, type RefObject } from 'react';
import {
  HistogramSeries,
  LineSeries,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import {
  calcBollinger,
  calcEMA,
  calcSMA,
  detectSupportResistance,
} from '../../utils/technicalIndicators';
import type { OverlaySettings } from './chartOverlaySettings';

interface CandlePoint {
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

const COLORS = {
  sma20: '#2196F3',
  sma50: '#FF9800',
  ema12: '#9C27B0',
  ema26: '#00BCD4',
  bbMiddle: '#607D8B',
  volumeUp: 'rgba(22,163,74,0.35)',
  volumeDown: 'rgba(239,68,68,0.35)',
  support: '#16a34a',
  resistance: '#ef4444',
};

function detectCrossovers(
  fast: { time: number; value: number }[],
  slow: { time: number; value: number }[]
): SeriesMarker<Time>[] {
  const markers: SeriesMarker<Time>[] = [];
  const slowMap = new Map(slow.map((point) => [point.time, point.value]));
  let prevDiff: number | null = null;

  for (const fastPoint of fast) {
    const slowValue = slowMap.get(fastPoint.time);
    if (slowValue === undefined) continue;
    const diff = fastPoint.value - slowValue;
    if (prevDiff !== null) {
      if (prevDiff <= 0 && diff > 0) {
        markers.push({
          time: fastPoint.time as UTCTimestamp as Time,
          position: 'belowBar',
          color: '#16a34a',
          shape: 'arrowUp',
          text: 'Buy',
        });
      } else if (prevDiff >= 0 && diff < 0) {
        markers.push({
          time: fastPoint.time as UTCTimestamp as Time,
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

export function useMarketChartOverlays(
  containerRef: RefObject<HTMLDivElement | null>
) {
  const sma20Ref = useRef<ISeriesApi<'Line', Time> | null>(null);
  const sma50Ref = useRef<ISeriesApi<'Line', Time> | null>(null);
  const ema12Ref = useRef<ISeriesApi<'Line', Time> | null>(null);
  const ema26Ref = useRef<ISeriesApi<'Line', Time> | null>(null);
  const bbMiddleRef = useRef<ISeriesApi<'Line', Time> | null>(null);
  const bbUpperRef = useRef<ISeriesApi<'Line', Time> | null>(null);
  const bbLowerRef = useRef<ISeriesApi<'Line', Time> | null>(null);
  const volumeRef = useRef<ISeriesApi<'Histogram', Time> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);

  const clear = useCallback(() => {
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
  }, []);

  const applyOverlays = useCallback(
    (
      chart: IChartApi | null,
      mainSeries: ISeriesApi<'Candlestick', Time> | null,
      candles: CandlePoint[],
      overlays: OverlaySettings
    ) => {
      if (!chart || !mainSeries || candles.length === 0) return;

      const asTime = (points: { time: number; value: number }[]) =>
        points.map((point) => ({
          time: point.time as UTCTimestamp as Time,
          value: point.value,
        }));

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

      if (overlays.bollinger) {
        const bollinger = calcBollinger(candles, 20, 2);
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
        bbMiddleRef.current.setData(asTime(bollinger.middle));
        bbUpperRef.current?.setData(asTime(bollinger.upper));
        bbLowerRef.current?.setData(asTime(bollinger.lower));
      } else {
        for (const ref of [bbMiddleRef, bbUpperRef, bbLowerRef]) {
          if (ref.current) {
            chart.removeSeries(ref.current);
            ref.current = null;
          }
        }
      }

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
            .filter((candle) => candle.volume !== undefined)
            .map((candle) => ({
              time: candle.time as Time,
              value: candle.volume!,
              color:
                candle.close >= candle.open
                  ? COLORS.volumeUp
                  : COLORS.volumeDown,
            }))
        );
      } else if (volumeRef.current) {
        chart.removeSeries(volumeRef.current);
        volumeRef.current = null;
      }

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
        const lines = levels.map((level) =>
          mainSeries.createPriceLine({
            price: level.price,
            color:
              level.type === 'support' ? COLORS.support : COLORS.resistance,
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: true,
            title: level.type === 'support' ? 'S' : 'R',
          })
        );
        if (containerRef.current) {
          (
            containerRef.current as unknown as { __srLines: typeof lines }
          ).__srLines = lines;
        }
      }

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
    },
    [containerRef]
  );

  return { applyOverlays, clear };
}
