import type { Time } from 'lightweight-charts';
import type { CycleTrade } from '../../../../types/strategyVisualization';
import { snapToCandleTime } from '../taskTrendPanel/shared';

export interface CycleChartMarker {
  time: Time;
  position: 'aboveBar' | 'belowBar';
  color: string;
  shape: 'arrowUp' | 'arrowDown' | 'circle';
  text: string;
}

/** Maximum allowed distance (seconds) between a trade and its snapped candle. */
const MAX_SNAP_DISTANCE_SEC = 2 * 86400;

const PROTECTION_METHODS = new Set([
  'volatility_lock',
  'margin_protection',
  'shrink',
  'rebalance',
]);

function isProtectionTrade(trade: CycleTrade): boolean {
  return (
    PROTECTION_METHODS.has(trade.execution_method) ||
    (trade.description?.startsWith('[PROTECTION]') ?? false)
  );
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
    const snapped = snapToCandleTime(tradeSec, candleTimes);
    if (snapped == null) continue;
    if (Math.abs(Number(snapped) - tradeSec) > MAX_SNAP_DISTANCE_SEC) continue;

    const isOpen = trade.execution_method === 'open_position';
    const isBuy = trade.direction === 'buy';
    const isProtection = isProtectionTrade(trade);

    if (isProtection) {
      markers.push({
        time: snapped as Time,
        position: 'aboveBar',
        color: '#e91e63',
        shape: 'circle',
        text: `⚠ ${trade.execution_method.replace('_', ' ')} ${trade.units}`,
      });
    } else {
      markers.push({
        time: snapped as Time,
        position: isOpen ? 'belowBar' : 'aboveBar',
        color: isOpen ? (isBuy ? '#26a69a' : '#ef5350') : '#ff9800',
        shape: isOpen ? (isBuy ? 'arrowUp' : 'arrowDown') : 'circle',
        text: `${isOpen ? 'Open' : 'Close'} ${isBuy ? 'B' : 'S'} ${trade.units}`,
      });
    }
  }

  markers.sort((a, b) => Number(a.time) - Number(b.time));
  return markers;
}
