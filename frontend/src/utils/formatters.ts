// Formatting utility functions

import type { AppSettings } from '../hooks/useAppSettings';

/**
 * Read app settings from localStorage (for use outside React components).
 */
function getAppSettings(): Pick<
  AppSettings,
  'dateFormat' | 'decimalSeparator' | 'thousandsSeparator'
> {
  const defaults = {
    dateFormat: 'YYYY-MM-DD' as const,
    decimalSeparator: '.' as const,
    thousandsSeparator: ',' as const,
  };
  try {
    const raw = localStorage.getItem('app_settings');
    if (raw) {
      const parsed = JSON.parse(raw);
      return { ...defaults, ...parsed };
    }
  } catch {
    // ignore
  }
  return defaults;
}

/**
 * Format a number with the user's decimal/thousands separator preferences.
 */
export function formatDecimal(value: number, decimals: number = 2): string {
  const { decimalSeparator, thousandsSeparator } = getAppSettings();
  const fixed = Math.abs(value).toFixed(decimals);
  const [intPart, fracPart] = fixed.split('.');

  // Apply thousands separator
  let formatted = intPart;
  if (thousandsSeparator) {
    formatted = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, thousandsSeparator);
  }

  if (fracPart !== undefined) {
    formatted += decimalSeparator + fracPart;
  }

  return value < 0 ? '-' + formatted : formatted;
}

/**
 * Format a number as currency
 */
export function formatCurrency(
  value: number,
  currency: string = 'USD'
): string {
  const { decimalSeparator, thousandsSeparator } = getAppSettings();

  // Use Intl for the currency symbol, then replace separators
  const intlFormatted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);

  if (decimalSeparator === '.' && thousandsSeparator === ',') {
    return intlFormatted; // en-US default, no transformation needed
  }

  // Extract symbol and numeric part, then reformat
  const match = intlFormatted.match(/^([^0-9-]*)([-]?)([0-9.,]+)(.*)$/);
  if (!match) return intlFormatted;

  const [, prefix, sign, , suffix] = match;
  const numericStr = formatDecimal(Math.abs(value), 2);
  return `${prefix}${sign}${numericStr}${suffix}`;
}

/**
 * Format a number as percentage
 */
export function formatPercentage(value: number, decimals: number = 2): string {
  return `${formatDecimal(value, decimals)}%`;
}

/**
 * Format a large number with abbreviations (K, M, B)
 */
export function formatNumber(value: number): string {
  if (value >= 1_000_000_000) {
    return `${formatDecimal(value / 1_000_000_000, 2)}B`;
  }
  if (value >= 1_000_000) {
    return `${formatDecimal(value / 1_000_000, 2)}M`;
  }
  if (value >= 1_000) {
    return `${formatDecimal(value / 1_000, 2)}K`;
  }
  return formatDecimal(value, 2);
}

/**
 * Format a Date object according to the user's dateFormat preference.
 */
function applyDateFormat(date: Date): string {
  const { dateFormat } = getAppSettings();
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');

  switch (dateFormat) {
    case 'MM/DD/YYYY':
      return `${m}/${d}/${y}`;
    case 'DD/MM/YYYY':
      return `${d}/${m}/${y}`;
    case 'YYYY-MM-DD':
    default:
      return `${y}-${m}-${d}`;
  }
}

/**
 * Format a date/time string
 */
export function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  const datePart = applyDateFormat(date);
  const timePart = date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
  return `${datePart} ${timePart}`;
}

/**
 * Format a date string
 */
export function formatDate(dateString: string): string {
  return applyDateFormat(new Date(dateString));
}

/**
 * Format a time string
 */
export function formatTime(dateString: string): string {
  return new Date(dateString).toLocaleTimeString();
}
