import { fromZonedTime, toZonedTime } from 'date-fns-tz';
import { readAppSettings } from '../hooks/useAppSettings';

export function getLocaleForLanguage(language?: string): string {
  return language?.startsWith('ja') ? 'ja-JP' : 'en-US';
}

export function formatDateTimeInTimezone(
  value: Date | string | null | undefined,
  timezone: string,
  language?: string,
  options?: {
    includeSeconds?: boolean;
    includeTimezone?: boolean;
  }
): string {
  if (!value) return '-';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '-';

  const locale = getLocaleForLanguage(language);
  const { dateFormat } = readAppSettings();
  const formatter = new Intl.DateTimeFormat(locale, {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    ...(options?.includeSeconds ? { second: '2-digit' } : {}),
    ...(options?.includeTimezone ? { timeZoneName: 'short' } : {}),
  });
  const parts = formatter.formatToParts(date);
  const values = Object.fromEntries(
    parts
      .filter((part) => part.type !== 'literal')
      .map((part) => [part.type, part.value])
  ) as Record<string, string | undefined>;

  const datePart =
    dateFormat === 'MM/DD/YYYY'
      ? `${values.month}/${values.day}/${values.year}`
      : dateFormat === 'DD/MM/YYYY'
        ? `${values.day}/${values.month}/${values.year}`
        : `${values.year}-${values.month}-${values.day}`;

  const timeSegments = [values.hour, values.minute];
  if (options?.includeSeconds) {
    timeSegments.push(values.second);
  }
  const timePart = timeSegments.filter(Boolean).join(':');
  const zonePart =
    options?.includeTimezone && values.timeZoneName
      ? ` ${values.timeZoneName}`
      : '';

  return `${datePart} ${timePart}${zonePart}`;
}

export function formatDateInTimezone(
  value: Date | string | null | undefined,
  timezone: string,
  language?: string
): string {
  if (!value) return '-';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '-';

  const locale = getLocaleForLanguage(language);
  const { dateFormat } = readAppSettings();
  const formatter = new Intl.DateTimeFormat(locale, {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
  const parts = formatter.formatToParts(date);
  const values = Object.fromEntries(
    parts
      .filter((part) => part.type !== 'literal')
      .map((part) => [part.type, part.value])
  ) as Record<string, string | undefined>;

  if (dateFormat === 'MM/DD/YYYY') {
    return `${values.month}/${values.day}/${values.year}`;
  }
  if (dateFormat === 'DD/MM/YYYY') {
    return `${values.day}/${values.month}/${values.year}`;
  }
  return `${values.year}-${values.month}-${values.day}`;
}

export function formatTimestampWithTimezone(
  value: Date | string | null | undefined,
  timezone: string,
  language?: string
): string {
  return formatDateTimeInTimezone(value, timezone, language, {
    includeSeconds: true,
    includeTimezone: true,
  });
}

export function toTimezonePickerDate(
  value: Date | string | null | undefined,
  timezone: string
): Date | null {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return toZonedTime(date, timezone);
}

export function fromTimezonePickerDate(
  value: Date | null,
  timezone: string
): string | null {
  if (!value || Number.isNaN(value.getTime())) return null;
  return fromZonedTime(value, timezone).toISOString();
}
