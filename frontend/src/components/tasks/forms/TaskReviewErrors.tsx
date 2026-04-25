import { Alert, Typography } from '@mui/material';
import type { FieldErrors, FieldValues } from 'react-hook-form';

interface TaskReviewErrorsProps<TValues extends FieldValues> {
  errors: FieldErrors<TValues>;
  fieldLabels?: Record<string, string>;
  title: string;
  correctionHint: string;
}

function formatFieldName(field: string, fieldLabels?: Record<string, string>) {
  return (
    fieldLabels?.[field] ||
    field.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
  );
}

function formatErrorMessage(error: unknown) {
  if (typeof error === 'object' && error !== null && 'message' in error) {
    const message = (error as { message?: unknown }).message;
    if (message) {
      return String(message);
    }
  }
  return JSON.stringify(error);
}

export function TaskReviewErrors<TValues extends FieldValues>({
  errors,
  fieldLabels,
  title,
  correctionHint,
}: TaskReviewErrorsProps<TValues>) {
  const entries = Object.entries(errors);
  if (entries.length === 0) {
    return null;
  }

  return (
    <Alert severity="error" sx={{ mb: 3 }}>
      <Typography variant="subtitle2" gutterBottom>
        {title}
      </Typography>
      {entries.map(([field, error]) => (
        <Typography key={field} variant="body2">
          • <strong>{formatFieldName(field, fieldLabels)}:</strong>{' '}
          {formatErrorMessage(error)}
        </Typography>
      ))}
      <Typography variant="body2" sx={{ mt: 1, fontStyle: 'italic' }}>
        {correctionHint}
      </Typography>
    </Alert>
  );
}
