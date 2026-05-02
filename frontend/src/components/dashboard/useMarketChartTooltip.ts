import { useEffect, type RefObject } from 'react';
import type {
  IChartApi,
  ISeriesApi,
  MouseEventParams,
  Time,
  UTCTimestamp,
} from 'lightweight-charts';
import { useNumberFormatter } from '../../hooks/useNumberFormatter';

interface CandlePoint {
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface UseMarketChartTooltipOptions {
  chartRef: RefObject<IChartApi | null>;
  seriesRef: RefObject<ISeriesApi<'Candlestick', Time> | null>;
  tooltipRef: RefObject<HTMLDivElement | null>;
  candlesRef: RefObject<CandlePoint[]>;
}

export function useMarketChartTooltip({
  chartRef,
  seriesRef,
  tooltipRef,
  candlesRef,
}: UseMarketChartTooltipOptions) {
  const { formatNumber } = useNumberFormatter();

  useEffect(() => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series) {
      return;
    }

    const handleCrosshairMove = (param: MouseEventParams<Time>) => {
      const tooltip = tooltipRef.current;
      if (!tooltip) return;
      if (!param.time || !param.seriesData) {
        tooltip.style.display = 'none';
        return;
      }

      const data = param.seriesData.get(series);
      if (!data || typeof data !== 'object' || !('open' in data)) {
        tooltip.style.display = 'none';
        return;
      }

      const point = data as {
        open: number;
        high: number;
        low: number;
        close: number;
      };
      const change = point.close - point.open;
      const changeColor = change >= 0 ? '#16a34a' : '#ef4444';
      const changeSign = change >= 0 ? '+' : '-';
      const timestamp = typeof param.time === 'number' ? param.time : 0;
      const candle = candlesRef.current.find(
        (entry) => Number(entry.time) === timestamp
      );
      const volumeDisplay =
        candle?.volume !== undefined
          ? `  Vol: ${formatNumber(candle.volume, {
              maximumFractionDigits: 0,
            })}`
          : '';
      const formatPrice = (value: number) =>
        formatNumber(value, {
          minimumFractionDigits: 5,
          maximumFractionDigits: 5,
          useGrouping: false,
        });

      tooltip.style.display = 'block';
      tooltip.innerHTML =
        `<span style="color:#64748b">O</span> ${formatPrice(point.open)}` +
        `  <span style="color:#64748b">H</span> ${formatPrice(point.high)}` +
        `  <span style="color:#64748b">L</span> ${formatPrice(point.low)}` +
        `  <span style="color:#64748b">C</span> ${formatPrice(point.close)}` +
        `  <span style="color:${changeColor}">${changeSign}${formatPrice(Math.abs(change))}</span>` +
        `<span style="color:#94a3b8">${volumeDisplay}</span>`;
    };

    chart.subscribeCrosshairMove(handleCrosshairMove);
    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
    };
  }, [candlesRef, chartRef, formatNumber, seriesRef, tooltipRef]);
}
