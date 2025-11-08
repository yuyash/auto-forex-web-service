import React from 'react';
import { TextField, InputAdornment, FormHelperText } from '@mui/material';

interface BalanceInputProps {
  value: string | number;
  onChange: (value: string) => void;
  label?: string;
  required?: boolean;
  disabled?: boolean;
  error?: string;
  helperText?: string;
  currency?: string;
  min?: number;
  max?: number;
  decimalPlaces?: number;
}

export const BalanceInput: React.FC<BalanceInputProps> = ({
  value,
  onChange,
  label = 'Initial Balance',
  required = false,
  disabled = false,
  error,
  helperText,
  currency = 'USD',
  min = 0,
  max,
  decimalPlaces = 2,
}) => {
  const [internalValue, setInternalValue] = React.useState(value.toString());

  // Sync internal value with prop value
  React.useEffect(() => {
    setInternalValue(value.toString());
  }, [value]);

  const validationError = React.useMemo(() => {
    if (!internalValue && required) {
      return 'Balance is required';
    }

    const numValue = parseFloat(internalValue);

    if (internalValue && isNaN(numValue)) {
      return 'Please enter a valid number';
    }

    if (!isNaN(numValue)) {
      if (numValue < min) {
        return `Balance must be at least ${formatCurrency(min, currency)}`;
      }
      if (max !== undefined && numValue > max) {
        return `Balance must not exceed ${formatCurrency(max, currency)}`;
      }
      if (numValue <= 0) {
        return 'Balance must be greater than zero';
      }
    }

    return null;
  }, [internalValue, required, min, max, currency]);

  const displayError = error || validationError;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;

    // Allow empty string
    if (newValue === '') {
      setInternalValue('');
      onChange('');
      return;
    }

    // Allow numbers with optional decimal point and digits
    const regex = new RegExp(`^\\d*\\.?\\d{0,${decimalPlaces}}$`);
    if (regex.test(newValue)) {
      setInternalValue(newValue);
      onChange(newValue);
    }
  };

  const handleBlur = () => {
    // Format the value on blur
    const numValue = parseFloat(internalValue);
    if (!isNaN(numValue)) {
      const formatted = numValue.toFixed(decimalPlaces);
      setInternalValue(formatted);
      onChange(formatted);
    }
  };

  const numValue = parseFloat(internalValue);
  const isValid = !isNaN(numValue) && numValue > 0;

  return (
    <>
      <TextField
        fullWidth
        label={label}
        value={internalValue}
        onChange={handleChange}
        onBlur={handleBlur}
        required={required}
        disabled={disabled}
        error={!!displayError}
        type="text"
        inputMode="decimal"
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">{currency}</InputAdornment>
          ),
        }}
        helperText={displayError || helperText}
      />
      {!displayError && !helperText && isValid && (
        <FormHelperText>{formatCurrency(numValue, currency)}</FormHelperText>
      )}
    </>
  );
};

function formatCurrency(value: number, currency: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}
