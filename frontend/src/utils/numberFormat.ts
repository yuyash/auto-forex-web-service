import { readAppSettings } from '../hooks/useAppSettings';
import type { AppSettings } from '../hooks/useAppSettings';
import type { MoneyAmountLike } from '../types/money';

export interface FormatAppNumberOptions {
  minimumFractionDigits?: number;
  maximumFractionDigits?: number;
  useGrouping?: boolean;
  signed?: boolean;
}

export interface FormatMoneyAmountOptions extends FormatAppNumberOptions {
  currencyPlacement?: 'prefix' | 'suffix';
  useCurrencySymbol?: boolean;
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
  SGD: 'S$',
  HKD: 'HK$',
  NOK: 'kr',
  SEK: 'kr',
  DKK: 'kr',
  PLN: 'zł',
  CZK: 'Kč',
  HUF: 'Ft',
  MXN: 'MX$',
  ZAR: 'R',
};

const ZERO_DECIMAL_CURRENCIES = new Set(['JPY', 'HUF']);

export function normalizeCurrencyCode(
  code: string | null | undefined,
  fallback = ''
): string {
  const upper = String(code ?? '')
    .trim()
    .toUpperCase();
  if (upper.length === 3 && /^[A-Z]{3}$/.test(upper)) {
    return upper;
  }
  return fallback;
}

/**
 * Return the display symbol for a currency code (e.g. "JPY" → "¥").
 * Returns the original code when no symbol mapping exists.
 */
export function currencySymbol(code: string | null | undefined): string {
  const upper = normalizeCurrencyCode(code);
  if (!upper) return '';
  return CURRENCY_SYMBOLS[upper] ?? upper;
}

export function currencyFractionDigits(
  code: string | null | undefined,
  fallback = 2
): number {
  const upper = normalizeCurrencyCode(code);
  if (!upper) return fallback;
  return ZERO_DECIMAL_CURRENCIES.has(upper) ? 0 : fallback;
}

export function formatMoneyAmount(
  value: number,
  currencyCode: string | null | undefined,
  options: FormatMoneyAmountOptions = {},
  separators?: NumberFormatSeparators
): string {
  if (!Number.isFinite(value)) return '-';
  const {
    currencyPlacement = 'prefix',
    useCurrencySymbol = true,
    signed = false,
    minimumFractionDigits = currencyFractionDigits(currencyCode),
    maximumFractionDigits = currencyFractionDigits(currencyCode),
    ...numberOptions
  } = options;
  const code = normalizeCurrencyCode(currencyCode);
  const currency = useCurrencySymbol ? currencySymbol(code) : code;
  const sign = signed ? (value >= 0 ? '+' : '-') : value < 0 ? '-' : '';
  const absoluteValue = signed || value < 0 ? Math.abs(value) : value;
  const numericText = formatAppNumber(
    absoluteValue,
    {
      ...numberOptions,
      minimumFractionDigits,
      maximumFractionDigits,
      signed: false,
    },
    separators
  );
  if (!currency) return `${sign}${numericText}`;
  return currencyPlacement === 'suffix'
    ? `${sign}${numericText} ${currency}`
    : `${sign}${currency} ${numericText}`;
}

export function formatMoneyPayload(
  money: MoneyAmountLike | null | undefined,
  options: FormatMoneyAmountOptions = {},
  separators?: NumberFormatSeparators
): string {
  if (!money) return '-';
  const amount = Number(money.amount);
  if (!Number.isFinite(amount)) return '-';
  return formatMoneyAmount(amount, money.currency, options, separators);
}
