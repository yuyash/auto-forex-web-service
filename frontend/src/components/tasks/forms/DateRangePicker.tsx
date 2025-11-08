import React from 'react';
import { Box, FormHelperText } from '@mui/material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';

interface DateRangePickerProps {
  startDate: Date | null;
  endDate: Date | null;
  onStartDateChange: (date: Date | null) => void;
  onEndDateChange: (date: Date | null) => void;
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
  // Validation
  const startError = React.useMemo(() => {
    if (!startDate && required) {
      return 'Start date is required';
    }
    if (startDate && endDate && startDate >= endDate) {
      return 'Start date must be before end date';
    }
    if (startDate && maxDate && startDate > maxDate) {
      return `Start date must be before ${maxDate.toLocaleDateString()}`;
    }
    return null;
  }, [startDate, endDate, required, maxDate]);

  const endError = React.useMemo(() => {
    if (!endDate && required) {
      return 'End date is required';
    }
    if (startDate && endDate && endDate <= startDate) {
      return 'End date must be after start date';
    }
    if (endDate && minDate && endDate < minDate) {
      return `End date must be after ${minDate.toLocaleDateString()}`;
    }
    return null;
  }, [startDate, endDate, required, minDate]);

  const hasError = !!error || !!startError || !!endError;
  const displayError = error || startError || endError;

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Box sx={{ flex: 1, minWidth: 250 }}>
            <DateTimePicker
              label={startLabel}
              value={startDate}
              onChange={onStartDateChange}
              disabled={disabled}
              minDate={minDate}
              maxDate={endDate || maxDate}
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
              value={endDate}
              onChange={onEndDateChange}
              disabled={disabled}
              minDate={startDate || minDate}
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
        {!hasError && !helperText && startDate && endDate && (
          <FormHelperText sx={{ mt: -1 }}>
            Duration: {calculateDuration(startDate, endDate)}
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
