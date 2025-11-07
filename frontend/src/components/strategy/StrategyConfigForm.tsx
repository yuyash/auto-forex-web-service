import { useState, useEffect } from 'react';
import {
  Box,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormHelperText,
  Typography,
  Alert,
  Divider,
  Checkbox,
  FormControlLabel,
  Stack,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import type {
  ConfigSchema,
  ConfigProperty,
  StrategyConfig,
} from '../../types/strategy';

interface StrategyConfigFormProps {
  configSchema: ConfigSchema;
  config: StrategyConfig;
  onChange: (config: StrategyConfig) => void;
  disabled?: boolean;
  showValidation?: boolean;
}

interface ValidationErrors {
  [key: string]: string;
}

const StrategyConfigForm = ({
  configSchema,
  config,
  onChange,
  disabled = false,
  showValidation = false,
}: StrategyConfigFormProps) => {
  const { t } = useTranslation('strategy');
  const [validationErrors, setValidationErrors] = useState<ValidationErrors>(
    {}
  );

  // Validate config against schema
  const validateConfig = (currentConfig: StrategyConfig): ValidationErrors => {
    const errors: ValidationErrors = {};

    // Check required fields
    if (configSchema.required) {
      configSchema.required.forEach((fieldName) => {
        if (
          currentConfig[fieldName] === undefined ||
          currentConfig[fieldName] === null ||
          currentConfig[fieldName] === ''
        ) {
          errors[fieldName] = t('validation.required', {
            defaultValue: 'This field is required',
          });
        }
      });
    }

    // Validate field types and constraints
    Object.entries(configSchema.properties || {}).forEach(
      ([fieldName, fieldSchema]) => {
        const value = currentConfig[fieldName];

        // Skip validation if field is empty and not required
        if (
          value === undefined ||
          value === null ||
          value === '' ||
          (Array.isArray(value) && value.length === 0)
        ) {
          return;
        }

        // Number validation
        if (fieldSchema.type === 'number' || fieldSchema.type === 'integer') {
          const numValue = Number(value);

          if (isNaN(numValue)) {
            errors[fieldName] = t('validation.invalidNumber', {
              defaultValue: 'Must be a valid number',
            });
            return;
          }

          if (
            fieldSchema.minimum !== undefined &&
            numValue < fieldSchema.minimum
          ) {
            errors[fieldName] = t('validation.minimum', {
              defaultValue: `Must be at least ${fieldSchema.minimum}`,
              min: fieldSchema.minimum,
            });
          }

          if (
            fieldSchema.maximum !== undefined &&
            numValue > fieldSchema.maximum
          ) {
            errors[fieldName] = t('validation.maximum', {
              defaultValue: `Must be at most ${fieldSchema.maximum}`,
              max: fieldSchema.maximum,
            });
          }

          if (fieldSchema.type === 'integer' && !Number.isInteger(numValue)) {
            errors[fieldName] = t('validation.integer', {
              defaultValue: 'Must be a whole number',
            });
          }
        }

        // Array validation
        if (fieldSchema.type === 'array' && Array.isArray(value)) {
          if (fieldSchema.items?.type === 'string') {
            const invalidItems = value.filter(
              (item) => typeof item !== 'string'
            );
            if (invalidItems.length > 0) {
              errors[fieldName] = t('validation.invalidArray', {
                defaultValue: 'All items must be strings',
              });
            }
          }
        }

        // Enum validation
        if (fieldSchema.enum && !fieldSchema.enum.includes(String(value))) {
          errors[fieldName] = t('validation.invalidOption', {
            defaultValue: 'Invalid option selected',
          });
        }
      }
    );

    return errors;
  };

  // Validate on config change
  useEffect(() => {
    if (showValidation) {
      const errors = validateConfig(config);
      setValidationErrors(errors);
    } else {
      setValidationErrors({});
    }
    // validateConfig is stable and doesn't need to be in deps
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config, showValidation, configSchema]);

  // Handle field change
  const handleFieldChange = (fieldName: string, value: unknown) => {
    const updatedConfig = {
      ...config,
      [fieldName]: value,
    };
    onChange(updatedConfig);
  };

  // Render field based on schema type
  const renderField = (fieldName: string, fieldSchema: ConfigProperty) => {
    const value = config[fieldName] ?? fieldSchema.default ?? '';
    const error = validationErrors[fieldName];
    const isRequired = configSchema.required?.includes(fieldName);

    // Enum field (dropdown)
    if (fieldSchema.enum) {
      const isProgressionField =
        fieldName.includes('progression') || fieldName.includes('mode');

      return (
        <FormControl
          fullWidth
          key={fieldName}
          error={!!error}
          disabled={disabled}
        >
          <InputLabel required={isRequired}>
            {formatFieldLabel(fieldName)}
          </InputLabel>
          <Select
            value={String(value)}
            label={formatFieldLabel(fieldName)}
            onChange={(e) => handleFieldChange(fieldName, e.target.value)}
          >
            {fieldSchema.enum.map((option: string) => (
              <MenuItem key={option} value={option}>
                <Box>
                  <Typography variant="body2">
                    {formatEnumValue(option)}
                  </Typography>
                  {isProgressionField && (
                    <Typography variant="caption" color="text.secondary">
                      {getProgressionDescription(option)}
                    </Typography>
                  )}
                </Box>
              </MenuItem>
            ))}
          </Select>
          {(fieldSchema.description || error) && (
            <FormHelperText>{error || fieldSchema.description}</FormHelperText>
          )}
        </FormControl>
      );
    }

    // Boolean field (checkbox)
    if (fieldSchema.type === 'boolean') {
      return (
        <FormControlLabel
          key={fieldName}
          control={
            <Checkbox
              checked={Boolean(value)}
              onChange={(e) => handleFieldChange(fieldName, e.target.checked)}
              disabled={disabled}
            />
          }
          label={
            <Box>
              <Typography variant="body1">
                {formatFieldLabel(fieldName)}
                {isRequired && (
                  <Typography component="span" color="error">
                    {' '}
                    *
                  </Typography>
                )}
              </Typography>
              {fieldSchema.description && (
                <Typography variant="caption" color="text.secondary">
                  {fieldSchema.description}
                </Typography>
              )}
            </Box>
          }
        />
      );
    }

    // Number field
    if (fieldSchema.type === 'number' || fieldSchema.type === 'integer') {
      return (
        <TextField
          key={fieldName}
          fullWidth
          label={formatFieldLabel(fieldName)}
          type="number"
          value={value}
          onChange={(e) => {
            const numValue =
              fieldSchema.type === 'integer'
                ? parseInt(e.target.value, 10)
                : parseFloat(e.target.value);
            handleFieldChange(fieldName, isNaN(numValue) ? '' : numValue);
          }}
          helperText={error || fieldSchema.description}
          error={!!error}
          required={isRequired}
          disabled={disabled}
          inputProps={{
            min: fieldSchema.minimum,
            max: fieldSchema.maximum,
            step: fieldSchema.type === 'integer' ? 1 : 'any',
          }}
        />
      );
    }

    // Array field (comma-separated string input)
    if (fieldSchema.type === 'array') {
      const arrayValue = Array.isArray(value) ? value.join(', ') : '';
      return (
        <TextField
          key={fieldName}
          fullWidth
          label={formatFieldLabel(fieldName)}
          value={arrayValue}
          onChange={(e) => {
            const items = e.target.value
              .split(',')
              .map((item) => item.trim())
              .filter((item) => item.length > 0);
            handleFieldChange(fieldName, items);
          }}
          helperText={
            error || fieldSchema.description || 'Enter comma-separated values'
          }
          error={!!error}
          required={isRequired}
          disabled={disabled}
        />
      );
    }

    // Default: string field
    return (
      <TextField
        key={fieldName}
        fullWidth
        label={formatFieldLabel(fieldName)}
        value={value}
        onChange={(e) => handleFieldChange(fieldName, e.target.value)}
        helperText={error || fieldSchema.description}
        error={!!error}
        required={isRequired}
        disabled={disabled}
      />
    );
  };

  // Format field name to readable label
  const formatFieldLabel = (fieldName: string): string => {
    return fieldName
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  // Format enum value to readable text
  const formatEnumValue = (value: string): string => {
    return value
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  // Get description for progression modes
  const getProgressionDescription = (mode: string): string => {
    const descriptions: Record<string, string> = {
      equal: 'All layers use the same value',
      additive: 'Each layer adds the increment (e.g., 10, 15, 20)',
      exponential:
        'Each layer multiplies by increment (e.g., 10, 20, 40 with 2x)',
      inverse: 'Each layer divides (e.g., 10, 5, 3.33)',
    };
    return descriptions[mode] || '';
  };

  // Check if there are any validation errors
  const hasErrors = Object.keys(validationErrors).length > 0;

  if (
    !configSchema.properties ||
    Object.keys(configSchema.properties).length === 0
  ) {
    return (
      <Alert severity="info">
        {t('noParameters', {
          defaultValue: 'This strategy has no configurable parameters.',
        })}
      </Alert>
    );
  }

  return (
    <Box>
      {showValidation && hasErrors && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {t('validation.formErrors', {
            defaultValue: 'Please fix the errors below before proceeding.',
          })}
        </Alert>
      )}

      <Typography variant="subtitle1" gutterBottom>
        {t('strategyParameters', { defaultValue: 'Strategy Parameters' })}
      </Typography>

      <Divider sx={{ mb: 2 }} />

      <Stack spacing={2}>
        {Object.entries(configSchema.properties).map(
          ([fieldName, fieldSchema]) => (
            <Box key={fieldName}>{renderField(fieldName, fieldSchema)}</Box>
          )
        )}
      </Stack>

      {configSchema.required && configSchema.required.length > 0 && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ mt: 2, display: 'block' }}
        >
          * {t('requiredFields', { defaultValue: 'Required fields' })}
        </Typography>
      )}
    </Box>
  );
};

export default StrategyConfigForm;
