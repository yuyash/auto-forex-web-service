/**
 * Unit tests for CacheManager.
 * Verifies get/set/merge/clear and time range tracking.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { CacheManager } from '../../../src/utils/CacheManager';
import type { OHLCData } from '../../../src/types/chart';

function candle(time: number, close = 1.0): OHLCData {
  return {
    time,
    open: close,
    high: close + 0.01,
    low: close - 0.01,
    close,
    volume: 100,
  } as OHLCData;
}

describe('CacheManager', () => {
  let cache: CacheManager;

  beforeEach(() => {
    cache = new CacheManager();
  });

  it('returns null for uncached data', () => {
    expect(cache.get('EUR_USD', 'M5')).toBeNull();
  });

  it('stores and retrieves data', () => {
    const data = [candle(100), candle(200)];
    cache.set('EUR_USD', 'M5', data);
    expect(cache.get('EUR_USD', 'M5')).toHaveLength(2);
  });

  it('sorts data by timestamp on set', () => {
    cache.set('EUR_USD', 'M5', [candle(300), candle(100), candle(200)]);
    const result = cache.get('EUR_USD', 'M5')!;
    expect(result[0].time).toBe(100);
    expect(result[2].time).toBe(300);
  });

  it('handles empty data on set', () => {
    cache.set('EUR_USD', 'M5', []);
    expect(cache.get('EUR_USD', 'M5')).toEqual([]);
  });

  it('generates correct cache keys', () => {
    expect(cache.getCacheKey('EUR_USD', 'M5')).toBe('EUR_USD_M5');
    expect(cache.getCacheKey('GBP_JPY', 'H1')).toBe('GBP_JPY_H1');
  });

  it('keeps separate caches per instrument/granularity', () => {
    cache.set('EUR_USD', 'M5', [candle(100)]);
    cache.set('EUR_USD', 'H1', [candle(200), candle(300)]);
    expect(cache.get('EUR_USD', 'M5')).toHaveLength(1);
    expect(cache.get('EUR_USD', 'H1')).toHaveLength(2);
  });

  describe('merge', () => {
    it('merges new data with existing', () => {
      cache.set('EUR_USD', 'M5', [candle(100), candle(200)]);
      cache.merge('EUR_USD', 'M5', [candle(300)]);
      expect(cache.get('EUR_USD', 'M5')).toHaveLength(3);
    });

    it('deduplicates by timestamp', () => {
      cache.set('EUR_USD', 'M5', [candle(100), candle(200)]);
      cache.merge('EUR_USD', 'M5', [candle(200, 2.0), candle(300)]);
      const result = cache.get('EUR_USD', 'M5')!;
      expect(result).toHaveLength(3);
      // Duplicate timestamp should use the newer value
      expect(result[1].close).toBe(2.0);
    });

    it('sets data when no existing cache', () => {
      cache.merge('EUR_USD', 'M5', [candle(100)]);
      expect(cache.get('EUR_USD', 'M5')).toHaveLength(1);
    });

    it('does nothing when merging empty data', () => {
      cache.set('EUR_USD', 'M5', [candle(100)]);
      cache.merge('EUR_USD', 'M5', []);
      expect(cache.get('EUR_USD', 'M5')).toHaveLength(1);
    });
  });

  describe('clear', () => {
    it('clears specific instrument/granularity', () => {
      cache.set('EUR_USD', 'M5', [candle(100)]);
      cache.set('EUR_USD', 'H1', [candle(200)]);
      cache.clear('EUR_USD', 'M5');
      expect(cache.get('EUR_USD', 'M5')).toBeNull();
      expect(cache.get('EUR_USD', 'H1')).toHaveLength(1);
    });

    it('clears entire cache', () => {
      cache.set('EUR_USD', 'M5', [candle(100)]);
      cache.set('GBP_JPY', 'H1', [candle(200)]);
      cache.clear();
      expect(cache.get('EUR_USD', 'M5')).toBeNull();
      expect(cache.get('GBP_JPY', 'H1')).toBeNull();
    });
  });

  describe('getTimeRange', () => {
    it('returns null for uncached data', () => {
      expect(cache.getTimeRange('EUR_USD', 'M5')).toBeNull();
    });

    it('returns null for empty data', () => {
      cache.set('EUR_USD', 'M5', []);
      expect(cache.getTimeRange('EUR_USD', 'M5')).toBeNull();
    });

    it('returns correct oldest and newest timestamps', () => {
      cache.set('EUR_USD', 'M5', [candle(100), candle(300), candle(200)]);
      const range = cache.getTimeRange('EUR_USD', 'M5');
      expect(range).toEqual({ oldest: 100, newest: 300 });
    });
  });
});
