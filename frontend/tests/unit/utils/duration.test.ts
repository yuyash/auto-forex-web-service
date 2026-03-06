/**
 * Unit tests for duration utility functions.
 */

import { describe, it, expect } from 'vitest';
import {
  durationMsBetween,
  formatDurationMs,
} from '../../../src/utils/duration';

describe('durationMsBetween', () => {
  it('returns positive duration for valid range', () => {
    expect(
      durationMsBetween('2024-01-01T00:00:00Z', '2024-01-01T01:00:00Z')
    ).toBe(3_600_000);
  });

  it('returns null when start is null', () => {
    expect(durationMsBetween(null, '2024-01-01T00:00:00Z')).toBeNull();
  });

  it('returns null when end is null', () => {
    expect(durationMsBetween('2024-01-01T00:00:00Z', null)).toBeNull();
  });

  it('returns null when end is before start', () => {
    expect(
      durationMsBetween('2024-01-02T00:00:00Z', '2024-01-01T00:00:00Z')
    ).toBeNull();
  });

  it('returns 0 for identical timestamps', () => {
    expect(
      durationMsBetween('2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z')
    ).toBe(0);
  });

  it('returns null for invalid date strings', () => {
    expect(durationMsBetween('not-a-date', '2024-01-01T00:00:00Z')).toBeNull();
  });
});

describe('formatDurationMs', () => {
  it('formats seconds only', () => {
    expect(formatDurationMs(45_000)).toBe('45s');
  });

  it('formats minutes and seconds', () => {
    expect(formatDurationMs(125_000)).toBe('2m 5s');
  });

  it('formats hours and minutes', () => {
    expect(formatDurationMs(3_725_000)).toBe('1h 2m');
  });

  it('formats days and hours', () => {
    expect(formatDurationMs(90_000_000)).toBe('1d 1h');
  });

  it('formats zero', () => {
    expect(formatDurationMs(0)).toBe('0s');
  });
});
