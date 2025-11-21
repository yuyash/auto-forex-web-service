/**
 * Unit tests for chart data transformation utilities
 */

import { describe, it, expect } from 'vitest';
import {
  transformCandles,
  convertBackendTradeToFrontend,
  getGranularityDuration,
  calculateBufferedRange,
  type APICandle,
  type BackendTrade,
} from './chartDataTransform';

describe('transformCandles', () => {
  it('should transform API candles to chart format', () => {
    const apiCandles: APICandle[] = [
      {
        time: 1704067200, // 2024-01-01 00:00:00 UTC
        open: 1.1,
        high: 1.2,
        low: 1.0,
        close: 1.15,
        volume: 1000,
      },
      {
        time: 1704070800, // 2024-01-01 01:00:00 UTC
        open: 1.15,
        high: 1.25,
        low: 1.1,
        close: 1.2,
        volume: 1500,
      },
    ];

    const result = transformCandles(apiCandles);

    expect(result).toHaveLength(2);
    expect(result[0].date).toEqual(new Date(1704067200 * 1000));
    expect(result[0].open).toBe(1.1);
    expect(result[0].high).toBe(1.2);
    expect(result[0].low).toBe(1.0);
    expect(result[0].close).toBe(1.15);
    expect(result[0].volume).toBe(1000);
  });

  it('should handle empty array', () => {
    const result = transformCandles([]);
    expect(result).toEqual([]);
  });

  it('should preserve all OHLC values', () => {
    const apiCandles: APICandle[] = [
      {
        time: 1704067200,
        open: 1.23456,
        high: 1.34567,
        low: 1.12345,
        close: 1.28901,
        volume: 5000,
      },
    ];

    const result = transformCandles(apiCandles);

    expect(result[0].open).toBe(1.23456);
    expect(result[0].high).toBe(1.34567);
    expect(result[0].low).toBe(1.12345);
    expect(result[0].close).toBe(1.28901);
    expect(result[0].volume).toBe(5000);
  });
});

describe('convertBackendTradeToFrontend', () => {
  it('should convert backend trade format to frontend format', () => {
    const backendTrade: BackendTrade = {
      opened_at: '2024-01-01T10:00:00Z',
      closed_at: '2024-01-01T11:00:00Z',
      instrument: 'EUR_USD',
      direction: 'long',
      units: 1000,
      entry_price: 1.1,
      exit_price: 1.15,
      pnl: 50.0,
      duration: '1h',
    };

    const result = convertBackendTradeToFrontend(backendTrade);

    expect(result.entry_time).toBe('2024-01-01T10:00:00Z');
    expect(result.exit_time).toBe('2024-01-01T11:00:00Z');
    expect(result.instrument).toBe('EUR_USD');
    expect(result.direction).toBe('long');
    expect(result.units).toBe(1000);
    expect(result.entry_price).toBe(1.1);
    expect(result.exit_price).toBe(1.15);
    expect(result.pnl).toBe(50.0);
    expect(result.duration).toBe('1h');
  });

  it('should handle trade without duration', () => {
    const backendTrade: BackendTrade = {
      opened_at: '2024-01-01T10:00:00Z',
      closed_at: '2024-01-01T11:00:00Z',
      instrument: 'EUR_USD',
      direction: 'short',
      units: 500,
      entry_price: 1.2,
      exit_price: 1.18,
      pnl: 10.0,
    };

    const result = convertBackendTradeToFrontend(backendTrade);

    expect(result.duration).toBeUndefined();
  });
});

describe('getGranularityDuration', () => {
  it('should calculate duration for M1 (1 minute)', () => {
    expect(getGranularityDuration('M1')).toBe(60 * 1000);
  });

  it('should calculate duration for M5 (5 minutes)', () => {
    expect(getGranularityDuration('M5')).toBe(5 * 60 * 1000);
  });

  it('should calculate duration for M15 (15 minutes)', () => {
    expect(getGranularityDuration('M15')).toBe(15 * 60 * 1000);
  });

  it('should calculate duration for H1 (1 hour)', () => {
    expect(getGranularityDuration('H1')).toBe(60 * 60 * 1000);
  });

  it('should calculate duration for H4 (4 hours)', () => {
    expect(getGranularityDuration('H4')).toBe(4 * 60 * 60 * 1000);
  });

  it('should calculate duration for D (1 day)', () => {
    expect(getGranularityDuration('D')).toBe(24 * 60 * 60 * 1000);
  });

  it('should calculate duration for W (1 week)', () => {
    expect(getGranularityDuration('W')).toBe(7 * 24 * 60 * 60 * 1000);
  });

  it('should calculate duration for S1 (1 second)', () => {
    expect(getGranularityDuration('S1')).toBe(1000);
  });

  it('should default to H1 for unknown granularity', () => {
    expect(getGranularityDuration('X1')).toBe(60 * 60 * 1000);
  });
});

describe('calculateBufferedRange', () => {
  it('should add buffer candles before and after date range', () => {
    const startDate = new Date('2024-01-01T10:00:00Z');
    const endDate = new Date('2024-01-01T12:00:00Z');
    const granularity = 'H1';

    const result = calculateBufferedRange(startDate, endDate, granularity);

    // Buffer is 3 candles of 1 hour each = 3 hours
    expect(result.from).toEqual(new Date('2024-01-01T07:00:00Z'));
    expect(result.to).toEqual(new Date('2024-01-01T15:00:00Z'));
  });

  it('should calculate buffer for M5 granularity', () => {
    const startDate = new Date('2024-01-01T10:00:00Z');
    const endDate = new Date('2024-01-01T10:30:00Z');
    const granularity = 'M5';

    const result = calculateBufferedRange(startDate, endDate, granularity);

    // Buffer is 3 candles of 5 minutes each = 15 minutes
    expect(result.from).toEqual(new Date('2024-01-01T09:45:00Z'));
    expect(result.to).toEqual(new Date('2024-01-01T10:45:00Z'));
  });

  it('should calculate buffer for D granularity', () => {
    const startDate = new Date('2024-01-01T00:00:00Z');
    const endDate = new Date('2024-01-05T00:00:00Z');
    const granularity = 'D';

    const result = calculateBufferedRange(startDate, endDate, granularity);

    // Buffer is 3 candles of 1 day each = 3 days
    expect(result.from).toEqual(new Date('2023-12-29T00:00:00Z'));
    expect(result.to).toEqual(new Date('2024-01-08T00:00:00Z'));
  });

  it('should handle same start and end date', () => {
    const date = new Date('2024-01-01T10:00:00Z');
    const granularity = 'M15';

    const result = calculateBufferedRange(date, date, granularity);

    // Buffer is 3 candles of 15 minutes each = 45 minutes
    expect(result.from).toEqual(new Date('2024-01-01T09:15:00Z'));
    expect(result.to).toEqual(new Date('2024-01-01T10:45:00Z'));
  });
});
