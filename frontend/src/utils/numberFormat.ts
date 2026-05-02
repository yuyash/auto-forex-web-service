import { readAppSettings } from '../hooks/useAppSettings';
import type { AppSettings } from '../hooks/useAppSettings';

export interface FormatAppNumberOptions {
  minimumFractionDigits?: number;
  maximumFractionDigits?: number;
  useGrouping?: boolean;
  signed?: boolean;
}

export type NumberFormatSeparators = Pick<
  AppSettings,
  'decimalSeparator' | 'thousandsSeparator'
>;

function applySeparators(
  value: string,
  separators: NumberFormatSeparators = readAppSettings()
): string {
  const { decimalSeparator, thousandsSeparator } = separators;
  const [integerPart, fractionPart] = value.split('.');
  const normalizedInteger = integerPart.replace(/,/g, thousandsSeparator);

  if (fractionPart == null) {
    return normalizedInteger;
  }

  return `${normalizedInteger}${decimalSeparator}${fractionPart}`;
}

export function formatAppNumber(
  value: number,
  options: FormatAppNumberOptions = {},
  separators?: NumberFormatSeparators
): string {
  if (!Number.isFinite(value)) return '-';

  const {
    minimumFractionDigits = 0,
    maximumFractionDigits = 2,
    useGrouping = true,
    signed = false,
  } = options;

  const absoluteValue = Math.abs(value);
  const formatted = new Intl.NumberFormat('en-US', {
    minimumFractionDigits,
    maximumFractionDigits,
    useGrouping,
  }).format(absoluteValue);

  const sign = signed ? (value >= 0 ? '+' : '-') : value < 0 ? '-' : '';
  return `${sign}${applySeparators(formatted, separators)}`;
}

export function formatAppPercent(
  value: number,
  fractionDigits = 2,
  signed = false,
  separators?: NumberFormatSeparators
): string {
  return `${formatAppNumber(
    value,
    {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
      signed,
    },
    separators
  )}%`;
}

/**
 * Map ISO 4217 currency codes to their display symbols.
 * Falls through to the original code for unmapped currencies.
 */
const CURRENCY_SYMBOLS: Record<string, string> = {
  JPY: '¥',
  USD: '$',
  EUR: '€',
  GBP: '£',
  AUD: 'A$',
  CAD: 'C$',
  CHF: 'CHF',
  NZD: 'NZ$',
};

/**
 * Return the display symbol for a currency code (e.g. "JPY" → "¥").
 * Returns the original code when no symbol mapping exists.
 */
export function currencySymbol(code: string | null | undefined): string {
  if (!code) return '';
  const upper = code.trim().toUpperCase();
  return CURRENCY_SYMBOLS[upper] ?? upper;
}
