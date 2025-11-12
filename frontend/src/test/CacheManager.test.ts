import { describe, it, expect, beforeEach } from 'vitest';
import { CacheManager } from '../utils/CacheManager';
import type { OHLCData } from '../types/chart';

describe('CacheManager', () => {
  let cacheManager: CacheManager;

  beforeEach(() => {
    cacheManager = new CacheManager();
  });

  describe('getCacheKey', () => {
    it('should generate unique cache key from instrument and granularity', () => {
      const key = cacheManager.getCacheKey('EUR_USD', 'M5');
      expect(key).toBe('EUR_USD_M5');
    });

    it('should generate different keys for different instrument', () => {
      const key1 = cacheManager.getCacheKey('EUR_USD', 'M5');
      const key2 = cacheManager.getCacheKey('GBP_USD', 'M5');
      expect(key1).not.toBe(key2);
    });

    it('should generate different keys for different granularities', () => {
      const key1 = cacheManager.getCacheKey('EUR_USD', 'M5');
      const key2 = cacheManager.getCacheKey('EUR_USD', 'H1');
      expect(key1).not.toBe(key2);
    });
  });

  describe('get', () => {
    it('should return null for non-existent cache entry', () => {
      const result = cacheManager.get('EUR_USD', 'M5');
      expect(result).toBeNull();
    });

    it('should retrieve cached data after set', () => {
      const testData: OHLCData[] = [
        { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
      ];
      cacheManager.set('EUR_USD', 'M5', testData);
      const result = cacheManager.get('EUR_USD', 'M5');
      expect(result).toEqual(testData);
    });

    it('should return empty array for empty cache entry', () => {
      cacheManager.set('EUR_USD', 'M5', []);
      const result = cacheManager.get('EUR_USD', 'M5');
      expect(result).toEqual([]);
    });
  });

  describe('set', () => {
    it('should store data in cache', () => {
      const testData: OHLCData[] = [
        { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
        { time: 2000, open: 1.15, high: 1.25, low: 1.1, close: 1.2 },
      ];
      cacheManager.set('EUR_USD', 'M5', testData);
      const result = cacheManager.get('EUR_USD', 'M5');
      expect(result).toEqual(testData);
    });

    it('should sort data by timestamp', () => {
      const unsortedData: OHLCData[] = [
        { time: 3000, open: 1.2, high: 1.3, low: 1.15, close: 1.25 },
        { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
        { time: 2000, open: 1.15, high: 1.25, low: 1.1, close: 1.2 },
      ];
      cacheManager.set('EUR_USD', 'M5', unsortedData);
      const result = cacheManager.get('EUR_USD', 'M5');
      expect(result![0].time).toBe(1000);
      expect(result![1].time).toBe(2000);
      expect(result![2].time).toBe(3000);
    });

    it('should replace existing data', () => {
      const data1: OHLCData[] = [
        { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
      ];
      const data2: OHLCData[] = [
        { time: 2000, open: 1.15, high: 1.25, low: 1.1, close: 1.2 },
      ];
      cacheManager.set('EUR_USD', 'M5', data1);
      cacheManager.set('EUR_USD', 'M5', data2);
      const result = cacheManager.get('EUR_USD', 'M5');
      expect(result).toEqual(data2);
    });

    it('should handle empty data array', () => {
      cacheManager.set('EUR_USD', 'M5', []);
      const result = cacheManager.get('EUR_USD', 'M5');
      expect(result).toEqual([]);
    });
  });

  describe('merge', () => {
    it('should merge new data with existing cache', () => {
      const existingData: OHLCData[] = [
        { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
      ];
      const newData: OHLCData[] = [
        { time: 2000, open: 1.15, high: 1.25, low: 1.1, close: 1.2 },
      ];
      cacheManager.set('EUR_USD', 'M5', existingData);
      cacheManager.merge('EUR_USD', 'M5', newData);
      const result = cacheManager.get('EUR_USD', 'M5');
      expect(result).toHaveLength(2);
      expect(result![0].time).toBe(1000);
      expect(result![1].time).toBe(2000);
    });

    it('should remove duplicate timestamps', () => {
      const existingData: OHLCData[] = [
        { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
        { time: 2000, open: 1.15, high: 1.25, low: 1.1, close: 1.2 },
      ];
      const newData: OHLCData[] = [
        { time: 2000, open: 1.16, high: 1.26, low: 1.12, close: 1.21 },
        { time: 3000, open: 1.2, high: 1.3, low: 1.15, close: 1.25 },
      ];
      cacheManager.set('EUR_USD', 'M5', existingData);
      cacheManager.merge('EUR_USD', 'M5', newData);
      const result = cacheManager.get('EUR_USD', 'M5');
      expect(result).toHaveLength(3);
      expect(result![1].time).toBe(2000);
      expect(result![1].open).toBe(1.16); // Should use newer data
    });

    it('should maintain sorted order after merge', () => {
      const existingData: OHLCData[] = [
        { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
        { time: 3000, open: 1.2, high: 1.3, low: 1.15, close: 1.25 },
      ];
      const newData: OHLCData[] = [
        { time: 2000, open: 1.15, high: 1.25, low: 1.1, close: 1.2 },
      ];
      cacheManager.set('EUR_USD', 'M5', existingData);
      cacheManager.merge('EUR_USD', 'M5', newData);
      const result = cacheManager.get('EUR_USD', 'M5');
      expect(result![0].time).toBe(1000);
      expect(result![1].time).toBe(2000);
      expect(result![2].time).toBe(3000);
    });

    it('should set new data if no existing cache', () => {
      const newData: OHLCData[] = [
        { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
      ];
      cacheManager.merge('EUR_USD', 'M5', newData);
      const result = cacheManager.get('EUR_USD', 'M5');
      expect(result).toEqual(newData);
    });

    it('should handle empty new data', () => {
      const existingData: OHLCData[] = [
        { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
      ];
      cacheManager.set('EUR_USD', 'M5', existingData);
      cacheManager.merge('EUR_USD', 'M5', []);
      const result = cacheManager.get('EUR_USD', 'M5');
      expect(result).toEqual(existingData);
    });
  });

  describe('clear', () => {
    it('should clear specific cache entry', () => {
      const testData: OHLCData[] = [
        { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
      ];
      cacheManager.set('EUR_USD', 'M5', testData);
      cacheManager.set('GBP_USD', 'M5', testData);
      cacheManager.clear('EUR_USD', 'M5');
      expect(cacheManager.get('EUR_USD', 'M5')).toBeNull();
      expect(cacheManager.get('GBP_USD', 'M5')).toEqual(testData);
    });

    it('should clear entire cache when no parameters provided', () => {
      const testData: OHLCData[] = [
        { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
      ];
      cacheManager.set('EUR_USD', 'M5', testData);
      cacheManager.set('GBP_USD', 'M5', testData);
      cacheManager.set('EUR_USD', 'H1', testData);
      cacheManager.clear();
      expect(cacheManager.get('EUR_USD', 'M5')).toBeNull();
      expect(cacheManager.get('GBP_USD', 'M5')).toBeNull();
      expect(cacheManager.get('EUR_USD', 'H1')).toBeNull();
    });
  });

  describe('getTimeRange', () => {
    it('should return null for non-existent cache entry', () => {
      const result = cacheManager.getTimeRange('EUR_USD', 'M5');
      expect(result).toBeNull();
    });

    it('should return null for empty cache entry', () => {
      cacheManager.set('EUR_USD', 'M5', []);
      const result = cacheManager.getTimeRange('EUR_USD', 'M5');
      expect(result).toBeNull();
    });

    it('should return correct time range for cached data', () => {
      const testData: OHLCData[] = [
        { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
        { time: 2000, open: 1.15, high: 1.25, low: 1.1, close: 1.2 },
        { time: 3000, open: 1.2, high: 1.3, low: 1.15, close: 1.25 },
      ];
      cacheManager.set('EUR_USD', 'M5', testData);
      const result = cacheManager.getTimeRange('EUR_USD', 'M5');
      expect(result).toEqual({ oldest: 1000, newest: 3000 });
    });

    it('should update time range after merge', () => {
      const existingData: OHLCData[] = [
        { time: 2000, open: 1.15, high: 1.25, low: 1.1, close: 1.2 },
      ];
      const newData: OHLCData[] = [
        { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
        { time: 3000, open: 1.2, high: 1.3, low: 1.15, close: 1.25 },
      ];
      cacheManager.set('EUR_USD', 'M5', existingData);
      cacheManager.merge('EUR_USD', 'M5', newData);
      const result = cacheManager.getTimeRange('EUR_USD', 'M5');
      expect(result).toEqual({ oldest: 1000, newest: 3000 });
    });

    it('should handle single data point', () => {
      const testData: OHLCData[] = [
        { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
      ];
      cacheManager.set('EUR_USD', 'M5', testData);
      const result = cacheManager.getTimeRange('EUR_USD', 'M5');
      expect(result).toEqual({ oldest: 1000, newest: 1000 });
    });
  });

  describe('integration scenarios', () => {
    it('should handle single instrument and granularities independently', () => {
      const eurData: OHLCData[] = [
        { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
      ];
      const gbpData: OHLCData[] = [
        { time: 2000, open: 1.3, high: 1.4, low: 1.2, close: 1.35 },
      ];
      cacheManager.set('EUR_USD', 'M5', eurData);
      cacheManager.set('GBP_USD', 'M5', gbpData);
      cacheManager.set('EUR_USD', 'H1', gbpData);

      expect(cacheManager.get('EUR_USD', 'M5')).toEqual(eurData);
      expect(cacheManager.get('GBP_USD', 'M5')).toEqual(gbpData);
      expect(cacheManager.get('EUR_USD', 'H1')).toEqual(gbpData);
    });

    it('should handle complex merge with overlapping and new data', () => {
      const initial: OHLCData[] = [
        { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
        { time: 2000, open: 1.15, high: 1.25, low: 1.1, close: 1.2 },
        { time: 3000, open: 1.2, high: 1.3, low: 1.15, close: 1.25 },
      ];
      const additional: OHLCData[] = [
        { time: 500, open: 1.05, high: 1.15, low: 0.95, close: 1.1 },
        { time: 2000, open: 1.16, high: 1.26, low: 1.12, close: 1.21 },
        { time: 4000, open: 1.25, high: 1.35, low: 1.2, close: 1.3 },
      ];
      cacheManager.set('EUR_USD', 'M5', initial);
      cacheManager.merge('EUR_USD', 'M5', additional);
      const result = cacheManager.get('EUR_USD', 'M5');

      expect(result).toHaveLength(5);
      expect(result![0].time).toBe(500);
      expect(result![1].time).toBe(1000);
      expect(result![2].time).toBe(2000);
      expect(result![2].open).toBe(1.16); // Updated value
      expect(result![3].time).toBe(3000);
      expect(result![4].time).toBe(4000);
    });
  });
});
