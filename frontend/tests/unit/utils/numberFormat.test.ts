import { afterEach, describe, expect, it } from 'vitest';
import {
  APP_SETTINGS_STORAGE_KEY,
  DEFAULT_APP_SETTINGS,
} from '../../../src/hooks/useAppSettings';
import {
  currencyFractionDigits,
  formatAppNumber,
  formatMoneyAmount,
  formatMoneyPayload,
  formatAppPercent,
  normalizeCurrencyCode,
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

  it('normalizes currency codes and falls back for invalid values', () => {
    expect(normalizeCurrencyCode(' usd ')).toBe('USD');
    expect(normalizeCurrencyCode('US', 'JPY')).toBe('JPY');
    expect(normalizeCurrencyCode(null, 'EUR')).toBe('EUR');
  });

  it('formats currency-aware money with symbol placement and signs', () => {
    expect(
      formatMoneyAmount(1234.56, 'USD', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })
    ).toBe('$ 1,234.56');
    expect(
      formatMoneyAmount(-1234.56, 'USD', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
        signed: true,
        currencyPlacement: 'suffix',
      })
    ).toBe('-1,234.56 USD');
    expect(
      formatMoneyAmount(1234.56, 'JPY', {
        currencyPlacement: 'suffix',
        language: 'ja',
      })
    ).toBe('1,235 円');
  });

  it('uses zero minor units for JPY-style currencies by default', () => {
    expect(currencyFractionDigits('JPY')).toBe(0);
    expect(formatMoneyAmount(1234.56, 'JPY')).toBe('¥ 1,235');
  });

  it('formats money payloads from API DTOs', () => {
    expect(
      formatMoneyPayload(
        { amount: '12.5', currency: 'EUR' },
        {
          signed: true,
          currencyPlacement: 'suffix',
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }
      )
    ).toBe('+12.50 EUR');
    expect(formatMoneyPayload(null)).toBe('-');
  });
});
