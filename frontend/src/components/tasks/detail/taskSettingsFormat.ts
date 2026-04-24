import { formatDateTimeInTimezone } from '../../../utils/timezone';

export type TaskSettingValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | object;

export function formatBoolean(value: TaskSettingValue): string {
  return value ? 'Yes' : 'No';
}

export function formatSettingValue(value: TaskSettingValue): string {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'boolean') return formatBoolean(value);
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function formatDateTimeSetting(
  value: TaskSettingValue,
  timezone: string,
  language?: string
): string {
  if (!value) return '-';
  return formatDateTimeInTimezone(String(value), timezone, language, {
    includeTimezone: true,
  });
}
