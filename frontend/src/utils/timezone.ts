import { fromZonedTime, toZonedTime } from 'date-fns-tz';
import { readAppSettings, type AppSettings } from '../hooks/useAppSettings';

export interface DateTimeFormatOptions {
  includeSeconds?: boolean;
  includeMilliseconds?: boolean;
  includeTimezone?: boolean;
  dateFormat?: AppSettings['dateFormat'];
}

export function getLocaleForLanguage(language?: string): string {
  return language?.startsWith('ja') ? 'ja-JP' : 'en-US';
}

export function formatDateTimeInTimezone(
  value: Date | string | null | undefined,
  timezone: string,
  language?: string,
  options?: DateTimeFormatOptions
): string {
  if (!value) return '-';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '-';

  const locale = getLocaleForLanguage(language);
  const dateFormat = options?.dateFormat ?? readAppSettings().dateFormat;
  const formatter = new Intl.DateTimeFormat(locale, {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    ...(options?.includeSeconds || options?.includeMilliseconds
      ? { second: '2-digit' }
      : {}),
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

  const timeSegments = [normalizeHour(values.hour), values.minute];
  if (options?.includeSeconds || options?.includeMilliseconds) {
    timeSegments.push(values.second);
  }
  const millisecondsPart = options?.includeMilliseconds
    ? `.${String(date.getMilliseconds()).padStart(3, '0')}`
    : '';
  const timePart = `${timeSegments.filter(Boolean).join(':')}${millisecondsPart}`;
  const zonePart = options?.includeTimezone
    ? ` ${getTimezoneAbbreviation(timezone, date, language)}`
    : '';

  return `${datePart} ${timePart}${zonePart}`;
}

type ZoneOffsetAbbrMap = Record<string, Record<string, string>>;

const TIMEZONE_ABBR_BY_ZONE_AND_OFFSET: ZoneOffsetAbbrMap = {
  'America/Chicago': { 'GMT-6': 'CST', 'GMT-5': 'CDT' },
  'America/Denver': { 'GMT-7': 'MST', 'GMT-6': 'MDT' },
  'America/Mexico_City': { 'GMT-6': 'CST', 'GMT-5': 'CDT' },
  'America/Sao_Paulo': { 'GMT-3': 'BRT', 'GMT-2': 'BRST' },
  'Asia/Bangkok': { 'GMT+7': 'ICT' },
  'Asia/Dubai': { 'GMT+4': 'GST' },
  'Asia/Hong_Kong': { 'GMT+8': 'HKT' },
  'Asia/Kolkata': { 'GMT+5:30': 'IST' },
  'Asia/Seoul': { 'GMT+9': 'KST' },
  'Asia/Shanghai': { 'GMT+8': 'CST' },
  'Asia/Singapore': { 'GMT+8': 'SGT' },
  'Asia/Tokyo': { 'GMT+9': 'JST' },
  'Australia/Brisbane': { 'GMT+10': 'AEST' },
  'Australia/Melbourne': { 'GMT+10': 'AEST', 'GMT+11': 'AEDT' },
  'Australia/Sydney': { 'GMT+10': 'AEST', 'GMT+11': 'AEDT' },
  'Europe/Amsterdam': { 'GMT+1': 'CET', 'GMT+2': 'CEST' },
  'Europe/Berlin': { 'GMT+1': 'CET', 'GMT+2': 'CEST' },
  'Europe/Brussels': { 'GMT+1': 'CET', 'GMT+2': 'CEST' },
  'Europe/London': { GMT: 'GMT', 'GMT+1': 'BST' },
  'Europe/Madrid': { 'GMT+1': 'CET', 'GMT+2': 'CEST' },
  'Europe/Paris': { 'GMT+1': 'CET', 'GMT+2': 'CEST' },
  'Europe/Rome': { 'GMT+1': 'CET', 'GMT+2': 'CEST' },
  'Europe/Stockholm': { 'GMT+1': 'CET', 'GMT+2': 'CEST' },
  'Europe/Vienna': { 'GMT+1': 'CET', 'GMT+2': 'CEST' },
  'Europe/Moscow': { 'GMT+3': 'MSK' },
  'Pacific/Auckland': { 'GMT+12': 'NZST', 'GMT+13': 'NZDT' },
};

function normalizeHour(hour?: string): string | undefined {
  if (hour !== '24') return hour;
  return '00';
}

function normalizeGmtOffset(value: string): string {
  return value
    .replace('UTC', 'GMT')
    .replace(/GMT([+-])0(\d)(?::00)?$/, 'GMT$1$2')
    .replace(/GMT([+-]\d{1,2}):00$/, 'GMT$1');
}

function isShortTimezoneName(value: string): boolean {
  return /^[A-Z]{2,5}$/.test(value);
}

function readIntlTimezoneName(
  timezone: string,
  date: Date,
  locale: string
): string | null {
  try {
    const parts = new Intl.DateTimeFormat(locale, {
      timeZone: timezone,
      timeZoneName: 'short',
    }).formatToParts(date);
    return parts.find((part) => part.type === 'timeZoneName')?.value ?? null;
  } catch {
    return null;
  }
}

export function getTimezoneAbbreviation(
  timezone: string,
  value: Date | string = new Date(),
  language?: string
): string {
  const date = value instanceof Date ? value : new Date(value);
  const safeDate = Number.isNaN(date.getTime()) ? new Date() : date;
  const resolvedTimezone = timezone || 'UTC';
  if (resolvedTimezone === 'UTC') return 'UTC';

  const localeNames = [
    readIntlTimezoneName(
      resolvedTimezone,
      safeDate,
      getLocaleForLanguage(language)
    ),
    readIntlTimezoneName(resolvedTimezone, safeDate, 'en-US'),
  ].filter(Boolean) as string[];

  const directShortName = localeNames.find((name) => isShortTimezoneName(name));
  if (directShortName) return directShortName;

  const offsetName = localeNames
    .map((name) => normalizeGmtOffset(name))
    .find((name) => name.startsWith('GMT'));
  const mapped = offsetName
    ? TIMEZONE_ABBR_BY_ZONE_AND_OFFSET[resolvedTimezone]?.[offsetName]
    : undefined;
  if (mapped) return mapped;

  return offsetName ?? resolvedTimezone;
}

export function formatDateInTimezone(
  value: Date | string | null | undefined,
  timezone: string,
  language?: string,
  options?: Pick<DateTimeFormatOptions, 'dateFormat'>
): string {
  if (!value) return '-';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '-';

  const locale = getLocaleForLanguage(language);
  const dateFormat = options?.dateFormat ?? readAppSettings().dateFormat;
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
