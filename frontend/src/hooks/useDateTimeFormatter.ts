import { useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useAppSettings } from './useAppSettings';
import {
  formatDateInTimezone,
  formatDateTimeInTimezone,
  getTimezoneAbbreviation,
  type DateTimeFormatOptions,
} from '../utils/timezone';

export function useDateTimeFormatter(
  defaultOptions: DateTimeFormatOptions = {}
) {
  const { user } = useAuth();
  const { settings } = useAppSettings();
  const timezone = user?.timezone || 'UTC';
  const language = user?.language;
  const dateFormat = settings.dateFormat;
  const { includeSeconds, includeMilliseconds, includeTimezone } =
    defaultOptions;

  const formatDateTime = useCallback(
    (
      value: Date | string | null | undefined,
      options?: DateTimeFormatOptions
    ) =>
      formatDateTimeInTimezone(value, timezone, language, {
        includeSeconds,
        includeMilliseconds,
        includeTimezone,
        ...options,
        dateFormat,
      }),
    [
      dateFormat,
      includeMilliseconds,
      includeSeconds,
      includeTimezone,
      language,
      timezone,
    ]
  );

  const formatDate = useCallback(
    (value: Date | string | null | undefined) =>
      formatDateInTimezone(value, timezone, language, { dateFormat }),
    [dateFormat, language, timezone]
  );

  const getTimezoneLabel = useCallback(
    (value: Date | string = new Date()) =>
      getTimezoneAbbreviation(timezone, value, language),
    [language, timezone]
  );

  return {
    timezone,
    language,
    formatDateTime,
    formatDate,
    getTimezoneLabel,
  };
}
