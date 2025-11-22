/**
 * Chart Data Transformation Utilities
 *
 * This file contains utilities for transforming API data into chart-compatible formats,
 * including candle data transformation, trade data conversion, granularity calculations,
 * and buffered range calculations.
 */

import type { OandaGranularity } from '../types/oanda';
import { CHART_CONFIG } from '../config/chartConfig';

/**
 * API Candle format (from backend)
 */
export interface APICandle {
  time: number; // Unix timestamp
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/**
 * Chart Candle format (for react-financial-charts)
 */
export interface ChartCandle {
  date: Date;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/**
 * Backend Trade format (from trading/models.py)
 */
export interface BackendTrade {
  opened_at: string;
  closed_at: string;
  instrument: string;
  direction: 'long' | 'short';
  units: number;
  entry_price: number;
  exit_price: number;
  pnl: number;
  duration?: string;
}

/**
 * Frontend Trade format (from types/execution.ts)
 */
export interface FrontendTrade {
  entry_time: string;
  exit_time: string;
  instrument: string;
  direction: 'long' | 'short';
  units: number;
  entry_price: number;
  exit_price: number;
  pnl: number;
  duration?: string;
}

/**
 * Transform API candles to chart format
 * Converts Unix timestamps to JavaScript Date objects
 *
 * @param apiCandles - Array of candles from the API
 * @returns Array of candles in chart format
 */
export function transformCandles(apiCandles: APICandle[]): ChartCandle[] {
  return apiCandles
    .map((candle) => {
      // Validate timestamp
      if (!candle.time || candle.time <= 0) {
        console.error('Invalid candle timestamp:', candle);
        return null;
      }

      return {
        date: new Date(candle.time * 1000), // Convert Unix timestamp to Date
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
        volume: candle.volume,
      };
    })
    .filter((candle): candle is ChartCandle => candle !== null);
}

/**
 * Convert backend trade format to frontend format
 * Maps opened_at/closed_at to entry_time/exit_time
 *
 * @param backendTrade - Trade in backend format
 * @returns Trade in frontend format
 */
export function convertBackendTradeToFrontend(
  backendTrade: BackendTrade
): FrontendTrade {
  return {
    entry_time: backendTrade.opened_at,
    exit_time: backendTrade.closed_at,
    instrument: backendTrade.instrument,
    direction: backendTrade.direction,
    units: backendTrade.units,
    entry_price: backendTrade.entry_price,
    exit_price: backendTrade.exit_price,
    pnl: backendTrade.pnl,
    duration: backendTrade.duration,
  };
}

/**
 * Get the duration of a single candle in milliseconds for a given granularity
 *
 * @param granularity - OANDA granularity string (e.g., 'M1', 'H1', 'D')
 * @returns Duration in milliseconds
 */
export function getGranularityDuration(granularity: string): number {
  const unit = granularity.charAt(0);
  const value = parseInt(granularity.substring(1)) || 1;

  const durations: Record<string, number> = {
    S: 1000, // seconds
    M: 60 * 1000, // minutes
    H: 60 * 60 * 1000, // hours
    D: 24 * 60 * 60 * 1000, // days
    W: 7 * 24 * 60 * 60 * 1000, // weeks
  };

  return (durations[unit] || durations['H']) * value;
}

/**
 * Calculate buffered range for backtest charts
 * Adds buffer candles before start and after end
 *
 * @param startDate - Start date of the backtest
 * @param endDate - End date of the backtest
 * @param granularity - Chart granularity
 * @returns Buffered date range
 */
export function calculateBufferedRange(
  startDate: Date,
  endDate: Date,
  granularity: OandaGranularity
): { from: Date; to: Date } {
  const candleDuration = getGranularityDuration(granularity);
  const bufferSize = CHART_CONFIG.BACKTEST_BUFFER_CANDLES;

  return {
    from: new Date(startDate.getTime() - candleDuration * bufferSize),
    to: new Date(endDate.getTime() + candleDuration * bufferSize),
  };
}
