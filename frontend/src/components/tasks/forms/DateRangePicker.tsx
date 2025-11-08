import React from 'react';
import { Box, FormHelperText } from '@mui/material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';

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
}) => {
  // Convert string to Date if needed
  const toDate = (value: Date | string | null): Date | null => {
    if (!value) return null;
    if (value instanceof Date) return value;
    return new Date(value);
  };

  const startDateValue = toDate(startDate);
  const endDateValue = toDate(endDate);

  const handleStartChange = (date: Date | null) => {
    onStartDateChange(date ? date.toISOString() : null);
  };

  const handleEndChange = (date: Date | null) => {
    onEndDateChange(date ? date.toISOString() : null);
  };
  // Validation
  const startError = React.useMemo(() => {
    if (!startDateValue && required) {
      return 'Start date is required';
    }
    if (startDateValue && endDateValue && startDateValue >= endDateValue) {
      return 'Start date must be before end date';
    }
    if (startDateValue && maxDate && startDateValue > maxDate) {
      return `Start date must be before ${maxDate.toLocaleDateString()}`;
    }
    return null;
  }, [startDateValue, endDateValue, required, maxDate]);

  const endError = React.useMemo(() => {
    if (!endDateValue && required) {
      return 'End date is required';
    }
    if (startDateValue && endDateValue && endDateValue <= startDateValue) {
      return 'End date must be after start date';
    }
    if (endDateValue && minDate && endDateValue < minDate) {
      return `End date must be after ${minDate.toLocaleDateString()}`;
    }
    return null;
  }, [startDateValue, endDateValue, required, minDate]);

  const hasError = !!error || !!startError || !!endError;
  const displayError = error || startError || endError;

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Box sx={{ flex: 1, minWidth: 250 }}>
            <DateTimePicker
              label={startLabel}
              value={startDateValue}
              onChange={handleStartChange}
              disabled={disabled}
              minDate={minDate}
              maxDate={endDateValue || maxDate}
              slotProps={{
                textField: {
                  required,
                  error: !!startError,
                  fullWidth: true,
                },
              }}
            />
          </Box>
          <Box sx={{ flex: 1, minWidth: 250 }}>
            <DateTimePicker
              label={endLabel}
              value={endDateValue}
              onChange={handleEndChange}
              disabled={disabled}
              minDate={startDateValue || minDate}
              maxDate={maxDate}
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
