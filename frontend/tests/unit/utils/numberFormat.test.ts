import { afterEach, describe, expect, it } from 'vitest';
import {
  APP_SETTINGS_STORAGE_KEY,
  DEFAULT_APP_SETTINGS,
} from '../../../src/hooks/useAppSettings';
import {
  formatAppNumber,
  formatAppPercent,
} from '../../../src/utils/numberFormat';

describe('number formatting', () => {
  afterEach(() => {
    localStorage.clear();
  });

  it('uses configured decimal and thousands separators', () => {
    localStorage.setItem(
      APP_SETTINGS_STORAGE_KEY,
      JSON.stringify({
        ...DEFAULT_APP_SETTINGS,
        decimalSeparator: ',',
        thousandsSeparator: ' ',
      })
    );

    expect(
      formatAppNumber(1234567.89, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })
    ).toBe('1 234 567,89');
  });

  it('formats signed percentages with the configured decimal separator', () => {
    localStorage.setItem(
      APP_SETTINGS_STORAGE_KEY,
      JSON.stringify({
        ...DEFAULT_APP_SETTINGS,
        decimalSeparator: ',',
        thousandsSeparator: '.',
      })
    );

    expect(formatAppPercent(12.345, 2, true)).toBe('+12,35%');
    expect(formatAppPercent(-12.345, 2, true)).toBe('-12,35%');
  });
});
