import {
  FormControl,
  FormHelperText,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from '@mui/material';
import { SUPPORTED_CURRENCIES } from '../../../constants/currencies';

interface CurrencyCodeFieldProps {
  id: string;
  label: string;
  value: string | undefined;
  onChange: (value: string) => void;
  options?: readonly string[];
  error?: boolean;
  helperText?: string;
  required?: boolean;
  disabled?: boolean;
}

export function CurrencyCodeField({
  id,
  label,
  value,
  onChange,
  options,
  error = false,
  helperText,
  required = false,
  disabled = false,
}: CurrencyCodeFieldProps) {
  const normalizedOptions = Array.from(
    new Set(
      (options ?? [])
        .map((currency) =>
          String(currency || '')
            .trim()
            .toUpperCase()
        )
        .filter((currency) => /^[A-Z]{3}$/.test(currency))
    )
  );
  if (normalizedOptions.length > 0) {
    const labelId = `${id}-label`;
    return (
      <FormControl
        fullWidth
        error={error}
        required={required}
        disabled={disabled}
      >
        <InputLabel id={labelId}>{label}</InputLabel>
        <Select
          labelId={labelId}
          id={id}
          label={label}
          value={value ?? ''}
          onChange={(event) =>
            onChange(String(event.target.value).toUpperCase())
          }
        >
          {normalizedOptions.map((currency) => (
            <MenuItem key={currency} value={currency}>
              {currency}
            </MenuItem>
          ))}
        </Select>
        {helperText ? <FormHelperText>{helperText}</FormHelperText> : null}
      </FormControl>
    );
  }

  const optionsId = `${id}-options`;
  return (
    <>
      <TextField
        fullWidth
        id={id}
        label={label}
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value.toUpperCase())}
        error={error}
        helperText={helperText}
        required={required}
        disabled={disabled}
        inputProps={{
          list: optionsId,
          maxLength: 3,
          pattern: '[A-Za-z]{3}',
          autoCapitalize: 'characters',
          autoComplete: 'off',
        }}
      />
      <datalist id={optionsId}>
        {SUPPORTED_CURRENCIES.map((currency) => (
          <option key={currency} value={currency} />
        ))}
      </datalist>
    </>
  );
}
