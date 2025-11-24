/**
 * OANDA API Types
 *
 * Type definitions for OANDA API data structures and enums.
 */

/**
 * OANDA Granularity (Timeframe) Options
 *
 * Represents the time interval for each candlestick.
 */
export type OandaGranularity =
  | 'M1' // 1 minute
  | 'M5' // 5 minutes
  | 'M15' // 15 minutes
  | 'M30' // 30 minutes
  | 'H1' // 1 hour
  | 'H4' // 4 hours
  | 'D' // 1 day
  | 'W' // 1 week
  | 'M'; // 1 month
