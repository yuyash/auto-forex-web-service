import React from 'react';
import { Alert, AlertTitle, List, ListItem, ListItemText } from '@mui/material';

interface FormErrorSummaryProps {
  errors: Record<string, string | string[]>;
  title?: string;
}

/**
 * Component for displaying form-level validation errors
 * Shows a summary of all validation errors at the top of the form
 */
const FormErrorSummary: React.FC<FormErrorSummaryProps> = ({
  errors,
  title = 'Please fix the following errors:',
}) => {
  const errorEntries = Object.entries(errors).filter(
    ([, value]) => value && (Array.isArray(value) ? value.length > 0 : true)
  );

  if (errorEntries.length === 0) {
    return null;
  }

  return (
    <Alert severity="error" sx={{ mb: 3 }}>
      <AlertTitle>{title}</AlertTitle>
      <List dense disablePadding>
        {errorEntries.map(([field, error]) => {
          const errorMessages = Array.isArray(error) ? error : [error];
          return errorMessages.map((msg, index) => (
            <ListItem key={`${field}-${index}`} disablePadding>
              <ListItemText
                primary={`${field.charAt(0).toUpperCase() + field.slice(1)}: ${msg}`}
              />
            </ListItem>
          ));
        })}
      </List>
    </Alert>
  );
};

export default FormErrorSummary;
