import { formatInTimeZone, fromZonedTime, toZonedTime } from 'date-fns-tz';

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
  return new Intl.DateTimeFormat(locale, {
    timeZone: timezone,
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    ...(options?.includeSeconds ? { second: '2-digit' } : {}),
    ...(options?.includeTimezone ? { timeZoneName: 'short' } : {}),
  }).format(date);
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
  return new Intl.DateTimeFormat(locale, {
    timeZone: timezone,
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date);
}

export function formatTimestampWithTimezone(
  value: Date | string | null | undefined,
  timezone: string
): string {
  if (!value) return '-';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return formatInTimeZone(date, timezone, 'yyyy-MM-dd HH:mm:ss zzz');
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
