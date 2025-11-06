import type { OHLCData } from '../types/chart';

/**
 * Interface for cached candle data with metadata
 */
interface CachedCandleData {
  data: OHLCData[];
  oldestTime: number;
  newestTime: number;
  lastUpdated: number;
}

/**
 * Interface for time range information
 */
interface TimeRange {
  oldest: number;
  newest: number;
}

/**
 * CacheManager handles client-side storage of fetched candle data
 * organized by instrument and granularity.
 *
 * Features:
 * - Map-based storage for O(1) lookup performance
 * - Automatic deduplication and sorting by timestamp
 * - Time range tracking for boundary detection
 * - Efficient merge operations for new data
 */
export class CacheManager {
  private cache: Map<string, CachedCandleData>;

  constructor() {
    this.cache = new Map();
  }

  /**
   * Generates a unique cache key from instrument and granularity
   * @param instrument - Trading instrument (e.g., "EUR_USD")
   * @param granularity - Candle granularity (e.g., "M5")
   * @returns Cache key in format "instrument_granularity"
   */
  getCacheKey(instrument: string, granularity: string): string {
    return `${instrument}_${granularity}`;
  }

  /**
   * Retrieves cached data for a specific instrument and granularity
   * @param instrument - Trading instrument
   * @param granularity - Candle granularity
   * @returns Array of OHLC data or null if not cached
   */
  get(instrument: string, granularity: string): OHLCData[] | null {
    const key = this.getCacheKey(instrument, granularity);
    const cached = this.cache.get(key);
    return cached ? cached.data : null;
  }

  /**
   * Stores new data in the cache, replacing any existing data
   * @param instrument - Trading instrument
   * @param granularity - Candle granularity
   * @param data - Array of OHLC data to cache
   */
  set(instrument: string, granularity: string, data: OHLCData[]): void {
    const key = this.getCacheKey(instrument, granularity);

    if (data.length === 0) {
      this.cache.set(key, {
        data: [],
        oldestTime: 0,
        newestTime: 0,
        lastUpdated: Date.now(),
      });
      return;
    }

    // Sort data by timestamp to ensure correct ordering
    const sortedData = [...data].sort((a, b) => a.time - b.time);

    this.cache.set(key, {
      data: sortedData,
      oldestTime: sortedData[0].time,
      newestTime: sortedData[sortedData.length - 1].time,
      lastUpdated: Date.now(),
    });
  }

  /**
   * Merges new data with existing cache, removing duplicates
   * Maintains sorted order by timestamp
   * @param instrument - Trading instrument
   * @param granularity - Candle granularity
   * @param newData - Array of new OHLC data to merge
   */
  merge(instrument: string, granularity: string, newData: OHLCData[]): void {
    const key = this.getCacheKey(instrument, granularity);
    const existing = this.cache.get(key);

    if (!existing || existing.data.length === 0) {
      // No existing data, just set the new data
      this.set(instrument, granularity, newData);
      return;
    }

    if (newData.length === 0) {
      // No new data to merge
      return;
    }

    // Combine existing and new data
    const combined = [...existing.data, ...newData];

    // Remove duplicates based on timestamp using a Map
    const uniqueMap = new Map<number, OHLCData>();
    combined.forEach((candle) => {
      uniqueMap.set(candle.time, candle);
    });

    // Convert back to array and sort by timestamp
    const mergedData = Array.from(uniqueMap.values()).sort(
      (a, b) => a.time - b.time
    );

    // Update cache with merged data
    this.cache.set(key, {
      data: mergedData,
      oldestTime: mergedData[0].time,
      newestTime: mergedData[mergedData.length - 1].time,
      lastUpdated: Date.now(),
    });
  }

  /**
   * Clears cache for specific instrument/granularity or entire cache
   * @param instrument - Optional trading instrument to clear
   * @param granularity - Optional candle granularity to clear
   */
  clear(instrument?: string, granularity?: string): void {
    if (instrument && granularity) {
      // Clear specific cache entry
      const key = this.getCacheKey(instrument, granularity);
      this.cache.delete(key);
    } else {
      // Clear entire cache
      this.cache.clear();
    }
  }

  /**
   * Gets the time range (oldest and newest timestamps) for cached data
   * @param instrument - Trading instrument
   * @param granularity - Candle granularity
   * @returns TimeRange object or null if no data cached
   */
  getTimeRange(instrument: string, granularity: string): TimeRange | null {
    const key = this.getCacheKey(instrument, granularity);
    const cached = this.cache.get(key);

    if (!cached || cached.data.length === 0) {
      return null;
    }

    return {
      oldest: cached.oldestTime,
      newest: cached.newestTime,
    };
  }
}
