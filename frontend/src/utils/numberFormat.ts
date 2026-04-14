import { readAppSettings } from '../hooks/useAppSettings';

interface FormatAppNumberOptions {
  minimumFractionDigits?: number;
  maximumFractionDigits?: number;
  useGrouping?: boolean;
  signed?: boolean;
}

function applySeparators(value: string): string {
  const { decimalSeparator, thousandsSeparator } = readAppSettings();
  const [integerPart, fractionPart] = value.split('.');
  const normalizedInteger = integerPart.replace(/,/g, thousandsSeparator);

  if (fractionPart == null) {
    return normalizedInteger;
  }

  return `${normalizedInteger}${decimalSeparator}${fractionPart}`;
}

export function formatAppNumber(
  value: number,
  options: FormatAppNumberOptions = {}
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
  return `${sign}${applySeparators(formatted)}`;
}

export function formatAppPercent(
  value: number,
  fractionDigits = 2,
  signed = false
): string {
  return `${formatAppNumber(value, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
    signed,
  })}%`;
}
