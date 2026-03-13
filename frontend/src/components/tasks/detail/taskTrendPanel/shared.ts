import type { CandlestickData, Time, UTCTimestamp } from 'lightweight-charts';
import type { TaskEvent } from '../../../../hooks/useTaskEvents';
import type { TaskPosition } from '../../../../hooks/useTaskPositions';

export type CandlePoint = CandlestickData<Time>;

export type ReplayTrade = {
  id: string;
  sequence: number;
  timestamp: string;
  timeSec: UTCTimestamp;
  instrument: string;
  direction: 'long' | 'short' | '';
  units: string;
  price: string;
  execution_method?: string;
  execution_method_display?: string;
  layer_index?: number | null;
  retracement_count?: number | null;
  position_id?: string | null;
};

export type TrendPosition = TaskPosition & { _status: 'open' | 'closed' };

export type SortableKey =
  | 'timestamp'
  | 'direction'
  | 'layer_index'
  | 'retracement_count'
  | 'units'
  | 'price'
  | 'execution_method';

export type LSPosSortableKey =
  | 'entry_time'
  | 'exit_time'
  | '_status'
  | 'layer_index'
  | 'retracement_count'
  | 'units'
  | 'entry_price'
  | 'exit_price'
  | '_pips'
  | '_pnl';

export interface ReplaySummary {
  realizedPnl: number;
  unrealizedPnl: number;
  totalTrades: number;
  openPositions: number;
}

export const TARGET_CANDLE_COUNT = 10000;
export const LOT_UNITS = 1000;

export const GRANULARITY_MINUTES: Record<string, number> = {
  M1: 1,
  M2: 2,
  M4: 4,
  M5: 5,
  M10: 10,
  M15: 15,
  M30: 30,
  H1: 60,
  H2: 120,
  H3: 180,
  H4: 240,
  H6: 360,
  H8: 480,
  H12: 720,
  D: 1440,
  W: 10080,
  M: 43200,
};

export const ALLOWED_GRANULARITIES = [
  { value: 'M1', label: '1 Minute' },
  { value: 'M5', label: '5 Minutes' },
  { value: 'M15', label: '15 Minutes' },
  { value: 'M30', label: '30 Minutes' },
  { value: 'H1', label: '1 Hour' },
  { value: 'H4', label: '4 Hours' },
  { value: 'H8', label: '8 Hours' },
  { value: 'H12', label: '12 Hours' },
  { value: 'D', label: 'Daily' },
  { value: 'W', label: 'Weekly' },
  { value: 'M', label: 'Monthly' },
];

export const ALLOWED_VALUES = new Set(
  ALLOWED_GRANULARITIES.map((g) => g.value)
);

export const POLLING_INTERVAL_OPTIONS = [
  { value: 10_000, label: '10s' },
  { value: 30_000, label: '30s' },
  { value: 60_000, label: '1m' },
  { value: 300_000, label: '5m' },
  { value: 900_000, label: '15m' },
];

export const DEFAULT_REPLAY_WIDTHS: Record<string, number> = {
  timestamp: 160,
  direction: 70,
  layer_index: 60,
  retracement_count: 60,
  units: 70,
  price: 90,
  execution_method: 110,
};

export const DEFAULT_LS_POSITION_WIDTHS: Record<string, number> = {
  entry_time: 160,
  exit_time: 150,
  _status: 70,
  layer_index: 60,
  retracement_count: 65,
  units: 70,
  entry_price: 100,
  exit_price: 100,
  _pips: 80,
  _pnl: 140,
};

export function isoToSec(value?: string | null): number | null {
  if (!value) return null;
  const ms = new Date(value).getTime();
  return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
}

export const parseUtcTimestamp = (value: unknown): UTCTimestamp | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    if (value > 1_000_000_000_000) {
      return Math.floor(value / 1000) as UTCTimestamp;
    }
    if (value > 1_000_000_000) {
      return Math.floor(value) as UTCTimestamp;
    }
  }

  if (typeof value === 'string') {
    const asNumber = Number(value);
    if (Number.isFinite(asNumber)) {
      if (asNumber > 1_000_000_000_000) {
        return Math.floor(asNumber / 1000) as UTCTimestamp;
      }
      if (asNumber > 1_000_000_000) {
        return Math.floor(asNumber) as UTCTimestamp;
      }
    }

    const ms = new Date(value).getTime();
    if (Number.isFinite(ms)) {
      return Math.floor(ms / 1000) as UTCTimestamp;
    }
  }

  return null;
};

export const toEventMarkerTime = (event: TaskEvent): UTCTimestamp | null => {
  const detailTimestamp =
    typeof event.details?.timestamp === 'string'
      ? event.details.timestamp
      : undefined;
  return (
    parseUtcTimestamp(detailTimestamp) ?? parseUtcTimestamp(event.created_at)
  );
};

export const snapToCandleTime = (
  timeSec: number,
  candleTimes: number[]
): UTCTimestamp | null => {
  if (candleTimes.length === 0) return null;

  let lo = 0;
  let hi = candleTimes.length - 1;

  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (candleTimes[mid] < timeSec) {
      lo = mid + 1;
    } else {
      hi = mid;
    }
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
};

export const snapToCandleTimeInLoadedRange = (
  timeSec: number,
  candleTimes: number[]
): UTCTimestamp | null => {
  if (candleTimes.length === 0) return null;
  if (
    timeSec < candleTimes[0] ||
    timeSec > candleTimes[candleTimes.length - 1]
  ) {
    return null;
  }
  return snapToCandleTime(timeSec, candleTimes);
};

export const findFirstCandleAtOrAfter = (
  timeSec: number,
  candleTimes: number[]
): UTCTimestamp | null => {
  if (candleTimes.length === 0) return null;
  const first = candleTimes[0];
  const last = candleTimes[candleTimes.length - 1];
  if (timeSec <= first) return first as UTCTimestamp;
  if (timeSec > last) return null;

  let lo = 0;
  let hi = candleTimes.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (candleTimes[mid] < timeSec) {
      lo = mid + 1;
    } else {
      hi = mid;
    }
  }
  return candleTimes[lo] as UTCTimestamp;
};

export const findLastCandleAtOrBefore = (
  timeSec: number,
  candleTimes: number[]
): UTCTimestamp | null => {
  if (candleTimes.length === 0) return null;
  const first = candleTimes[0];
  const last = candleTimes[candleTimes.length - 1];
  if (timeSec < first) return null;
  if (timeSec >= last) return last as UTCTimestamp;

  let lo = 0;
  let hi = candleTimes.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >>> 1;
    if (candleTimes[mid] <= timeSec) {
      lo = mid;
    } else {
      hi = mid - 1;
    }
  }
  return candleTimes[lo] as UTCTimestamp;
};

export const findGapAroundTime = (
  timeSec: number,
  candleTimes: number[],
  gapThresholdSeconds: number
): { from: number; to: number } | null => {
  if (candleTimes.length < 2) return null;
  for (let i = 1; i < candleTimes.length; i += 1) {
    const prev = candleTimes[i - 1];
    const next = candleTimes[i];
    if (timeSec < prev || timeSec > next) continue;
    if (next - prev > gapThresholdSeconds) {
      return { from: prev, to: next };
    }
  }
  return null;
};

export const recommendGranularity = (
  fromIso: string | undefined,
  toIso: string | undefined,
  available: string[]
): string => {
  if (!fromIso || !toIso || available.length === 0) return 'M1';

  const fromMs = new Date(fromIso).getTime();
  const toMs = new Date(toIso).getTime();
  if (!Number.isFinite(fromMs) || !Number.isFinite(toMs) || toMs <= fromMs) {
    return 'H1';
  }

  const rangeMinutes = (toMs - fromMs) / (1000 * 60);
  let best = available[0] ?? 'H1';
  let bestDiff = Number.POSITIVE_INFINITY;

  for (const g of available) {
    const mins = GRANULARITY_MINUTES[g];
    if (!mins) continue;
    const candles = rangeMinutes / mins;
    const diff = Math.abs(candles - TARGET_CANDLE_COUNT);
    if (diff < bestDiff) {
      bestDiff = diff;
      best = g;
    }
  }

  return best;
};

export const computePosPnl = (
  pos: TaskPosition & { _status: 'open' | 'closed' },
  currentPrice: number | null
): number => {
  const entryP = pos.entry_price ? parseFloat(pos.entry_price) : null;
  const exitP = pos.exit_price ? parseFloat(pos.exit_price) : null;
  const units = Math.abs(pos.units ?? 0);
  const dir = String(pos.direction).toLowerCase();
  if (pos._status === 'open' && currentPrice != null && entryP != null) {
    return dir === 'long'
      ? (currentPrice - entryP) * units
      : (entryP - currentPrice) * units;
  }
  if (pos._status === 'closed' && exitP != null && entryP != null) {
    return dir === 'long' ? (exitP - entryP) * units : (entryP - exitP) * units;
  }
  return 0;
};

export const computePosPips = (
  pos: TaskPosition & { _status: 'open' | 'closed' },
  currentPrice: number | null,
  pipSize: number | null | undefined
): number => {
  if (!pipSize) return 0;
  const entryP = pos.entry_price ? parseFloat(pos.entry_price) : null;
  if (entryP == null || !Number.isFinite(entryP)) return 0;
  const dir = String(pos.direction).toLowerCase();
  if (pos._status === 'open' && currentPrice != null) {
    const diff = dir === 'long' ? currentPrice - entryP : entryP - currentPrice;
    const pips = diff / pipSize;
    return Number.isFinite(pips) ? pips : 0;
  }
  const exitP = pos.exit_price ? parseFloat(pos.exit_price) : null;
  if (exitP != null && Number.isFinite(exitP)) {
    const diff = dir === 'long' ? exitP - entryP : entryP - exitP;
    const pips = diff / pipSize;
    return Number.isFinite(pips) ? pips : 0;
  }
  return 0;
};
