import React from 'react';
import { TextField, type TextFieldProps } from '@mui/material';

interface ValidatedTextFieldProps
  extends Omit<TextFieldProps, 'error' | 'helperText'> {
  error?: string;
  touched?: boolean;
  onBlurValidation?: (value: string) => void;
  onChangeValidation?: (value: string) => void;
}

/**
 * TextField component with integrated validation error display
 * Automatically shows error state and message when field has been touched
 */
const ValidatedTextField: React.FC<ValidatedTextFieldProps> = ({
  error,
  touched,
  onBlurValidation,
  onChangeValidation,
  onBlur,
  onChange,
  ...props
}) => {
  const hasError = Boolean(error && touched);

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    onBlur?.(e);
    onBlurValidation?.(e.target.value);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange?.(e);
    onChangeValidation?.(e.target.value);
  };

  return (
    <>
      <TextField
        {...props}
        error={hasError}
        onBlur={handleBlur}
        onChange={handleChange}
        helperText={hasError ? error : props.helperText}
      />
    </>
  );
};

export default ValidatedTextField;
