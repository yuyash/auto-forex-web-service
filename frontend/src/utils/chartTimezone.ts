/**
 * Chart Timezone Formatting Utilities
 *
 * This file contains utilities for formatting chart times in different timezones
 * and configuring timezone-aware axis formatting.
 */

import { formatInTimeZone } from 'date-fns-tz';

/**
 * Format a date for chart display in the specified timezone
 *
 * @param date - Date to format
 * @param timezone - IANA timezone string (e.g., 'America/New_York', 'UTC')
 * @returns Formatted date string
 */
export function formatChartTime(date: Date, timezone: string): string {
  // If timezone is provided and not UTC, format in that timezone
  if (timezone && timezone !== 'UTC') {
    return formatInTimeZone(date, timezone, 'yyyy-MM-dd HH:mm:ss');
  }
  // Otherwise use UTC
  return formatInTimeZone(date, 'UTC', 'yyyy-MM-dd HH:mm:ss') + ' UTC';
}

/**
 * Configure time axis formatting for the specified timezone
 * Returns formatting functions for axis ticks and tooltips
 *
 * @param timezone - IANA timezone string (e.g., 'America/New_York', 'UTC')
 * @returns Object with tickFormat and tooltipFormat functions
 */
export function configureTimeAxis(timezone: string) {
  return {
    /**
     * Format function for axis tick labels
     * Shows abbreviated date and time
     */
    tickFormat: (date: Date) => {
      if (timezone && timezone !== 'UTC') {
        return formatInTimeZone(date, timezone, 'MMM dd HH:mm');
      }
      return formatInTimeZone(date, 'UTC', 'MMM dd HH:mm');
    },

    /**
     * Format function for tooltip display
     * Shows full date, time, and timezone abbreviation
     */
    tooltipFormat: (date: Date) => {
      if (timezone && timezone !== 'UTC') {
        return formatInTimeZone(date, timezone, 'yyyy-MM-dd HH:mm:ss zzz');
      }
      return formatInTimeZone(date, 'UTC', 'yyyy-MM-dd HH:mm:ss') + ' UTC';
    },
  };
}

/**
 * Format a date for axis display (short format)
 *
 * @param date - Date to format
 * @param timezone - IANA timezone string
 * @returns Formatted date string for axis
 */
export function formatAxisDate(date: Date, timezone: string = 'UTC'): string {
  if (timezone && timezone !== 'UTC') {
    return formatInTimeZone(date, timezone, 'yyyy-MM-dd');
  }
  return formatInTimeZone(date, 'UTC', 'yyyy-MM-dd');
}

/**
 * Format a date for tooltip display (long format)
 *
 * @param date - Date to format
 * @param timezone - IANA timezone string
 * @returns Formatted date string for tooltip
 */
export function formatTooltipDate(
  date: Date,
  timezone: string = 'UTC'
): string {
  if (timezone && timezone !== 'UTC') {
    return formatInTimeZone(date, timezone, 'yyyy-MM-dd HH:mm:ss zzz');
  }
  return formatInTimeZone(date, 'UTC', 'yyyy-MM-dd HH:mm:ss') + ' UTC';
}
