/**
 * Unit tests for chart timezone formatting utilities.
 */

import { describe, it, expect } from 'vitest';
import {
  formatChartTime,
  configureTimeAxis,
  formatAxisDate,
  formatTooltipDate,
} from '../../../src/utils/chartTimezone';

const TEST_DATE = new Date('2024-06-15T14:30:00Z');

describe('formatChartTime', () => {
  it('formats in UTC with suffix', () => {
    const result = formatChartTime(TEST_DATE, 'UTC');
    expect(result).toContain('2024-06-15');
    expect(result).toContain('14:30:00');
    expect(result).toContain('UTC');
  });

  it('formats in a specific timezone', () => {
    const result = formatChartTime(TEST_DATE, 'America/New_York');
    // EDT is UTC-4, so 14:30 UTC = 10:30 EDT
    expect(result).toContain('10:30:00');
    expect(result).not.toContain('UTC');
  });

  it('handles empty timezone as UTC', () => {
    const result = formatChartTime(TEST_DATE, '');
    expect(result).toContain('UTC');
  });
});

describe('configureTimeAxis', () => {
  it('returns tickFormat and tooltipFormat functions', () => {
    const axis = configureTimeAxis('UTC');
    expect(typeof axis.tickFormat).toBe('function');
    expect(typeof axis.tooltipFormat).toBe('function');
  });

  it('tickFormat returns abbreviated format', () => {
    const axis = configureTimeAxis('UTC');
    const result = axis.tickFormat(TEST_DATE);
    expect(result).toContain('Jun');
    expect(result).toContain('14:30');
  });

  it('tooltipFormat returns full format with timezone', () => {
    const axis = configureTimeAxis('America/New_York');
    const result = axis.tooltipFormat(TEST_DATE);
    expect(result).toContain('2024-06-15');
    expect(result).toContain('10:30:00');
  });
});

describe('formatAxisDate', () => {
  it('formats date in UTC by default', () => {
    expect(formatAxisDate(TEST_DATE)).toBe('2024-06-15');
  });

  it('formats date in specific timezone', () => {
    // At UTC midnight, it's still previous day in NYC
    const midnight = new Date('2024-06-15T03:00:00Z');
    const result = formatAxisDate(midnight, 'America/New_York');
    expect(result).toBe('2024-06-14');
  });
});

describe('formatTooltipDate', () => {
  it('formats with UTC suffix for UTC timezone', () => {
    const result = formatTooltipDate(TEST_DATE, 'UTC');
    expect(result).toContain('UTC');
  });

  it('formats with timezone abbreviation for non-UTC', () => {
    const result = formatTooltipDate(TEST_DATE, 'America/New_York');
    // Should contain EDT or EST
    expect(result).toMatch(/E[DS]T/);
  });
});
