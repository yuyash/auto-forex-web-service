import { useState, useEffect, useMemo, useRef } from 'react';
import {
  Box,
  Stepper,
  Step,
  StepLabel,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  Alert,
  CircularProgress,
  Divider,
  Card,
  CardContent,
} from '@mui/material';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import StrategyConfigForm from '../strategy/StrategyConfigForm';
import { useStrategies } from '../../hooks/useStrategies';
import { strategiesApi } from '../../services/api';
import type { StrategyConfigCreateData } from '../../types/configuration';
import type { StrategyConfig, ConfigSchema } from '../../types/strategy';
import { STRATEGY_CONFIG_SCHEMAS } from './strategyConfigSchemas';

// Validation schema
const configurationSchema = z.object({
  name: z
    .string()
    .min(1, 'Name is required')
    .max(100, 'Name must be less than 100 characters'),
  strategy_type: z.string().min(1, 'Strategy type is required'),
  description: z
    .string()
    .max(500, 'Description must be less than 500 characters')
    .optional(),
  parameters: z.record(z.string(), z.unknown()),
});

type ConfigurationFormData = z.infer<typeof configurationSchema>;

interface ConfigurationFormProps {
  mode?: 'create' | 'edit';
  initialData?: Partial<ConfigurationFormData>;
  onSubmit: (data: StrategyConfigCreateData) => Promise<void>;
  onCancel: () => void;
  isLoading?: boolean;
}

// Default parameters for each strategy type
// These should match the required parameters in the backend strategy schemas
const DEFAULT_PARAMETERS: Record<string, Record<string, unknown>> = {
  floor: {
    base_lot_size: 1.0,
    lot_unit_size: 1000,
    retracement_lot_mode: 'additive',
    retracement_lot_amount: 1.0,
    retracement_pips: 30,
    take_profit_pips: 25,
    max_layers: 3,
    max_retracements_per_layer: 10,
    retracement_trigger_progression: 'constant',
    retracement_trigger_increment: 5.0,
    take_profit_trigger_progression: 'constant',
    take_profit_trigger_increment: 5.0,
    take_profit_pips_mode: 'constant',
    take_profit_pips_amount: 5.0,
    entry_signal_lookback_candles: 50,
    entry_signal_candle_granularity_seconds: 60,
    allow_duplicate_units: false,
    hedging_enabled: false,
    margin_protection_enabled: true,
    margin_rate: 0.04,
    margin_cut_start_ratio: 0.6,
    margin_cut_target_ratio: 0.5,
    volatility_check_enabled: true,
    volatility_lock_multiplier: 5.0,
    volatility_unlock_multiplier: 1.5,
    dynamic_parameter_adjustment_enabled: false,
    atr_period: 14,
    atr_baseline_period: 50,
    market_condition_override_enabled: true,
    market_condition_spread_limit_pips: 3.0,
  },
  ma_crossover: {
    instrument: 'USD_JPY',
    fast_period: 50,
    slow_period: 200,
    position_size: 1000,
    stop_loss_pips: 50,
    take_profit_pips: 100,
  },
  rsi: {
    instrument: 'USD_JPY',
    period: 14,
    oversold: 30,
    overbought: 70,
    position_size: 1000,
  },
  macd: {
    instrument: 'USD_JPY',
    fast_period: 12,
    slow_period: 26,
    signal_period: 9,
    position_size: 1000,
  },
  mean_reversion: {
    instrument: 'USD_JPY',
    period: 20,
    std_dev: 2,
    position_size: 1000,
  },
  scalping: {
    instrument: 'USD_JPY',
    position_size: 1000,
    stop_loss_pips: 10,
    take_profit_pips: 15,
  },
  swing_trading: {
    instrument: 'USD_JPY',
    position_size: 1000,
    stop_loss_pips: 100,
    take_profit_pips: 200,
  },
  stochastic: {
    instrument: 'USD_JPY',
    k_period: 14,
    d_period: 3,
    oversold: 20,
    overbought: 80,
    position_size: 1000,
  },
  arbitrage: {
    instrument: 'USD_JPY',
    position_size: 1000,
    min_spread: 0.0001,
  },
};

const getDefaultParameters = (
  strategyType: string,
  schema?: ConfigSchema,
  apiDefaults?: StrategyConfig
): StrategyConfig => {
  const effectiveSchema = schema ?? STRATEGY_CONFIG_SCHEMAS[strategyType];

  if (effectiveSchema) {
    const defaults: StrategyConfig = {};

    Object.entries(effectiveSchema.properties).forEach(([key, property]) => {
      if (property.default !== undefined) {
        defaults[key] = property.default;
      }
    });

    const merged = apiDefaults ? { ...defaults, ...apiDefaults } : defaults;
    return merged;
  }

  const fallback = DEFAULT_PARAMETERS[strategyType];
  const base = fallback ? { ...fallback } : {};
  return apiDefaults ? { ...base, ...apiDefaults } : base;
};

const ConfigurationForm = ({
  mode = 'create',
  initialData,
  onSubmit,
  onCancel,
  isLoading = false,
}: ConfigurationFormProps) => {
  const {
    strategies,
    isLoading: isStrategiesLoading,
    error: strategiesError,
  } = useStrategies();

  const isEditMode = mode === 'edit';
  const initialStrategyType = initialData?.strategy_type || '';
  const initialStrategySchema = useMemo<ConfigSchema | undefined>(() => {
    if (!initialStrategyType) return undefined;

    // Prefer the frontend-defined schema (which includes group metadata)
    // over the API-returned one.
    const frontendSchema = STRATEGY_CONFIG_SCHEMAS[initialStrategyType];
    if (frontendSchema) return frontendSchema;

    const fromApi = strategies.find((s) => s.id === initialStrategyType)
      ?.config_schema as unknown;

    if (
      fromApi &&
      typeof fromApi === 'object' &&
      fromApi !== null &&
      'properties' in fromApi
    ) {
      return fromApi as ConfigSchema;
    }

    return undefined;
  }, [initialStrategyType, strategies]);

  const initialParameters = useMemo<StrategyConfig>(() => {
    const defaults = initialStrategyType
      ? getDefaultParameters(initialStrategyType, initialStrategySchema)
      : {};

    if (initialData?.parameters) {
      return {
        ...defaults,
        ...initialData.parameters,
      };
    }

    return defaults;
  }, [initialStrategyType, initialData, initialStrategySchema]);

  const [activeStep, setActiveStep] = useState(0);
  const [parameters, setParameters] =
    useState<StrategyConfig>(initialParameters);
  const [strategyDefaults, setStrategyDefaults] =
    useState<StrategyConfig | null>(null);

  const hasUserEditedParamsRef = useRef(false);
  const lastDefaultsStrategyRef = useRef<string>('');

  const {
    control,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<ConfigurationFormData>({
    resolver: zodResolver(configurationSchema),
    defaultValues: {
      name: initialData?.name || '',
      strategy_type: initialStrategyType,
      description: initialData?.description || '',
      parameters: initialParameters,
    },
  });

  // Watch strategy_type for reactivity
  // eslint-disable-next-line react-hooks/incompatible-library
  const selectedStrategyType = watch('strategy_type');

  const selectedStrategy = useMemo(() => {
    return strategies.find((s) => s.id === selectedStrategyType);
  }, [strategies, selectedStrategyType]);

  const strategySchema = useMemo<ConfigSchema | undefined>(() => {
    if (!selectedStrategyType) return undefined;

    // Prefer the frontend-defined schema (which includes group metadata)
    // over the API-returned one.
    const frontendSchema = STRATEGY_CONFIG_SCHEMAS[selectedStrategyType];
    if (frontendSchema) return frontendSchema;

    const fromApi = selectedStrategy?.config_schema as unknown;
    if (
      fromApi &&
      typeof fromApi === 'object' &&
      fromApi !== null &&
      'properties' in fromApi
    ) {
      return fromApi as ConfigSchema;
    }

    return undefined;
  }, [selectedStrategy, selectedStrategyType]);

  const previousStrategyTypeRef = useRef<string>(initialStrategyType || '');
  const previousInitialDataRef =
    useRef<ConfigurationFormProps['initialData']>(initialData);

  // Fetch defaults for selected strategy from backend.
  useEffect(() => {
    const strategyType = selectedStrategyType || '';
    if (!strategyType) {
      setStrategyDefaults(null);
      lastDefaultsStrategyRef.current = '';
      return;
    }

    let isCancelled = false;

    (async () => {
      try {
        const resp = await strategiesApi.defaults(strategyType);
        if (isCancelled) return;
        setStrategyDefaults((resp.defaults ?? {}) as StrategyConfig);
        lastDefaultsStrategyRef.current = strategyType;
      } catch {
        if (isCancelled) return;
        setStrategyDefaults(null);
        lastDefaultsStrategyRef.current = strategyType;
      }
    })();

    return () => {
      isCancelled = true;
    };
  }, [selectedStrategyType]);

  // Update parameters when strategy type or initial data changes
  useEffect(() => {
    const currentType = selectedStrategyType || '';
    const previousType = previousStrategyTypeRef.current;
    const initialDataChanged = previousInitialDataRef.current !== initialData;

    if (currentType && currentType !== previousType) {
      hasUserEditedParamsRef.current = false;
    }

    if (!currentType) {
      if (previousType) {
        setParameters({});
        setValue('parameters', {});
      }
      previousStrategyTypeRef.current = currentType;
      previousInitialDataRef.current = initialData;
      return;
    }

    const defaultsForCurrentTypeReady =
      lastDefaultsStrategyRef.current === currentType;
    const shouldApplyDefaultsUpdate =
      !initialDataChanged &&
      currentType === previousType &&
      defaultsForCurrentTypeReady &&
      !hasUserEditedParamsRef.current;

    if (
      !initialDataChanged &&
      currentType === previousType &&
      !shouldApplyDefaultsUpdate
    ) {
      return;
    }

    const apiDefaults =
      defaultsForCurrentTypeReady && strategyDefaults
        ? strategyDefaults
        : undefined;
    const defaults = getDefaultParameters(
      currentType,
      strategySchema,
      apiDefaults
    );
    let nextParameters: StrategyConfig = { ...defaults };

    if (
      initialData &&
      initialData.strategy_type === currentType &&
      initialData.parameters
    ) {
      nextParameters = {
        ...defaults,
        ...initialData.parameters,
      };
    }

    setParameters(nextParameters);
    setValue('parameters', nextParameters);

    previousStrategyTypeRef.current = currentType;
    previousInitialDataRef.current = initialData;
  }, [
    selectedStrategyType,
    initialData,
    setValue,
    strategySchema,
    strategyDefaults,
  ]);

  const handleNext = (e?: React.MouseEvent) => {
    // Prevent form submission
    e?.preventDefault();
    setActiveStep((prev) => prev + 1);
  };

  const handleBack = (e?: React.MouseEvent) => {
    // Prevent form submission
    e?.preventDefault();
    setActiveStep((prev) => prev - 1);
  };

  const handleParameterChange = (key: string, value: unknown) => {
    hasUserEditedParamsRef.current = true;
    const newParameters: StrategyConfig = { ...parameters, [key]: value };
    setParameters(newParameters);
    setValue('parameters', newParameters);
  };

  const handleStrategyConfigChange = (config: StrategyConfig) => {
    hasUserEditedParamsRef.current = true;
    setParameters(config);
    setValue('parameters', config);
  };

  const onFormSubmit = async (data: ConfigurationFormData) => {
    await onSubmit({
      name: data.name,
      strategy_type: data.strategy_type,
      description: data.description,
      parameters: parameters,
    });
  };

  // Different steps for create vs edit mode
  const steps = isEditMode
    ? ['Parameters', 'Review']
    : ['Basic Information', 'Strategy Type', 'Parameters', 'Review'];

  const formatParameterLabel = (key: string): string => {
    const schemaLabel = strategySchema?.properties?.[key]?.title;

    if (schemaLabel) {
      return schemaLabel;
    }

    return key
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  const formatParameterValue = (value: unknown): string => {
    if (Array.isArray(value)) {
      return value.join(', ');
    }

    if (typeof value === 'boolean') {
      return value ? 'Yes' : 'No';
    }

    if (value === null || value === undefined || value === '') {
      return '-';
    }

    return String(value);
  };

  // Filter parameters to only show visible ones (respecting dependsOn conditions)
  const isParameterVisible = (key: string): boolean => {
    if (!strategySchema) return true;
    const fieldSchema = strategySchema.properties[key];
    if (!fieldSchema?.dependsOn) return true;

    const matchesSingleCondition = (cond: {
      field: string;
      values: string[];
      and?: Array<{ field: string; values: string[] }>;
    }): boolean => {
      const dependentRaw = parameters[cond.field];
      const dependentValue =
        dependentRaw === undefined || dependentRaw === null
          ? ''
          : String(dependentRaw);
      if (!cond.values.includes(dependentValue)) return false;
      if (!cond.and || cond.and.length === 0) return true;
      return cond.and.every((andCond) => {
        const rawCond = parameters[andCond.field];
        const valueCond =
          rawCond === undefined || rawCond === null ? '' : String(rawCond);
        return andCond.values.includes(valueCond);
      });
    };

    if (matchesSingleCondition(fieldSchema.dependsOn)) return true;
    if (!fieldSchema.dependsOn.or || fieldSchema.dependsOn.or.length === 0) {
      return false;
    }
    return fieldSchema.dependsOn.or.some((orCond) =>
      matchesSingleCondition(orCond)
    );
  };

  const reviewParameters: Array<[string, unknown]> = strategySchema
    ? [
        ...Object.keys(strategySchema.properties)
          .filter(isParameterVisible)
          .map((key) => [key, parameters[key]] as [string, unknown]),
        ...Object.entries(parameters).filter(
          ([key]) => !(key in strategySchema.properties)
        ),
      ]
    : Object.entries(parameters);

  return (
    <Box sx={{ width: '100%' }}>
      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {steps.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      <form onSubmit={handleSubmit(onFormSubmit)}>
        {/* Step 1: Basic Information (Create mode only) */}
        {!isEditMode && activeStep === 0 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Basic Information
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Provide a name and description for your strategy configuration
            </Typography>
            <Controller<ConfigurationFormData>
              name="name"
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label="Configuration Name"
                  placeholder="e.g., Conservative MA Crossover"
                  error={!!errors.name}
                  helperText={errors.name?.message}
                  sx={{ mb: 3 }}
                />
              )}
            />
            <Controller<ConfigurationFormData>
              name="description"
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label="Description (Optional)"
                  placeholder="Describe the purpose of this configuration"
                  multiline
                  rows={3}
                  error={!!errors.description}
                  helperText={errors.description?.message}
                />
              )}
            />
          </Box>
        )}

        {/* Step 2: Strategy Type (Create mode only) */}
        {!isEditMode && activeStep === 1 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Select Strategy Type
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Choose the trading strategy algorithm
            </Typography>

            {strategiesError && (
              <Alert severity="error" sx={{ mb: 2 }}>
                Failed to load strategies. Please try again.
              </Alert>
            )}

            <Controller<ConfigurationFormData>
              name="strategy_type"
              control={control}
              render={({ field }) => (
                <FormControl fullWidth error={!!errors.strategy_type}>
                  <InputLabel>Strategy Type</InputLabel>
                  <Select
                    {...field}
                    label="Strategy Type"
                    disabled={
                      !!initialData?.strategy_type || isStrategiesLoading
                    }
                  >
                    {isStrategiesLoading ? (
                      <MenuItem value="" disabled>
                        <Box
                          sx={{ display: 'flex', alignItems: 'center', gap: 2 }}
                        >
                          <CircularProgress size={16} />
                          <Typography variant="body2">
                            Loading strategies…
                          </Typography>
                        </Box>
                      </MenuItem>
                    ) : (
                      strategies.map((strategy) => (
                        <MenuItem key={strategy.id} value={strategy.id}>
                          <Box>
                            <Typography variant="body1">
                              {strategy.name}
                            </Typography>
                            {!!strategy.description && (
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                {strategy.description}
                              </Typography>
                            )}
                          </Box>
                        </MenuItem>
                      ))
                    )}
                  </Select>
                  {errors.strategy_type && (
                    <Typography variant="caption" color="error" sx={{ mt: 1 }}>
                      {errors.strategy_type.message}
                    </Typography>
                  )}
                  {initialData?.strategy_type && (
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ mt: 1, display: 'block' }}
                    >
                      Strategy type cannot be changed after creation
                    </Typography>
                  )}
                </FormControl>
              )}
            />

            {selectedStrategy && (
              <Alert severity="info" sx={{ mt: 3 }}>
                <Typography variant="subtitle2" gutterBottom>
                  {selectedStrategy.name}
                </Typography>
                <Typography variant="body2">
                  {selectedStrategy.description}
                </Typography>
              </Alert>
            )}
          </Box>
        )}

        {/* Step 3: Parameters (Create mode) or Step 1: Parameters (Edit mode) */}
        {((isEditMode && activeStep === 0) ||
          (!isEditMode && activeStep === 2)) && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Configure Parameters
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Set the parameters for your {selectedStrategy?.name || 'strategy'}
            </Typography>
            {strategySchema ? (
              <StrategyConfigForm
                configSchema={strategySchema}
                config={parameters}
                onChange={handleStrategyConfigChange}
                disabled={isLoading}
                showValidation
              />
            ) : (
              <>
                {Object.entries(parameters).map(([key, value]) => (
                  <TextField
                    key={key}
                    fullWidth
                    label={formatParameterLabel(key)}
                    value={value as string | number}
                    onChange={(e) => {
                      const newValue =
                        typeof value === 'number'
                          ? e.target.value === ''
                            ? ''
                            : Number(e.target.value)
                          : e.target.value;
                      handleParameterChange(key, newValue);
                    }}
                    type={typeof value === 'number' ? 'number' : 'text'}
                    sx={{ mb: 2 }}
                  />
                ))}

                {Object.keys(parameters).length === 0 && (
                  <Alert severity="warning">
                    No parameters available for this strategy type. Please
                    select a strategy type first.
                  </Alert>
                )}
              </>
            )}
          </Box>
        )}

        {/* Step 4: Review (Create mode) or Step 2: Review (Edit mode) */}
        {((isEditMode && activeStep === 1) ||
          (!isEditMode && activeStep === 3)) && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Review Configuration
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Review your configuration before saving
            </Typography>

            <Card variant="outlined" sx={{ mb: 2 }}>
              <CardContent>
                {!isEditMode && (
                  <>
                    <Typography
                      variant="subtitle2"
                      color="text.secondary"
                      gutterBottom
                    >
                      Name
                    </Typography>
                    <Typography variant="body1" sx={{ mb: 2 }}>
                      {watch('name')}
                    </Typography>

                    {watch('description') && (
                      <>
                        <Typography
                          variant="subtitle2"
                          color="text.secondary"
                          gutterBottom
                        >
                          Description
                        </Typography>
                        <Typography variant="body1" sx={{ mb: 2 }}>
                          {watch('description')}
                        </Typography>
                      </>
                    )}

                    <Typography
                      variant="subtitle2"
                      color="text.secondary"
                      gutterBottom
                    >
                      Strategy Type
                    </Typography>
                    <Typography variant="body1" sx={{ mb: 2 }}>
                      {selectedStrategy?.name}
                    </Typography>

                    <Divider sx={{ my: 2 }} />
                  </>
                )}

                {isEditMode && (
                  <>
                    <Typography
                      variant="subtitle2"
                      color="text.secondary"
                      gutterBottom
                    >
                      Configuration
                    </Typography>
                    <Typography variant="body1" sx={{ mb: 1 }}>
                      {watch('name')}
                    </Typography>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ mb: 2 }}
                    >
                      {selectedStrategy?.name}
                    </Typography>

                    <Divider sx={{ my: 2 }} />
                  </>
                )}

                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  gutterBottom
                >
                  Parameters
                </Typography>
                <Box sx={{ pl: 2 }}>
                  {reviewParameters.length === 0 ? (
                    <Typography variant="body2" color="text.secondary">
                      No parameters configured.
                    </Typography>
                  ) : (
                    reviewParameters.map(([key, value]) => (
                      <Box
                        key={key}
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          mb: 1,
                        }}
                      >
                        <Typography variant="body2" color="text.secondary">
                          {formatParameterLabel(key)}:
                        </Typography>
                        <Typography variant="body2" fontWeight={500}>
                          {formatParameterValue(value)}
                        </Typography>
                      </Box>
                    ))
                  )}
                </Box>
              </CardContent>
            </Card>
          </Box>
        )}

        {/* Navigation Buttons */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
          <Button type="button" onClick={onCancel} disabled={isLoading}>
            Cancel
          </Button>
          <Box sx={{ display: 'flex', gap: 2 }}>
            {activeStep > 0 && (
              <Button type="button" onClick={handleBack} disabled={isLoading}>
                Back
              </Button>
            )}
            {activeStep < steps.length - 1 ? (
              <Button
                type="button"
                variant="contained"
                onClick={handleNext}
                disabled={isLoading}
              >
                Next
              </Button>
            ) : (
              <Button
                type="submit"
                variant="contained"
                disabled={isLoading}
                startIcon={isLoading ? <CircularProgress size={20} /> : null}
              >
                {isLoading ? 'Saving...' : 'Save Configuration'}
              </Button>
            )}
          </Box>
        </Box>
      </form>
    </Box>
  );
};

export default ConfigurationForm;
