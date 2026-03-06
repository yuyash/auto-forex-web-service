/**
 * Unit tests for formatting utility functions.
 * Pure logic — no React, no DOM.
 */

import { describe, it, expect } from 'vitest';
import {
  formatCurrency,
  formatPercentage,
  formatNumber,
  formatDateTime,
  formatDate,
  formatTime,
} from '../../../src/utils/formatters';

describe('formatCurrency', () => {
  it('formats positive USD values', () => {
    expect(formatCurrency(1234.56)).toBe('$1,234.56');
  });

  it('formats zero', () => {
    expect(formatCurrency(0)).toBe('$0.00');
  });

  it('formats negative values', () => {
    expect(formatCurrency(-99.9)).toBe('-$99.90');
  });

  it('respects currency parameter', () => {
    const result = formatCurrency(1000, 'EUR');
    expect(result).toContain('1,000.00');
  });
});

describe('formatPercentage', () => {
  it('formats with default decimals', () => {
    expect(formatPercentage(12.345)).toBe('12.35%');
  });

  it('formats with custom decimals', () => {
    expect(formatPercentage(12.345, 1)).toBe('12.3%');
  });

  it('formats zero', () => {
    expect(formatPercentage(0)).toBe('0.00%');
  });

  it('formats negative values', () => {
    expect(formatPercentage(-5.5)).toBe('-5.50%');
  });
});

describe('formatNumber', () => {
  it('formats billions', () => {
    expect(formatNumber(1_500_000_000)).toBe('1.50B');
  });

  it('formats millions', () => {
    expect(formatNumber(2_500_000)).toBe('2.50M');
  });

  it('formats thousands', () => {
    expect(formatNumber(12_345)).toBe('12.35K');
  });

  it('formats small numbers without abbreviation', () => {
    expect(formatNumber(999)).toBe('999.00');
  });
});

describe('formatDateTime / formatDate / formatTime', () => {
  const iso = '2024-06-15T14:30:00Z';

  it('formatDateTime returns a non-empty string', () => {
    expect(formatDateTime(iso).length).toBeGreaterThan(0);
  });

  it('formatDate returns a non-empty string', () => {
    expect(formatDate(iso).length).toBeGreaterThan(0);
  });

  it('formatTime returns a non-empty string', () => {
    expect(formatTime(iso).length).toBeGreaterThan(0);
  });
});
