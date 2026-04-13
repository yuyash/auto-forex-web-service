import React from 'react';
import { Box, FormHelperText } from '@mui/material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import {
  fromTimezonePickerDate,
  toTimezonePickerDate,
} from '../../../utils/timezone';

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
  startLabel = 'Start Date',
  endLabel = 'End Date',
  required = false,
  disabled = false,
  error,
  helperText,
  minDate,
  maxDate,
  timezone = 'UTC',
}) => {
  const startDateValue = toTimezonePickerDate(startDate, timezone);
  const endDateValue = toTimezonePickerDate(endDate, timezone);
  const minDateValue = toTimezonePickerDate(minDate ?? null, timezone);
  const maxDateValue = toTimezonePickerDate(maxDate ?? null, timezone);

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
      return 'Start date is required';
    }
    if (startDateValue && !isValidDate(startDateValue)) {
      return 'Invalid date';
    }
    if (
      startDateValue &&
      endDateValue &&
      isValidDate(startDateValue) &&
      isValidDate(endDateValue) &&
      startDateValue >= endDateValue
    ) {
      return 'Start date must be before end date';
    }
    if (
      startDateValue &&
      maxDateValue &&
      isValidDate(startDateValue) &&
      startDateValue > maxDateValue
    ) {
      return `Start date must be before ${maxDateValue.toLocaleDateString()}`;
    }
    return null;
  }, [endDateValue, maxDateValue, required, startDateValue]);

  const endError = React.useMemo(() => {
    if (!endDateValue && required) {
      return 'End date is required';
    }
    if (endDateValue && !isValidDate(endDateValue)) {
      return 'Invalid date';
    }
    if (
      startDateValue &&
      endDateValue &&
      isValidDate(startDateValue) &&
      isValidDate(endDateValue) &&
      endDateValue <= startDateValue
    ) {
      return 'End date must be after start date';
    }
    if (
      endDateValue &&
      minDateValue &&
      isValidDate(endDateValue) &&
      endDateValue < minDateValue
    ) {
      return `End date must be after ${minDateValue.toLocaleDateString()}`;
    }
    return null;
  }, [endDateValue, minDateValue, required, startDateValue]);

  const hasError = !!error || !!startError || !!endError;
  const displayError = error || startError || endError;

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Box sx={{ flex: 1, minWidth: { xs: '100%', sm: 250 } }}>
            <DateTimePicker
              label={startLabel}
              value={startDateValue}
              onChange={handleStartChange}
              disabled={disabled}
              minDate={minDateValue ?? undefined}
              maxDate={endDateValue || maxDateValue || undefined}
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
              label={endLabel}
              value={endDateValue}
              onChange={handleEndChange}
              disabled={disabled}
              minDate={startDateValue || minDateValue || undefined}
              maxDate={maxDateValue ?? undefined}
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
