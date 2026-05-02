import React from 'react';
import { TextField, InputAdornment, FormHelperText } from '@mui/material';
import { useNumberFormatter } from '../../../hooks/useNumberFormatter';
import {
  currencySymbol,
  formatAppNumber,
  type FormatAppNumberOptions,
} from '../../../utils/numberFormat';

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
  const { formatNumber, separators } = useNumberFormatter();
  const decimalSeparator = separators.decimalSeparator;
  const [internalValue, setInternalValue] = React.useState(
    value !== undefined && value !== null
      ? localizeEditableNumber(value.toString(), decimalSeparator)
      : ''
  );

  // Sync internal value with prop value
  React.useEffect(() => {
    setInternalValue(
      value !== undefined && value !== null
        ? localizeEditableNumber(value.toString(), decimalSeparator)
        : ''
    );
  }, [decimalSeparator, value]);

  const validationError = React.useMemo(() => {
    if (!internalValue && required) {
      return 'Balance is required';
    }

    const numValue = parseFloat(
      normalizeEditableNumber(internalValue, decimalSeparator)
    );

    if (internalValue && isNaN(numValue)) {
      return 'Please enter a valid number';
    }

    if (!isNaN(numValue)) {
      if (numValue < min) {
        return `Balance must be at least ${formatCurrency(min, currency, formatNumber)}`;
      }
      if (max !== undefined && numValue > max) {
        return `Balance must not exceed ${formatCurrency(max, currency, formatNumber)}`;
      }
      if (numValue <= 0) {
        return 'Balance must be greater than zero';
      }
    }

    return null;
  }, [
    internalValue,
    required,
    min,
    max,
    currency,
    formatNumber,
    decimalSeparator,
  ]);

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
    const decimalPattern = decimalSeparator === '.' ? '\\.' : decimalSeparator;
    const regex = new RegExp(
      `^\\d*(?:${decimalPattern}\\d{0,${decimalPlaces}})?$`
    );
    if (regex.test(newValue)) {
      setInternalValue(newValue);
      onChange(normalizeEditableNumber(newValue, decimalSeparator));
    }
  };

  const handleBlur = () => {
    // Format the value on blur
    const numValue = parseFloat(
      normalizeEditableNumber(internalValue, decimalSeparator)
    );
    if (!isNaN(numValue)) {
      const formatted = formatNumber(numValue, {
        minimumFractionDigits: decimalPlaces,
        maximumFractionDigits: decimalPlaces,
        useGrouping: false,
      });
      setInternalValue(formatted);
      onChange(formatNormalizedNumber(numValue, decimalPlaces));
    }
  };

  const numValue = parseFloat(
    normalizeEditableNumber(internalValue, decimalSeparator)
  );
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
        <FormHelperText>
          {formatCurrency(numValue, currency, formatNumber)}
        </FormHelperText>
      )}
    </>
  );
};

function formatCurrency(
  value: number,
  currency: string,
  formatNumber: (value: number, options?: FormatAppNumberOptions) => string
): string {
  const symbol = currencySymbol(currency);
  const prefix =
    symbol === currency.trim().toUpperCase() ? `${symbol} ` : symbol;
  return `${prefix}${formatNumber(value, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function normalizeEditableNumber(value: string, decimalSeparator: '.' | ',') {
  return decimalSeparator === ',' ? value.replace(',', '.') : value;
}

function localizeEditableNumber(value: string, decimalSeparator: '.' | ',') {
  return decimalSeparator === ',' ? value.replace('.', ',') : value;
}

function formatNormalizedNumber(value: number, decimalPlaces: number): string {
  return formatAppNumber(
    value,
    {
      minimumFractionDigits: decimalPlaces,
      maximumFractionDigits: decimalPlaces,
      useGrouping: false,
    },
    { decimalSeparator: '.', thousandsSeparator: '' }
  );
}
