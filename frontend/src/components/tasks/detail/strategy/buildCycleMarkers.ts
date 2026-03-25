import type { Time } from 'lightweight-charts';
import type { CycleTrade } from '../../../../types/strategyVisualization';
import { snapToCandleTimeInLoadedRange } from '../taskTrendPanel/shared';

export interface CycleChartMarker {
  time: Time;
  position: 'aboveBar' | 'belowBar';
  color: string;
  shape: 'arrowUp' | 'arrowDown' | 'circle';
  text: string;
}

export function buildCycleMarkers(
  trades: CycleTrade[],
  candleTimes: number[]
): CycleChartMarker[] {
  if (candleTimes.length === 0) return [];

  const markers: CycleChartMarker[] = [];

  for (const trade of trades) {
    if (!trade.timestamp) continue;
    const tradeSec = Math.floor(new Date(trade.timestamp).getTime() / 1000);
    const snapped = snapToCandleTimeInLoadedRange(tradeSec, candleTimes);
    if (snapped == null) continue;

    const isOpen = trade.execution_method === 'open_position';
    const isBuy = trade.direction === 'buy';

    markers.push({
      time: snapped as Time,
      position: isOpen ? 'belowBar' : 'aboveBar',
      color: isOpen ? (isBuy ? '#26a69a' : '#ef5350') : '#ff9800',
      shape: isOpen ? (isBuy ? 'arrowUp' : 'arrowDown') : 'circle',
      text: `${isOpen ? 'Open' : 'Close'} ${isBuy ? 'B' : 'S'} ${trade.units}`,
    });
  }

  markers.sort((a, b) => Number(a.time) - Number(b.time));
  return markers;
}
