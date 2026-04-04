import type { Time, UTCTimestamp } from 'lightweight-charts';
import type { CycleTrade } from '../../../../types/strategyVisualization';

/** Binary-search snap: find the candle time closest to `timeSec`. */
function snapToCandleTime(
  timeSec: number,
  candleTimes: number[]
): UTCTimestamp | null {
  if (candleTimes.length === 0) return null;
  let lo = 0;
  let hi = candleTimes.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (candleTimes[mid] < timeSec) lo = mid + 1;
    else hi = mid;
  }
  const candidates = [lo - 1, lo].filter(
    (i) => i >= 0 && i < candleTimes.length
  );
  let best = candidates[0]!;
  for (const i of candidates) {
    if (
      Math.abs(candleTimes[i] - timeSec) < Math.abs(candleTimes[best] - timeSec)
    ) {
      best = i;
    }
  }
  return candleTimes[best] as UTCTimestamp;
}

export interface CycleChartMarker {
  time: Time;
  position: 'aboveBar' | 'belowBar';
  color: string;
  shape: 'arrowUp' | 'arrowDown' | 'circle';
  text: string;
  /** Trade ID this marker corresponds to, used for click-to-select. */
  tradeId?: string;
}

/** Maximum allowed distance (seconds) between a trade and its snapped candle. */
const MAX_SNAP_DISTANCE_SEC = 2 * 86400;

const PROTECTION_METHODS = new Set([
  'volatility_lock',
  'margin_protection',
  'shrink',
]);

function isProtectionTrade(trade: CycleTrade): boolean {
  return (
    PROTECTION_METHODS.has(trade.execution_method) ||
    (trade.description?.startsWith('[PROTECTION]') ?? false)
  );
}

const HIGHLIGHT_COLOR = '#f59e0b';

export function buildCycleMarkers(
  trades: CycleTrade[],
  candleTimes: number[],
  selectedTradeIds?: Set<string>,
  markersVisible = true
): CycleChartMarker[] {
  if (candleTimes.length === 0) return [];

  const markers: CycleChartMarker[] = [];

  for (const trade of trades) {
    if (!trade.timestamp) continue;
    const tradeSec = Math.floor(new Date(trade.timestamp).getTime() / 1000);
    const snapped = snapToCandleTime(tradeSec, candleTimes);
    if (snapped == null) continue;
    if (Math.abs(Number(snapped) - tradeSec) > MAX_SNAP_DISTANCE_SEC) continue;

    const isSelected = selectedTradeIds?.has(trade.id) ?? false;

    // When markers are hidden, only show selected trades
    if (!markersVisible && !isSelected) continue;

    const isOpen = trade.execution_method === 'open_position';
    const isBuy = trade.direction === 'buy';
    const isProtection = isProtectionTrade(trade);

    const baseColor = isProtection
      ? '#e91e63'
      : isOpen
        ? isBuy
          ? '#26a69a'
          : '#ef5350'
        : '#ff9800';

    const color = isSelected ? HIGHLIGHT_COLOR : baseColor;

    if (isProtection) {
      markers.push({
        time: snapped as Time,
        position: 'aboveBar',
        color,
        shape: 'circle',
        text: `⚠ ${trade.execution_method.replace('_', ' ')} ${trade.units}`,
        tradeId: trade.id,
      });
    } else {
      markers.push({
        time: snapped as Time,
        position: isOpen ? 'belowBar' : 'aboveBar',
        color,
        shape: isOpen ? (isBuy ? 'arrowUp' : 'arrowDown') : 'circle',
        text: `${isOpen ? 'Open' : 'Close'} ${isBuy ? 'B' : 'S'} ${trade.units}`,
        tradeId: trade.id,
      });
    }
  }

  markers.sort((a, b) => Number(a.time) - Number(b.time));
  return markers;
}
