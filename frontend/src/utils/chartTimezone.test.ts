/**
 * Unit tests for chart timezone formatting utilities
 */

import { describe, it, expect } from 'vitest';
import {
  formatChartTime,
  configureTimeAxis,
  formatAxisDate,
  formatTooltipDate,
} from './chartTimezone';

describe('formatChartTime', () => {
  it('should format date in UTC when timezone is UTC', () => {
    const date = new Date('2024-01-01T10:30:45Z');
    const result = formatChartTime(date, 'UTC');

    expect(result).toBe('2024-01-01 10:30:45 UTC');
  });

  it('should format date in specified timezone', () => {
    const date = new Date('2024-01-01T10:30:45Z');
    const result = formatChartTime(date, 'America/New_York');

    // UTC 10:30 = EST 05:30 (UTC-5)
    expect(result).toBe('2024-01-01 05:30:45');
  });

  it('should format date in different timezone', () => {
    const date = new Date('2024-01-01T10:30:45Z');
    const result = formatChartTime(date, 'Asia/Tokyo');

    // UTC 10:30 = JST 19:30 (UTC+9)
    expect(result).toBe('2024-01-01 19:30:45');
  });

  it('should default to UTC when timezone is empty string', () => {
    const date = new Date('2024-01-01T10:30:45Z');
    const result = formatChartTime(date, '');

    expect(result).toBe('2024-01-01 10:30:45 UTC');
  });
});

describe('configureTimeAxis', () => {
  it('should return configuration object with format functions', () => {
    const config = configureTimeAxis('UTC');

    expect(config).toHaveProperty('tickFormat');
    expect(config).toHaveProperty('tooltipFormat');
    expect(typeof config.tickFormat).toBe('function');
    expect(typeof config.tooltipFormat).toBe('function');
  });

  it('should format tick labels in UTC', () => {
    const config = configureTimeAxis('UTC');
    const date = new Date('2024-01-15T10:30:00Z');
    const result = config.tickFormat(date);

    expect(result).toBe('Jan 15 10:30');
  });

  it('should format tick labels in specified timezone', () => {
    const config = configureTimeAxis('America/New_York');
    const date = new Date('2024-01-15T10:30:00Z');
    const result = config.tickFormat(date);

    // UTC 10:30 = EST 05:30
    expect(result).toBe('Jan 15 05:30');
  });

  it('should format tooltip in UTC with timezone abbreviation', () => {
    const config = configureTimeAxis('UTC');
    const date = new Date('2024-01-15T10:30:45Z');
    const result = config.tooltipFormat(date);

    expect(result).toBe('2024-01-15 10:30:45 UTC');
  });

  it('should format tooltip in specified timezone with abbreviation', () => {
    const config = configureTimeAxis('America/New_York');
    const date = new Date('2024-01-15T10:30:45Z');
    const result = config.tooltipFormat(date);

    // Should include timezone abbreviation (EST or EDT depending on date)
    expect(result).toContain('2024-01-15 05:30:45');
    expect(result).toMatch(/EST|EDT/);
  });
});

describe('formatAxisDate', () => {
  it('should format date for axis in UTC by default', () => {
    const date = new Date('2024-01-15T10:30:00Z');
    const result = formatAxisDate(date);

    expect(result).toBe('2024-01-15');
  });

  it('should format date for axis in specified timezone', () => {
    const date = new Date('2024-01-15T02:30:00Z');
    const result = formatAxisDate(date, 'America/New_York');

    // UTC 02:30 = EST 21:30 previous day
    expect(result).toBe('2024-01-14');
  });

  it('should format date for axis in UTC when explicitly specified', () => {
    const date = new Date('2024-01-15T10:30:00Z');
    const result = formatAxisDate(date, 'UTC');

    expect(result).toBe('2024-01-15');
  });
});

describe('formatTooltipDate', () => {
  it('should format date for tooltip in UTC by default', () => {
    const date = new Date('2024-01-15T10:30:45Z');
    const result = formatTooltipDate(date);

    expect(result).toBe('2024-01-15 10:30:45 UTC');
  });

  it('should format date for tooltip in specified timezone', () => {
    const date = new Date('2024-01-15T10:30:45Z');
    const result = formatTooltipDate(date, 'America/New_York');

    // Should include timezone abbreviation
    expect(result).toContain('2024-01-15 05:30:45');
    expect(result).toMatch(/EST|EDT/);
  });

  it('should format date for tooltip in UTC when explicitly specified', () => {
    const date = new Date('2024-01-15T10:30:45Z');
    const result = formatTooltipDate(date, 'UTC');

    expect(result).toBe('2024-01-15 10:30:45 UTC');
  });

  it('should handle different timezones correctly', () => {
    const date = new Date('2024-01-15T10:30:45Z');
    const resultTokyo = formatTooltipDate(date, 'Asia/Tokyo');
    const resultLondon = formatTooltipDate(date, 'Europe/London');

    // UTC 10:30 = JST 19:30 (UTC+9)
    expect(resultTokyo).toContain('2024-01-15 19:30:45');
    // Timezone abbreviation can be JST or GMT+9 depending on date-fns-tz version
    expect(resultTokyo).toMatch(/JST|GMT\+9/);

    // UTC 10:30 = GMT 10:30 (UTC+0 in winter)
    expect(resultLondon).toContain('2024-01-15 10:30:45');
    expect(resultLondon).toContain('GMT');
  });
});
