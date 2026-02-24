/**
 * Technical indicator calculation utilities for OHLC chart overlays.
 */

export interface CandleInput {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface LinePoint {
  time: number;
  value: number;
}

/**
 * Simple Moving Average (SMA)
 */
export function calcSMA(candles: CandleInput[], period: number): LinePoint[] {
  const result: LinePoint[] = [];
  if (candles.length < period) return result;
  let sum = 0;
  for (let i = 0; i < candles.length; i++) {
    sum += candles[i].close;
    if (i >= period) sum -= candles[i - period].close;
    if (i >= period - 1) {
      result.push({ time: candles[i].time, value: sum / period });
    }
  }
  return result;
}

/**
 * Exponential Moving Average (EMA)
 */
export function calcEMA(candles: CandleInput[], period: number): LinePoint[] {
  const result: LinePoint[] = [];
  if (candles.length < period) return result;
  const k = 2 / (period + 1);
  // Seed with SMA of first `period` candles
  let sum = 0;
  for (let i = 0; i < period; i++) sum += candles[i].close;
  let ema = sum / period;
  result.push({ time: candles[period - 1].time, value: ema });
  for (let i = period; i < candles.length; i++) {
    ema = candles[i].close * k + ema * (1 - k);
    result.push({ time: candles[i].time, value: ema });
  }
  return result;
}

/**
 * Bollinger Bands (SMA ± stddev * multiplier)
 */
export interface BollingerResult {
  middle: LinePoint[];
  upper: LinePoint[];
  lower: LinePoint[];
}

export function calcBollinger(
  candles: CandleInput[],
  period: number = 20,
  multiplier: number = 2
): BollingerResult {
  const middle: LinePoint[] = [];
  const upper: LinePoint[] = [];
  const lower: LinePoint[] = [];
  if (candles.length < period) return { middle, upper, lower };

  for (let i = period - 1; i < candles.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += candles[j].close;
    const sma = sum / period;
    let sqSum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sqSum += (candles[j].close - sma) ** 2;
    }
    const std = Math.sqrt(sqSum / period);
    const t = candles[i].time;
    middle.push({ time: t, value: sma });
    upper.push({ time: t, value: sma + multiplier * std });
    lower.push({ time: t, value: sma - multiplier * std });
  }
  return { middle, upper, lower };
}

/**
 * Detect simple support/resistance levels from recent highs/lows.
 * Returns up to `maxLevels` price levels.
 */
export function detectSupportResistance(
  candles: CandleInput[],
  maxLevels: number = 4,
  lookback: number = 50
): { price: number; type: 'support' | 'resistance' }[] {
  const slice = candles.slice(-lookback);
  if (slice.length < 5) return [];

  const pivots: { price: number; type: 'support' | 'resistance' }[] = [];

  for (let i = 2; i < slice.length - 2; i++) {
    const c = slice[i];
    // Local high
    if (
      c.high > slice[i - 1].high &&
      c.high > slice[i - 2].high &&
      c.high > slice[i + 1].high &&
      c.high > slice[i + 2].high
    ) {
      pivots.push({ price: c.high, type: 'resistance' });
    }
    // Local low
    if (
      c.low < slice[i - 1].low &&
      c.low < slice[i - 2].low &&
      c.low < slice[i + 1].low &&
      c.low < slice[i + 2].low
    ) {
      pivots.push({ price: c.low, type: 'support' });
    }
  }

  // Cluster nearby levels and keep strongest
  const tolerance =
    slice.length > 0
      ? (Math.max(...slice.map((c) => c.high)) -
          Math.min(...slice.map((c) => c.low))) *
        0.005
      : 0;

  const clustered: {
    price: number;
    type: 'support' | 'resistance';
    count: number;
  }[] = [];
  for (const p of pivots) {
    const existing = clustered.find(
      (c) => Math.abs(c.price - p.price) < tolerance
    );
    if (existing) {
      existing.count++;
      existing.price = (existing.price + p.price) / 2;
    } else {
      clustered.push({ ...p, count: 1 });
    }
  }

  clustered.sort((a, b) => b.count - a.count);
  return clustered
    .slice(0, maxLevels)
    .map(({ price, type }) => ({ price, type }));
}
