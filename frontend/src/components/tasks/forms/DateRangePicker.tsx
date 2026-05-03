import React from 'react';
import { Box, FormHelperText } from '@mui/material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { useTranslation } from 'react-i18next';
import {
  fromTimezonePickerDate,
  getTimezoneAbbreviation,
  toTimezonePickerDate,
} from '../../../utils/timezone';
import {
  useAppSettings,
  type AppSettings,
} from '../../../hooks/useAppSettings';

interface DateRangePickerProps {
  startDate: Date | string | null;
  endDate: Date | string | null;
  onStartDateChange: (date: Date | string | null) => void;
  onEndDateChange: (date: Date | string | null) => void;
  startLabel?: string;
  endLabel?: string;
  required?: boolean;
  disabled?: boolean;
  error?: string;
  helperText?: string;
  minDate?: Date;
  maxDate?: Date;
  timezone?: string;
}

export const DateRangePicker: React.FC<DateRangePickerProps> = ({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  startLabel,
  endLabel,
  required = false,
  disabled = false,
  error,
  helperText,
  minDate,
  maxDate,
  timezone = 'UTC',
}) => {
  const { t } = useTranslation(['common']);
  const { settings } = useAppSettings();
  const startDateValue = toTimezonePickerDate(startDate, timezone);
  const endDateValue = toTimezonePickerDate(endDate, timezone);
  const minDateValue = toTimezonePickerDate(minDate ?? null, timezone);
  const maxDateValue = toTimezonePickerDate(maxDate ?? null, timezone);
  const pickerFormat = toDateFnsDateTimeFormat(settings.dateFormat);
  const resolvedStartLabel = startLabel ?? t('common:dateRange.startDate');
  const resolvedEndLabel = endLabel ?? t('common:dateRange.endDate');
  const referenceDate = React.useMemo(() => {
    const date = new Date();
    date.setHours(0, 0, 0, 0);
    return date;
  }, []);

  const isValidDate = (d: Date | null): d is Date =>
    d instanceof Date && !isNaN(d.getTime());

  const handleStartChange = (date: Date | null) => {
    onStartDateChange(
      date && isValidDate(date) ? fromTimezonePickerDate(date, timezone) : null
    );
  };

  const handleEndChange = (date: Date | null) => {
    onEndDateChange(
      date && isValidDate(date) ? fromTimezonePickerDate(date, timezone) : null
    );
  };
  // Validation
  const startError = React.useMemo(() => {
    if (!startDateValue && required) {
      return t('common:dateRange.startDateRequired');
    }
    if (startDateValue && !isValidDate(startDateValue)) {
      return t('common:dateRange.invalidDate');
    }
    if (
      startDateValue &&
      endDateValue &&
      isValidDate(startDateValue) &&
      isValidDate(endDateValue) &&
      startDateValue >= endDateValue
    ) {
      return t('common:dateRange.startBeforeEnd');
    }
    if (
      startDateValue &&
      maxDateValue &&
      isValidDate(startDateValue) &&
      startDateValue > maxDateValue
    ) {
      return t('common:dateRange.startBeforeDate', {
        date: formatPickerDate(maxDateValue, settings.dateFormat),
      });
    }
    return null;
  }, [
    endDateValue,
    maxDateValue,
    required,
    settings.dateFormat,
    startDateValue,
    t,
  ]);

  const endError = React.useMemo(() => {
    if (!endDateValue && required) {
      return t('common:dateRange.endDateRequired');
    }
    if (endDateValue && !isValidDate(endDateValue)) {
      return t('common:dateRange.invalidDate');
    }
    if (
      startDateValue &&
      endDateValue &&
      isValidDate(startDateValue) &&
      isValidDate(endDateValue) &&
      endDateValue <= startDateValue
    ) {
      return t('common:dateRange.endAfterStart');
    }
    if (
      endDateValue &&
      minDateValue &&
      isValidDate(endDateValue) &&
      endDateValue < minDateValue
    ) {
      return t('common:dateRange.endAfterDate', {
        date: formatPickerDate(minDateValue, settings.dateFormat),
      });
    }
    return null;
  }, [
    endDateValue,
    minDateValue,
    required,
    settings.dateFormat,
    startDateValue,
    t,
  ]);

  const hasError = !!error || !!startError || !!endError;
  const displayError = error || startError || endError;

  // Derive a short timezone label (e.g. "JST", "UTC") for display.
  const tzLabel = React.useMemo(() => {
    return getTimezoneAbbreviation(timezone);
  }, [timezone]);

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Box sx={{ flex: 1, minWidth: { xs: '100%', sm: 250 } }}>
            <DateTimePicker
              label={`${resolvedStartLabel} (${tzLabel})`}
              value={startDateValue}
              format={pickerFormat}
              onChange={handleStartChange}
              disabled={disabled}
              minDate={minDateValue ?? undefined}
              maxDate={endDateValue || maxDateValue || undefined}
              referenceDate={referenceDate}
              slotProps={{
                textField: {
                  required,
                  error: !!startError,
                  fullWidth: true,
                },
              }}
            />
          </Box>
          <Box sx={{ flex: 1, minWidth: { xs: '100%', sm: 250 } }}>
            <DateTimePicker
              label={`${resolvedEndLabel} (${tzLabel})`}
              value={endDateValue}
              format={pickerFormat}
              onChange={handleEndChange}
              disabled={disabled}
              minDate={startDateValue || minDateValue || undefined}
              maxDate={maxDateValue ?? undefined}
              referenceDate={referenceDate}
              slotProps={{
                textField: {
                  required,
                  error: !!endError,
                  fullWidth: true,
                },
              }}
            />
          </Box>
        </Box>
        {hasError && (
          <FormHelperText error sx={{ mt: -1 }}>
            {displayError}
          </FormHelperText>
        )}
        {!hasError && helperText && (
          <FormHelperText sx={{ mt: -1 }}>{helperText}</FormHelperText>
        )}
        {!hasError && !helperText && startDateValue && endDateValue && (
          <FormHelperText sx={{ mt: -1 }}>
            Duration: {calculateDuration(startDateValue, endDateValue)}
          </FormHelperText>
        )}
      </Box>
    </LocalizationProvider>
  );
};

function toDateFnsDateTimeFormat(
  dateFormat: AppSettings['dateFormat']
): string {
  if (dateFormat === 'MM/DD/YYYY') return 'MM/dd/yyyy HH:mm';
  if (dateFormat === 'DD/MM/YYYY') return 'dd/MM/yyyy HH:mm';
  return 'yyyy-MM-dd HH:mm';
}

function formatPickerDate(
  date: Date,
  dateFormat: AppSettings['dateFormat']
): string {
  const year = String(date.getFullYear()).padStart(4, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');

  if (dateFormat === 'MM/DD/YYYY') return `${month}/${day}/${year}`;
  if (dateFormat === 'DD/MM/YYYY') return `${day}/${month}/${year}`;
  return `${year}-${month}-${day}`;
}

function calculateDuration(start: Date, end: Date): string {
  const diffMs = end.getTime() - start.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const diffMonths = Math.floor(diffDays / 30);
  const diffYears = Math.floor(diffDays / 365);

  if (diffYears > 0) {
    const remainingMonths = Math.floor((diffDays % 365) / 30);
    return `${diffYears} year${diffYears > 1 ? 's' : ''}${remainingMonths > 0 ? ` ${remainingMonths} month${remainingMonths > 1 ? 's' : ''}` : ''}`;
  } else if (diffMonths > 0) {
    const remainingDays = diffDays % 30;
    return `${diffMonths} month${diffMonths > 1 ? 's' : ''}${remainingDays > 0 ? ` ${remainingDays} day${remainingDays > 1 ? 's' : ''}` : ''}`;
  } else {
    return `${diffDays} day${diffDays !== 1 ? 's' : ''}`;
  }
}
