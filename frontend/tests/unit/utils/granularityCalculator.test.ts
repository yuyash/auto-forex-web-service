/**
 * Unit tests for granularity calculator.
 */

import { describe, it, expect } from 'vitest';
import {
  calculateGranularity,
  calculateDataPoints,
  getAvailableGranularities,
} from '../../../src/utils/granularityCalculator';

describe('calculateGranularity', () => {
  it('returns M1 for very short periods', () => {
    const start = new Date('2024-01-01T00:00:00Z');
    const end = new Date('2024-01-01T00:30:00Z');
    expect(calculateGranularity(start, end)).toBe('M1');
  });

  it('returns hourly granularity for multi-day range', () => {
    const start = new Date('2024-01-01T00:00:00Z');
    const end = new Date('2024-01-10T00:00:00Z');
    const result = calculateGranularity(start, end);
    expect(['H1', 'H4']).toContain(result);
  });

  it('returns daily or weekly for very long ranges', () => {
    const start = new Date('2023-01-01T00:00:00Z');
    const end = new Date('2024-01-01T00:00:00Z');
    const result = calculateGranularity(start, end);
    expect(['D', 'W']).toContain(result);
  });

  it('throws when start >= end', () => {
    const date = new Date('2024-01-01T00:00:00Z');
    expect(() => calculateGranularity(date, date)).toThrow(
      'Start date must be before end date'
    );
  });

  it('throws for out-of-range target data points', () => {
    const start = new Date('2024-01-01T00:00:00Z');
    const end = new Date('2024-01-02T00:00:00Z');
    expect(() => calculateGranularity(start, end, 10)).toThrow();
  });

  it('accepts custom target data points', () => {
    const start = new Date('2024-01-01T00:00:00Z');
    const end = new Date('2024-01-05T00:00:00Z');
    const result = calculateGranularity(start, end, 100);
    expect(typeof result).toBe('string');
  });
});

describe('calculateDataPoints', () => {
  it('calculates correct data points for 1-hour range with M1', () => {
    const start = new Date('2024-01-01T00:00:00Z');
    const end = new Date('2024-01-01T01:00:00Z');
    expect(calculateDataPoints(start, end, 'M1')).toBe(60);
  });

  it('calculates correct data points for 1-day range with H1', () => {
    const start = new Date('2024-01-01T00:00:00Z');
    const end = new Date('2024-01-02T00:00:00Z');
    expect(calculateDataPoints(start, end, 'H1')).toBe(24);
  });

  it('throws for invalid granularity', () => {
    const start = new Date('2024-01-01T00:00:00Z');
    const end = new Date('2024-01-02T00:00:00Z');
    expect(() => calculateDataPoints(start, end, 'INVALID' as never)).toThrow(
      'Invalid granularity'
    );
  });
});

describe('getAvailableGranularities', () => {
  it('returns all expected granularities', () => {
    const granularities = getAvailableGranularities();
    expect(granularities).toContain('M1');
    expect(granularities).toContain('H1');
    expect(granularities).toContain('D');
    expect(granularities).toContain('W');
    expect(granularities.length).toBe(8);
  });
});
