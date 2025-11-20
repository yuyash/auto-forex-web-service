import { describe, it, expect } from 'vitest';
import {
  calculateGranularity,
  calculateDataPoints,
  getAvailableGranularities,
  type OandaGranularity,
} from './granularityCalculator';

describe('granularityCalculator', () => {
  describe('calculateGranularity', () => {
    it('should return M1 for very short periods (less than 1 hour)', () => {
      const start = new Date('2025-01-01T10:00:00Z');
      const end = new Date('2025-01-01T10:30:00Z'); // 30 minutes

      const result = calculateGranularity(start, end);

      expect(result).toBe('M1');
    });

    it('should return appropriate granularity for short periods (1-3 hours)', () => {
      const start = new Date('2025-01-01T10:00:00Z');
      const end = new Date('2025-01-01T12:00:00Z'); // 2 hours

      const result = calculateGranularity(start, end);
      const dataPoints = calculateDataPoints(start, end, result);

      expect(['M1', 'M5']).toContain(result);
      expect(dataPoints).toBeGreaterThanOrEqual(50);
      expect(dataPoints).toBeLessThanOrEqual(500);
    });

    it('should return appropriate granularity for periods of several hours', () => {
      const start = new Date('2025-01-01T10:00:00Z');
      const end = new Date('2025-01-01T18:00:00Z'); // 8 hours

      const result = calculateGranularity(start, end);
      const dataPoints = calculateDataPoints(start, end, result);

      expect(['M5', 'M15']).toContain(result);
      expect(dataPoints).toBeGreaterThanOrEqual(50);
      expect(dataPoints).toBeLessThanOrEqual(500);
    });

    it('should return appropriate granularity for periods of 1-2 days', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-01-02T12:00:00Z'); // 1.5 days

      const result = calculateGranularity(start, end);
      const dataPoints = calculateDataPoints(start, end, result);

      expect(['M15', 'M30', 'H1']).toContain(result);
      expect(dataPoints).toBeGreaterThanOrEqual(50);
      expect(dataPoints).toBeLessThanOrEqual(500);
    });

    it('should return appropriate granularity for periods of several days', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-01-07T00:00:00Z'); // 7 days

      const result = calculateGranularity(start, end);
      const dataPoints = calculateDataPoints(start, end, result);

      expect(['M30', 'H1', 'H4']).toContain(result);
      expect(dataPoints).toBeGreaterThanOrEqual(50);
      expect(dataPoints).toBeLessThanOrEqual(500);
    });

    it('should return appropriate granularity for periods of several weeks', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-01-31T00:00:00Z'); // 30 days

      const result = calculateGranularity(start, end);
      const dataPoints = calculateDataPoints(start, end, result);

      expect(['H4', 'D']).toContain(result);
      expect(dataPoints).toBeGreaterThanOrEqual(50);
      expect(dataPoints).toBeLessThanOrEqual(500);
    });

    it('should return appropriate granularity for very long periods (months)', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-06-01T00:00:00Z'); // 5 months

      const result = calculateGranularity(start, end);
      const dataPoints = calculateDataPoints(start, end, result);

      expect(['D', 'W']).toContain(result);
      expect(dataPoints).toBeGreaterThanOrEqual(50);
      expect(dataPoints).toBeLessThanOrEqual(500);
    });

    it('should throw error if start date is after end date', () => {
      const start = new Date('2025-01-02T00:00:00Z');
      const end = new Date('2025-01-01T00:00:00Z');

      expect(() => calculateGranularity(start, end)).toThrow(
        'Start date must be before end date'
      );
    });

    it('should throw error if start date equals end date', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-01-01T00:00:00Z');

      expect(() => calculateGranularity(start, end)).toThrow(
        'Start date must be before end date'
      );
    });

    it('should throw error if target data points is too low', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-01-02T00:00:00Z');

      expect(() => calculateGranularity(start, end, 10)).toThrow(
        'Target data points must be between 50 and 500'
      );
    });

    it('should throw error if target data points is too high', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-01-02T00:00:00Z');

      expect(() => calculateGranularity(start, end, 1000)).toThrow(
        'Target data points must be between 50 and 500'
      );
    });

    it('should respect custom target data points', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-01-02T00:00:00Z'); // 1 day = 1440 minutes

      // With 100 target points, should prefer M15 (96 points) over M30 (48 points)
      const result = calculateGranularity(start, end, 100);

      expect(result).toBe('M15');
    });
  });

  describe('calculateDataPoints', () => {
    it('should calculate correct data points for M1 granularity', () => {
      const start = new Date('2025-01-01T10:00:00Z');
      const end = new Date('2025-01-01T11:00:00Z'); // 60 minutes

      const result = calculateDataPoints(start, end, 'M1');

      expect(result).toBe(60);
    });

    it('should calculate correct data points for M5 granularity', () => {
      const start = new Date('2025-01-01T10:00:00Z');
      const end = new Date('2025-01-01T11:00:00Z'); // 60 minutes

      const result = calculateDataPoints(start, end, 'M5');

      expect(result).toBe(12);
    });

    it('should calculate correct data points for H1 granularity', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-01-02T00:00:00Z'); // 24 hours

      const result = calculateDataPoints(start, end, 'H1');

      expect(result).toBe(24);
    });

    it('should calculate correct data points for D granularity', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-01-31T00:00:00Z'); // 30 days

      const result = calculateDataPoints(start, end, 'D');

      expect(result).toBe(30);
    });

    it('should calculate correct data points for W granularity', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-03-05T00:00:00Z'); // ~9 weeks

      const result = calculateDataPoints(start, end, 'W');

      expect(result).toBe(9);
    });

    it('should throw error for invalid granularity', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-01-02T00:00:00Z');

      expect(() =>
        calculateDataPoints(start, end, 'INVALID' as OandaGranularity)
      ).toThrow('Invalid granularity: INVALID');
    });
  });

  describe('getAvailableGranularities', () => {
    it('should return all available OANDA granularities', () => {
      const result = getAvailableGranularities();

      expect(result).toEqual(['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D', 'W']);
    });

    it('should return array with 8 granularities', () => {
      const result = getAvailableGranularities();

      expect(result).toHaveLength(8);
    });
  });

  describe('data point count validation', () => {
    it('should produce between 50-500 data points for 1 hour period', () => {
      const start = new Date('2025-01-01T10:00:00Z');
      const end = new Date('2025-01-01T11:00:00Z');

      const granularity = calculateGranularity(start, end);
      const dataPoints = calculateDataPoints(start, end, granularity);

      expect(dataPoints).toBeGreaterThanOrEqual(50);
      expect(dataPoints).toBeLessThanOrEqual(500);
    });

    it('should produce between 50-500 data points for 1 day period', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-01-02T00:00:00Z');

      const granularity = calculateGranularity(start, end);
      const dataPoints = calculateDataPoints(start, end, granularity);

      expect(dataPoints).toBeGreaterThanOrEqual(50);
      expect(dataPoints).toBeLessThanOrEqual(500);
    });

    it('should produce between 50-500 data points for 1 week period', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-01-08T00:00:00Z');

      const granularity = calculateGranularity(start, end);
      const dataPoints = calculateDataPoints(start, end, granularity);

      expect(dataPoints).toBeGreaterThanOrEqual(50);
      expect(dataPoints).toBeLessThanOrEqual(500);
    });

    it('should produce between 50-500 data points for 1 month period', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-02-01T00:00:00Z');

      const granularity = calculateGranularity(start, end);
      const dataPoints = calculateDataPoints(start, end, granularity);

      expect(dataPoints).toBeGreaterThanOrEqual(50);
      expect(dataPoints).toBeLessThanOrEqual(500);
    });

    it('should produce between 50-500 data points for 3 month period', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-04-01T00:00:00Z');

      const granularity = calculateGranularity(start, end);
      const dataPoints = calculateDataPoints(start, end, granularity);

      expect(dataPoints).toBeGreaterThanOrEqual(50);
      expect(dataPoints).toBeLessThanOrEqual(500);
    });

    it('should produce between 50-500 data points for 6 month period', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-07-01T00:00:00Z');

      const granularity = calculateGranularity(start, end);
      const dataPoints = calculateDataPoints(start, end, granularity);

      expect(dataPoints).toBeGreaterThanOrEqual(50);
      expect(dataPoints).toBeLessThanOrEqual(500);
    });

    it('should produce between 50-500 data points for 1 year period', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2026-01-01T00:00:00Z');

      const granularity = calculateGranularity(start, end);
      const dataPoints = calculateDataPoints(start, end, granularity);

      expect(dataPoints).toBeGreaterThanOrEqual(50);
      expect(dataPoints).toBeLessThanOrEqual(500);
    });
  });

  describe('edge cases', () => {
    it('should handle very short period (5 minutes)', () => {
      const start = new Date('2025-01-01T10:00:00Z');
      const end = new Date('2025-01-01T10:05:00Z');

      const granularity = calculateGranularity(start, end);

      expect(granularity).toBe('M1');
    });

    it('should handle very long period (2 years)', () => {
      const start = new Date('2023-01-01T00:00:00Z');
      const end = new Date('2025-01-01T00:00:00Z');

      const granularity = calculateGranularity(start, end);

      expect(granularity).toBe('W');
    });

    it('should handle period with fractional hours', () => {
      const start = new Date('2025-01-01T10:15:00Z');
      const end = new Date('2025-01-01T14:45:00Z'); // 4.5 hours

      const granularity = calculateGranularity(start, end);
      const dataPoints = calculateDataPoints(start, end, granularity);

      expect(['M1', 'M5', 'M15']).toContain(granularity);
      expect(dataPoints).toBeGreaterThanOrEqual(50);
      expect(dataPoints).toBeLessThanOrEqual(500);
    });

    it('should handle dates with milliseconds', () => {
      const start = new Date('2025-01-01T10:00:00.123Z');
      const end = new Date('2025-01-01T11:00:00.456Z');

      const granularity = calculateGranularity(start, end);

      expect(granularity).toBe('M1');
    });
  });

  describe('granularity selection logic', () => {
    it('should select valid OANDA granularity', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-01-15T00:00:00Z');

      const granularity = calculateGranularity(start, end);
      const validGranularities = getAvailableGranularities();

      expect(validGranularities).toContain(granularity);
    });

    it('should prefer granularity closest to target data points', () => {
      const start = new Date('2025-01-01T00:00:00Z');
      const end = new Date('2025-01-02T00:00:00Z'); // 1440 minutes

      const granularity = calculateGranularity(start, end, 200);
      const dataPoints = calculateDataPoints(start, end, granularity);

      // Should produce data points within acceptable range
      expect(dataPoints).toBeGreaterThanOrEqual(50);
      expect(dataPoints).toBeLessThanOrEqual(500);
      // Should be a valid granularity
      expect(getAvailableGranularities()).toContain(granularity);
    });
  });
});
