import { TextField } from '@mui/material';
import { SUPPORTED_CURRENCIES } from '../../../constants/currencies';

interface CurrencyCodeFieldProps {
  id: string;
  label: string;
  value: string | undefined;
  onChange: (value: string) => void;
  error?: boolean;
  helperText?: string;
  required?: boolean;
}

export function CurrencyCodeField({
  id,
  label,
  value,
  onChange,
  error = false,
  helperText,
  required = false,
}: CurrencyCodeFieldProps) {
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
