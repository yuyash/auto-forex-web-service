import { useState, useEffect, useMemo } from 'react';
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
  Tooltip,
  IconButton,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
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

  const matchesDependsOn = (
    currentConfig: StrategyConfig,
    dependsOn: NonNullable<ConfigProperty['dependsOn']>
  ): boolean => {
    const matchesSingleCondition = (cond: {
      field: string;
      values: string[];
      and?: Array<{ field: string; values: string[] }>;
    }): boolean => {
      const raw = currentConfig[cond.field];
      const value = raw === undefined || raw === null ? '' : String(raw);
      if (!cond.values.includes(value)) return false;
      if (!cond.and || cond.and.length === 0) return true;
      return cond.and.every((andCond) => {
        const rawCond = currentConfig[andCond.field];
        const valueCond =
          rawCond === undefined || rawCond === null ? '' : String(rawCond);
        return andCond.values.includes(valueCond);
      });
    };

    if (matchesSingleCondition(dependsOn)) return true;
    if (!dependsOn.or || dependsOn.or.length === 0) return false;
    return dependsOn.or.some((orCond) => matchesSingleCondition(orCond));
  };

  useEffect(() => {
    if (!configSchema.properties) {
      return;
    }

    let updatedConfig: StrategyConfig | null = null;

    Object.entries(configSchema.properties).forEach(
      ([fieldName, fieldSchema]) => {
        if (!fieldSchema.dependsOn) {
          return;
        }

        const matches = matchesDependsOn(config, fieldSchema.dependsOn);

        if (
          !matches &&
          Object.prototype.hasOwnProperty.call(config, fieldName)
        ) {
          if (!updatedConfig) {
            updatedConfig = { ...config };
          }
          delete updatedConfig[fieldName];
        }
      }
    );

    if (updatedConfig) {
      onChange(updatedConfig);
    }
  }, [config, configSchema, onChange]);

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

  const renderLabel = (label: string, description?: string) => {
    if (!description) return label;
    return (
      <Box
        component="span"
        sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}
      >
        <span>{label}</span>
        <Tooltip title={description} placement="top" arrow>
          <IconButton size="small" aria-label={`${label} help`}>
            <InfoOutlinedIcon fontSize="inherit" />
          </IconButton>
        </Tooltip>
      </Box>
    );
  };

  // Render field based on schema type
  const renderField = (fieldName: string, fieldSchema: ConfigProperty) => {
    const value = config[fieldName] ?? fieldSchema.default ?? '';
    const error = validationErrors[fieldName];
    const isRequired = configSchema.required?.includes(fieldName);
    const label = fieldSchema.title ?? formatFieldLabel(fieldName);
    const labelNode = renderLabel(label, fieldSchema.description);

    // Enum field (dropdown)
    if (fieldSchema.enum) {
      const isProgressionField =
        fieldName.includes('progression') || fieldName.includes('mode');
      const isDirectionMethodField = fieldName === 'direction_method';
      const isNumericEnum = fieldSchema.enum.every(
        (opt) => typeof opt === 'number'
      );

      // Get description for enum option based on field type
      const getOptionDescription = (option: string | number): string => {
        if (isDirectionMethodField) {
          return getDirectionMethodDescription(String(option));
        }
        if (isProgressionField) {
          return getProgressionDescription(String(option));
        }
        return '';
      };

      // Format numeric enum values (e.g., granularity seconds to readable names)
      const formatNumericEnumValue = (val: number): string => {
        const granularityNames: Record<number, string> = {
          300: 'M5 (5 minutes)',
          900: 'M15 (15 minutes)',
          1800: 'M30 (30 minutes)',
          3600: 'H1 (1 hour)',
          7200: 'H2 (2 hours)',
          14400: 'H4 (4 hours)',
          28800: 'H8 (8 hours)',
          43200: 'H12 (12 hours)',
          86400: 'D1 (1 day)',
          604800: 'W1 (1 week)',
        };
        return granularityNames[val] || String(val);
      };

      const showOptionDescriptions =
        isProgressionField || isDirectionMethodField;

      const enumOptions = (fieldSchema.enum || []).filter((option) => {
        if (!isDirectionMethodField) return true;
        // Hide unsupported OHLC-based options until the UI provides candle inputs.
        return !String(option).startsWith('ohlc_');
      });

      return (
        <FormControl
          fullWidth
          size="small"
          key={fieldName}
          error={!!error}
          disabled={disabled}
        >
          <InputLabel required={isRequired}>{labelNode}</InputLabel>
          <Select
            size="small"
            value={isNumericEnum ? Number(value) : String(value)}
            label={label}
            onChange={(e) => {
              const newValue = isNumericEnum
                ? Number(e.target.value)
                : e.target.value;
              handleFieldChange(fieldName, newValue);
            }}
          >
            {enumOptions.map((option) => (
              <MenuItem key={String(option)} value={option}>
                <Box>
                  <Typography variant="body2">
                    {typeof option === 'number'
                      ? formatNumericEnumValue(option)
                      : formatEnumValue(String(option))}
                  </Typography>
                  {showOptionDescriptions && (
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{
                        display: 'block',
                        maxWidth: 400,
                        whiteSpace: 'normal',
                        lineHeight: 1.3,
                      }}
                    >
                      {getOptionDescription(option)}
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
              size="small"
              checked={Boolean(value)}
              onChange={(e) => handleFieldChange(fieldName, e.target.checked)}
              disabled={disabled}
            />
          }
          label={
            <Box>
              <Typography variant="body2">
                {renderLabel(label, fieldSchema.description)}
                {isRequired && (
                  <Typography component="span" color="error">
                    {' '}
                    *
                  </Typography>
                )}
              </Typography>
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
          size="small"
          label={labelNode}
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
          size="small"
          label={labelNode}
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
        size="small"
        label={labelNode}
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
      constant: 'Same value for every layer / retracement',
      additive: 'Increases by a fixed amount each time (e.g. 10 → 15 → 20)',
      subtractive:
        'Decreases by a fixed amount each time (e.g. 30 → 25 → 20, min 0)',
      multiplicative: 'Doubles each time (e.g. 10 → 20 → 40)',
      divisive: 'Halves each time (e.g. 40 → 20 → 10)',
      inverse: 'Halves each time (e.g. 1.0 → 0.5 → 0.25)',
    };
    return descriptions[mode] || '';
  };

  // Get description for direction decision methods
  const getDirectionMethodDescription = (method: string): string => {
    const descriptions: Record<string, string> = {
      // Tick-based methods
      momentum:
        'Analyzes price change over N ticks. Goes long if price increased, short if decreased. Simple and responsive to recent price action.',
      sma_crossover:
        'Uses two Simple Moving Averages on tick data. Goes long when fast SMA crosses above slow SMA, short when it crosses below. Good for trend following.',
      ema_crossover:
        'Uses two Exponential Moving Averages on tick data. Similar to SMA but gives more weight to recent prices. More responsive to price changes.',
      price_vs_sma:
        'Compares current price to a Simple Moving Average of ticks. Goes long when price is above SMA, short when below. Simple trend indicator.',
      rsi: 'Uses Relative Strength Index on tick data. Goes long when RSI is oversold (below threshold), short when overbought (above threshold). Good for mean reversion.',
      // OHLC-based methods (longer-term)
      ohlc_sma_crossover:
        'Uses SMA crossover on OHLC candles (hourly/daily). Better for longer-term trend following. Aggregates ticks into candles for smoother signals.',
      ohlc_ema_crossover:
        'Uses EMA crossover on OHLC candles (hourly/daily). Combines longer-term analysis with EMA responsiveness. Good for swing trading.',
      ohlc_price_vs_sma:
        'Compares current price to SMA of OHLC candle closes. Identifies if price is above/below longer-term average. Good for trend confirmation.',
    };
    return descriptions[method] || '';
  };

  // Check if there are any validation errors
  const hasErrors = Object.keys(validationErrors).length > 0;

  // Build ordered groups from schema properties
  // NOTE: This hook must be called before the early return below to satisfy
  // the Rules of Hooks (hooks must be called in the same order every render).
  const groupedFields = useMemo(() => {
    const groups: Array<{ name: string; fields: [string, ConfigProperty][] }> =
      [];
    const groupMap = new Map<string, [string, ConfigProperty][]>();
    const seenGroups: string[] = [];

    Object.entries(configSchema.properties || {}).forEach(
      ([fieldName, fieldSchema]) => {
        const groupName = fieldSchema.group || '';
        if (!groupMap.has(groupName)) {
          groupMap.set(groupName, []);
          seenGroups.push(groupName);
        }
        groupMap.get(groupName)!.push([fieldName, fieldSchema]);
      }
    );

    seenGroups.forEach((name) => {
      groups.push({ name, fields: groupMap.get(name)! });
    });

    return groups;
  }, [configSchema.properties]);

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

      {groupedFields.map(({ name: groupName, fields }, groupIdx) => {
        const visibleFields = fields.filter(([, fieldSchema]) => {
          if (!fieldSchema.dependsOn) return true;
          return matchesDependsOn(config, fieldSchema.dependsOn);
        });
        if (visibleFields.length === 0) return null;

        return (
          <Box key={groupName || '__ungrouped'} sx={{ mb: 3 }}>
            {groupIdx > 0 && <Divider sx={{ mb: 2 }} />}
            {groupName && (
              <Typography variant="subtitle1" gutterBottom>
                {groupName}
              </Typography>
            )}
            <Stack spacing={2}>
              {visibleFields.map(([fieldName, fieldSchema]) => (
                <Box key={fieldName}>{renderField(fieldName, fieldSchema)}</Box>
              ))}
            </Stack>
          </Box>
        );
      })}

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
