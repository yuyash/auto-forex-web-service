/**
 * Unit tests for technical indicator calculations.
 * Verifies SMA, EMA, Bollinger Bands, and support/resistance detection.
 */

import { describe, it, expect } from 'vitest';
import {
  calcSMA,
  calcEMA,
  calcBollinger,
  detectSupportResistance,
  type CandleInput,
} from '../../../src/utils/technicalIndicators';

function makeCandles(closes: number[], startTime = 1000): CandleInput[] {
  return closes.map((close, i) => ({
    time: startTime + i * 60,
    open: close - 0.5,
    high: close + 1,
    low: close - 1,
    close,
  }));
}

describe('calcSMA', () => {
  it('returns empty for insufficient data', () => {
    expect(calcSMA(makeCandles([1, 2]), 3)).toEqual([]);
  });

  it('calculates correct SMA values', () => {
    const candles = makeCandles([10, 20, 30, 40, 50]);
    const sma = calcSMA(candles, 3);
    // SMA(3) at index 2: (10+20+30)/3 = 20
    // SMA(3) at index 3: (20+30+40)/3 = 30
    // SMA(3) at index 4: (30+40+50)/3 = 40
    expect(sma).toHaveLength(3);
    expect(sma[0].value).toBeCloseTo(20);
    expect(sma[1].value).toBeCloseTo(30);
    expect(sma[2].value).toBeCloseTo(40);
  });

  it('preserves timestamps', () => {
    const candles = makeCandles([10, 20, 30], 5000);
    const sma = calcSMA(candles, 2);
    expect(sma[0].time).toBe(5060); // second candle's time
  });
});

describe('calcEMA', () => {
  it('returns empty for insufficient data', () => {
    expect(calcEMA(makeCandles([1]), 3)).toEqual([]);
  });

  it('seeds with SMA of first period candles', () => {
    const candles = makeCandles([10, 20, 30, 40, 50]);
    const ema = calcEMA(candles, 3);
    // First EMA value = SMA of first 3 = (10+20+30)/3 = 20
    expect(ema[0].value).toBeCloseTo(20);
  });

  it('applies exponential weighting', () => {
    const candles = makeCandles([10, 20, 30, 40, 50]);
    const ema = calcEMA(candles, 3);
    // k = 2/(3+1) = 0.5
    // EMA[1] = 40 * 0.5 + 20 * 0.5 = 30
    expect(ema[1].value).toBeCloseTo(30);
    // EMA[2] = 50 * 0.5 + 30 * 0.5 = 40
    expect(ema[2].value).toBeCloseTo(40);
  });
});

describe('calcBollinger', () => {
  it('returns empty bands for insufficient data', () => {
    const result = calcBollinger(makeCandles([1, 2, 3]), 5);
    expect(result.middle).toEqual([]);
    expect(result.upper).toEqual([]);
    expect(result.lower).toEqual([]);
  });

  it('middle band equals SMA', () => {
    const closes = Array.from({ length: 25 }, (_, i) => 100 + i);
    const candles = makeCandles(closes);
    const bb = calcBollinger(candles, 20, 2);
    const sma = calcSMA(candles, 20);

    expect(bb.middle).toHaveLength(sma.length);
    bb.middle.forEach((pt, i) => {
      expect(pt.value).toBeCloseTo(sma[i].value);
    });
  });

  it('upper > middle > lower', () => {
    const closes = Array.from({ length: 25 }, (_, i) => 100 + Math.sin(i) * 5);
    const candles = makeCandles(closes);
    const bb = calcBollinger(candles, 20, 2);

    bb.middle.forEach((_, i) => {
      expect(bb.upper[i].value).toBeGreaterThan(bb.middle[i].value);
      expect(bb.middle[i].value).toBeGreaterThan(bb.lower[i].value);
    });
  });
});

describe('detectSupportResistance', () => {
  it('returns empty for insufficient data', () => {
    expect(detectSupportResistance(makeCandles([1, 2, 3]))).toEqual([]);
  });

  it('detects resistance at local highs', () => {
    // Create a clear peak at index 5
    const closes = [10, 11, 12, 13, 14, 20, 14, 13, 12, 11, 10];
    const candles = closes.map((c, i) => ({
      time: 1000 + i * 60,
      open: c,
      high: c + 0.5,
      low: c - 0.5,
      close: c,
    }));
    const levels = detectSupportResistance(candles, 4, 50);
    const resistanceLevels = levels.filter((l) => l.type === 'resistance');
    expect(resistanceLevels.length).toBeGreaterThanOrEqual(1);
  });

  it('respects maxLevels parameter', () => {
    // Create multiple peaks and valleys
    const closes = [10, 15, 10, 15, 10, 15, 10, 15, 10, 15, 10];
    const candles = closes.map((c, i) => ({
      time: 1000 + i * 60,
      open: c,
      high: c + 0.5,
      low: c - 0.5,
      close: c,
    }));
    const levels = detectSupportResistance(candles, 2, 50);
    expect(levels.length).toBeLessThanOrEqual(2);
  });
});
