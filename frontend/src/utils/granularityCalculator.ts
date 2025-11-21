/**
 * Granularity Calculator Utility
 *
 * Calculates optimal OHLC chart granularity based on date range.
 * Targets 50-500 data points for optimal visualization.
 */

import type { OandaGranularity } from '../types/oanda';

// Re-export for convenience
export type { OandaGranularity };

interface GranularityConfig {
  granularity: OandaGranularity;
  minutesPerCandle: number;
}

// Available OANDA granularities with their duration in minutes
const GRANULARITIES: GranularityConfig[] = [
  { granularity: 'M1', minutesPerCandle: 1 },
  { granularity: 'M5', minutesPerCandle: 5 },
  { granularity: 'M15', minutesPerCandle: 15 },
  { granularity: 'M30', minutesPerCandle: 30 },
  { granularity: 'H1', minutesPerCandle: 60 },
  { granularity: 'H4', minutesPerCandle: 240 },
  { granularity: 'D', minutesPerCandle: 1440 },
  { granularity: 'W', minutesPerCandle: 10080 },
];

const MIN_DATA_POINTS = 50;
const MAX_DATA_POINTS = 500;
const TARGET_DATA_POINTS = 200;

/**
 * Calculate optimal granularity for a given date range
 *
 * @param startDate - Start date of the range
 * @param endDate - End date of the range
 * @param targetDataPoints - Desired number of data points (default: 200)
 * @returns Optimal OANDA granularity string
 */
export function calculateGranularity(
  startDate: Date,
  endDate: Date,
  targetDataPoints: number = TARGET_DATA_POINTS
): OandaGranularity {
  // Validate inputs
  if (startDate >= endDate) {
    throw new Error('Start date must be before end date');
  }

  if (
    targetDataPoints < MIN_DATA_POINTS ||
    targetDataPoints > MAX_DATA_POINTS
  ) {
    throw new Error(
      `Target data points must be between ${MIN_DATA_POINTS} and ${MAX_DATA_POINTS}`
    );
  }

  // Calculate duration in minutes
  const durationMs = endDate.getTime() - startDate.getTime();
  const durationMinutes = durationMs / (1000 * 60);

  // Handle edge case: very short periods (less than target data points in minutes)
  if (durationMinutes < targetDataPoints) {
    return 'M1';
  }

  // Find the granularity that gets closest to our target data points
  // Prioritize getting close to target count over matching ideal minutes per candle
  let bestGranularity = GRANULARITIES[0];
  let bestDataPointsDiff = Infinity;

  for (const config of GRANULARITIES) {
    const dataPoints = durationMinutes / config.minutesPerCandle;

    // Skip if this would give us too few or too many data points
    if (dataPoints < MIN_DATA_POINTS || dataPoints > MAX_DATA_POINTS) {
      continue;
    }

    // Calculate how close this is to our target data points
    const dataPointsDiff = Math.abs(dataPoints - targetDataPoints);

    if (dataPointsDiff < bestDataPointsDiff) {
      bestDataPointsDiff = dataPointsDiff;
      bestGranularity = config;
    }
  }

  // If no granularity fits within range, choose the one closest to target
  if (bestDataPointsDiff === Infinity) {
    // Find granularity that gives closest to target data points (ignoring min/max)
    let closestToTarget = GRANULARITIES[0];
    let closestDiff = Math.abs(
      durationMinutes / GRANULARITIES[0].minutesPerCandle - targetDataPoints
    );

    for (const config of GRANULARITIES) {
      const dataPoints = durationMinutes / config.minutesPerCandle;
      const diff = Math.abs(dataPoints - targetDataPoints);

      if (diff < closestDiff) {
        closestDiff = diff;
        closestToTarget = config;
      }
    }

    return closestToTarget.granularity;
  }

  return bestGranularity.granularity;
}

/**
 * Calculate the number of data points for a given date range and granularity
 *
 * @param startDate - Start date of the range
 * @param endDate - End date of the range
 * @param granularity - OANDA granularity
 * @returns Estimated number of data points
 */
export function calculateDataPoints(
  startDate: Date,
  endDate: Date,
  granularity: OandaGranularity
): number {
  const durationMs = endDate.getTime() - startDate.getTime();
  const durationMinutes = durationMs / (1000 * 60);

  const config = GRANULARITIES.find((g) => g.granularity === granularity);
  if (!config) {
    throw new Error(`Invalid granularity: ${granularity}`);
  }

  return Math.floor(durationMinutes / config.minutesPerCandle);
}

/**
 * Get all available OANDA granularities
 *
 * @returns Array of available granularity strings
 */
export function getAvailableGranularities(): OandaGranularity[] {
  return GRANULARITIES.map((g) => g.granularity);
}
