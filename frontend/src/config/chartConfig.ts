/**
 * Chart Configuration Constants
 *
 * This file contains all default configuration values for the financial charts
 * including granularity settings, data fetching parameters, auto-refresh settings,
 * error handling constants, and buffer/scroll/zoom thresholds.
 */

import type { OandaGranularity } from '../types/oanda';

export const CHART_CONFIG = {
  // Granularity
  DEFAULT_GRANULARITY: 'H1' as OandaGranularity,

  // Data fetching
  DEFAULT_FETCH_COUNT: 100, // Number of candles to fetch initially
  SCROLL_LOAD_COUNT: 500, // Number of candles to load when scrolling
  MAX_FETCH_COUNT: 5000, // Maximum candles per API request

  // Auto-refresh (for Dashboard and Trading Task charts only)
  DEFAULT_AUTO_REFRESH_ENABLED: true,
  DEFAULT_AUTO_REFRESH_INTERVAL: 60000, // 60 seconds in milliseconds
  AUTO_REFRESH_INTERVALS: [
    { label: '10 seconds', value: 10000 },
    { label: '30 seconds', value: 30000 },
    { label: '1 minute', value: 60000 },
    { label: '2 minutes', value: 120000 },
    { label: '5 minutes', value: 300000 },
  ],

  // Chart dimensions
  DEFAULT_HEIGHT: 500,
  MIN_HEIGHT: 300,
  MAX_HEIGHT: 1000,

  // Buffer for backtest charts
  BACKTEST_BUFFER_CANDLES: 3, // Number of candles to show before/after backtest range

  // Scroll/zoom thresholds
  SCROLL_LOAD_THRESHOLD: 10, // Load more data when within 10 candles of edge
  MIN_VISIBLE_CANDLES: 20,
  MAX_VISIBLE_CANDLES: 500,

  // Error handling
  MAX_RETRY_ATTEMPTS: 3,
  RETRY_DELAYS: [1000, 2000, 4000], // Exponential backoff delays in ms
} as const;

/**
 * Chart preferences stored in localStorage
 */
export interface ChartPreferences {
  instrument: string;
  granularity: OandaGranularity;
  autoRefreshEnabled: boolean;
  refreshInterval: number; // milliseconds
  showBuySellMarkers: boolean;
  showStartEndMarkers: boolean;
}

/**
 * Available granularities for chart display
 */
export const AVAILABLE_GRANULARITIES: OandaGranularity[] = [
  'M1',
  'M5',
  'M15',
  'H1',
  'H4',
  'D',
];

/**
 * Get available granularities for selection
 */
export function getAvailableGranularities(): OandaGranularity[] {
  return AVAILABLE_GRANULARITIES;
}

/**
 * Calculate appropriate granularity based on duration
 * @param startDate - Start date of the time range
 * @param endDate - End date of the time range
 * @returns Appropriate granularity for the duration
 */
export function calculateGranularity(
  startDate: Date,
  endDate: Date
): OandaGranularity {
  const durationMs = endDate.getTime() - startDate.getTime();
  const durationHours = durationMs / (1000 * 60 * 60);

  // Less than 6 hours: use M1
  if (durationHours < 6) {
    return 'M1';
  }
  // Less than 24 hours: use M5
  if (durationHours < 24) {
    return 'M5';
  }
  // Less than 3 days: use M15
  if (durationHours < 72) {
    return 'M15';
  }
  // Less than 2 weeks: use H1
  if (durationHours < 336) {
    return 'H1';
  }
  // Less than 2 months: use H4
  if (durationHours < 1440) {
    return 'H4';
  }
  // Otherwise: use D
  return 'D';
}
