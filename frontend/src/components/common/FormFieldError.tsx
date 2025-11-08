import React from 'react';
import { FormHelperText } from '@mui/material';
import ErrorIcon from '@mui/icons-material/Error';

interface FormFieldErrorProps {
  error?: string;
  touched?: boolean;
}

/**
 * Component for displaying field-level validation errors
 * Shows error message with icon when field has been touched and has an error
 */
const FormFieldError: React.FC<FormFieldErrorProps> = ({ error, touched }) => {
  if (!error || !touched) {
    return null;
  }

  return (
    <FormHelperText
      error
      sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}
    >
      <ErrorIcon sx={{ fontSize: 16 }} />
      {error}
    </FormHelperText>
  );
};

export default FormFieldError;
