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
import type { StrategyConfigCreateData } from '../../types/configuration';
import type { StrategyConfig, ConfigSchema } from '../../types/strategy';

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

// Available strategy types with descriptions
// These must match the strategies registered in the backend
const STRATEGY_TYPES = [
  {
    value: 'floor',
    label: 'Floor Strategy',
    description: 'Dynamic retracement strategy with ATR-based volatility lock',
  },
  {
    value: 'rsi',
    label: 'RSI Strategy',
    description: 'Relative Strength Index with oversold/overbought signals',
  },
  {
    value: 'macd',
    label: 'MACD Strategy',
    description: 'MACD with signal line crossovers and histogram analysis',
  },
  {
    value: 'mean_reversion',
    label: 'Mean Reversion',
    description: 'Mean reversion using Bollinger Bands',
  },
  {
    value: 'scalping',
    label: 'Scalping Strategy',
    description: 'High-frequency scalping strategy',
  },
  {
    value: 'swing_trading',
    label: 'Swing Trading',
    description: 'Swing trading strategy for medium-term positions',
  },
  {
    value: 'stochastic',
    label: 'Stochastic Strategy',
    description: 'Stochastic oscillator strategy',
  },
];

const FLOOR_STRATEGY_SCHEMA: ConfigSchema = {
  type: 'object',
  title: 'Floor Strategy Configuration',
  description:
    'Configuration for the Floor Strategy with dynamic retracement and ATR-based volatility lock.',
  properties: {
    base_lot_size: {
      type: 'number',
      title: 'Base Lot Size',
      description: 'Initial lot size for first entry (e.g., 1.0 = 1000 units)',
      default: 1.0,
      minimum: 0.01,
    },
    scaling_mode: {
      type: 'string',
      title: 'Retracement Mode',
      description: 'Mode for retracement position size on retracements',
      enum: ['additive', 'multiplicative'],
      default: 'additive',
    },
    scaling_amount: {
      type: 'number',
      title: 'Retracement Amount',
      description:
        'Amount to add (additive) or multiply by (multiplicative) on each retracement',
      default: 1.0,
      minimum: 0.01,
    },
    retracement_pips: {
      type: 'number',
      title: 'Retracement Pips',
      description: 'Number of pips retracement required to trigger retracement',
      default: 30,
      minimum: 1,
    },
    take_profit_pips: {
      type: 'number',
      title: 'Take Profit Pips',
      description: 'Number of pips profit to trigger position close',
      default: 25,
      minimum: 1,
    },
    max_layers: {
      type: 'integer',
      title: 'Maximum Layers',
      description: 'Maximum number of concurrent layers',
      default: 3,
      minimum: 1,
    },
    max_retracements_per_layer: {
      type: 'integer',
      title: 'Max Retracements Per Layer',
      description:
        'Upper bound on how many retracement scale-ins a layer can perform before it must reset or close.',
      default: 10,
      minimum: 1,
    },
    volatility_lock_multiplier: {
      type: 'number',
      title: 'Volatility Lock Multiplier',
      description:
        'ATR multiplier to trigger volatility lock (e.g., 5.0 = 5x normal ATR)',
      default: 5.0,
      minimum: 1,
    },
    retracement_trigger_progression: {
      type: 'string',
      title: 'Retracement Trigger Progression',
      description: 'How retracement triggers progress across layers',
      enum: ['equal', 'additive', 'exponential', 'inverse'],
      default: 'additive',
    },
    retracement_trigger_increment: {
      type: 'number',
      title: 'Retracement Trigger Increment',
      description:
        'Value to add (additive) or multiply by (exponential). Not used for equal/inverse',
      default: 5,
      minimum: 0,
      dependsOn: {
        field: 'retracement_trigger_progression',
        values: ['additive', 'exponential'],
      },
    },
    lot_size_progression: {
      type: 'string',
      title: 'Lot Size Progression',
      description: 'How lot sizes progress across layers',
      enum: ['equal', 'additive', 'exponential', 'inverse'],
      default: 'additive',
    },
    lot_size_increment: {
      type: 'number',
      title: 'Lot Size Increment',
      description:
        'Value to add (additive) or multiply by (exponential). Not used for equal/inverse',
      default: 0.5,
      minimum: 0,
      dependsOn: {
        field: 'lot_size_progression',
        values: ['additive', 'exponential'],
      },
    },
    direction_method: {
      type: 'string',
      title: 'Direction Decision Method',
      description:
        'Technical analysis method to determine trade direction. Tick-based methods use raw tick data. OHLC methods aggregate ticks into candles for longer-term analysis.',
      enum: [
        'momentum',
        'sma_crossover',
        'ema_crossover',
        'price_vs_sma',
        'rsi',
        'ohlc_sma_crossover',
        'ohlc_ema_crossover',
        'ohlc_price_vs_sma',
      ],
      default: 'momentum',
    },
    entry_signal_lookback_ticks: {
      type: 'integer',
      title: 'Momentum Lookback Ticks',
      description:
        'Number of ticks to analyze for determining entry direction based on price momentum.',
      default: 10,
      minimum: 5,
      dependsOn: {
        field: 'direction_method',
        values: ['momentum'],
      },
    },
    sma_fast_period: {
      type: 'integer',
      title: 'SMA Fast Period',
      description: 'Period for fast Simple Moving Average (in ticks).',
      default: 10,
      minimum: 2,
      dependsOn: {
        field: 'direction_method',
        values: ['sma_crossover'],
      },
    },
    sma_slow_period: {
      type: 'integer',
      title: 'SMA Slow Period',
      description: 'Period for slow Simple Moving Average (in ticks).',
      default: 30,
      minimum: 5,
      dependsOn: {
        field: 'direction_method',
        values: ['sma_crossover', 'price_vs_sma'],
      },
    },
    ema_fast_period: {
      type: 'integer',
      title: 'EMA Fast Period',
      description: 'Period for fast Exponential Moving Average (in ticks).',
      default: 12,
      minimum: 2,
      dependsOn: {
        field: 'direction_method',
        values: ['ema_crossover'],
      },
    },
    ema_slow_period: {
      type: 'integer',
      title: 'EMA Slow Period',
      description: 'Period for slow Exponential Moving Average (in ticks).',
      default: 26,
      minimum: 5,
      dependsOn: {
        field: 'direction_method',
        values: ['ema_crossover'],
      },
    },
    rsi_period: {
      type: 'integer',
      title: 'RSI Period',
      description: 'Period for Relative Strength Index calculation (in ticks).',
      default: 14,
      minimum: 2,
      dependsOn: {
        field: 'direction_method',
        values: ['rsi'],
      },
    },
    rsi_overbought: {
      type: 'integer',
      title: 'RSI Overbought Level',
      description:
        'RSI level above which market is overbought (triggers short).',
      default: 70,
      minimum: 50,
      dependsOn: {
        field: 'direction_method',
        values: ['rsi'],
      },
    },
    rsi_oversold: {
      type: 'integer',
      title: 'RSI Oversold Level',
      description: 'RSI level below which market is oversold (triggers long).',
      default: 30,
      minimum: 0,
      dependsOn: {
        field: 'direction_method',
        values: ['rsi'],
      },
    },
    ohlc_granularity: {
      type: 'integer',
      title: 'OHLC Candle Granularity',
      description:
        'Candle period for OHLC methods. Values: 300=M5, 900=M15, 1800=M30, 3600=H1, 14400=H4, 86400=D1.',
      enum: [300, 900, 1800, 3600, 7200, 14400, 28800, 43200, 86400, 604800],
      default: 3600,
      dependsOn: {
        field: 'direction_method',
        values: [
          'ohlc_sma_crossover',
          'ohlc_ema_crossover',
          'ohlc_price_vs_sma',
        ],
      },
    },
    ohlc_fast_period: {
      type: 'integer',
      title: 'OHLC Fast MA Period',
      description:
        'Number of candles for fast moving average in OHLC crossover methods.',
      default: 10,
      minimum: 2,
      dependsOn: {
        field: 'direction_method',
        values: ['ohlc_sma_crossover', 'ohlc_ema_crossover'],
      },
    },
    ohlc_slow_period: {
      type: 'integer',
      title: 'OHLC Slow MA Period',
      description: 'Number of candles for slow moving average in OHLC methods.',
      default: 20,
      minimum: 5,
      dependsOn: {
        field: 'direction_method',
        values: [
          'ohlc_sma_crossover',
          'ohlc_ema_crossover',
          'ohlc_price_vs_sma',
        ],
      },
    },
  },
  required: [
    'base_lot_size',
    'scaling_mode',
    'retracement_pips',
    'take_profit_pips',
  ],
};

const STRATEGY_CONFIG_SCHEMAS: Record<string, ConfigSchema> = {
  floor: FLOOR_STRATEGY_SCHEMA,
};

// Default parameters for each strategy type
// These should match the required parameters in the backend strategy schemas
const DEFAULT_PARAMETERS: Record<string, Record<string, unknown>> = {
  floor: {
    base_lot_size: 1.0,
    scaling_mode: 'additive',
    scaling_amount: 1.0,
    retracement_pips: 30,
    take_profit_pips: 25,
    max_layers: 3,
    max_retracements_per_layer: 10,
    volatility_lock_multiplier: 5.0,
    retracement_trigger_progression: 'additive',
    retracement_trigger_increment: 5,
    lot_size_progression: 'additive',
    lot_size_increment: 0.5,
    entry_signal_lookback_ticks: 10,
    direction_method: 'momentum',
    sma_fast_period: 10,
    sma_slow_period: 30,
    ema_fast_period: 12,
    ema_slow_period: 26,
    rsi_period: 14,
    rsi_overbought: 70,
    rsi_oversold: 30,
    ohlc_granularity: 3600,
    ohlc_fast_period: 10,
    ohlc_slow_period: 20,
  },
  ma_crossover: {
    fast_period: 50,
    slow_period: 200,
    position_size: 1000,
    stop_loss_pips: 50,
    take_profit_pips: 100,
  },
  rsi: {
    period: 14,
    oversold: 30,
    overbought: 70,
    position_size: 1000,
  },
  macd: {
    fast_period: 12,
    slow_period: 26,
    signal_period: 9,
    position_size: 1000,
  },
  mean_reversion: {
    period: 20,
    std_dev: 2,
    position_size: 1000,
  },
  scalping: {
    position_size: 1000,
    stop_loss_pips: 10,
    take_profit_pips: 15,
  },
  swing_trading: {
    position_size: 1000,
    stop_loss_pips: 100,
    take_profit_pips: 200,
  },
  stochastic: {
    k_period: 14,
    d_period: 3,
    oversold: 20,
    overbought: 80,
    position_size: 1000,
  },
  arbitrage: {
    position_size: 1000,
    min_spread: 0.0001,
  },
};

const getDefaultParameters = (strategyType: string): StrategyConfig => {
  const schema = STRATEGY_CONFIG_SCHEMAS[strategyType];

  if (schema) {
    const defaults: StrategyConfig = {};

    Object.entries(schema.properties).forEach(([key, property]) => {
      if (property.default !== undefined) {
        defaults[key] = property.default;
      }
    });

    return defaults;
  }

  const fallback = DEFAULT_PARAMETERS[strategyType];
  return fallback ? { ...fallback } : {};
};

const ConfigurationForm = ({
  mode = 'create',
  initialData,
  onSubmit,
  onCancel,
  isLoading = false,
}: ConfigurationFormProps) => {
  const isEditMode = mode === 'edit';
  const initialStrategyType = initialData?.strategy_type || '';
  const initialParameters = useMemo<StrategyConfig>(() => {
    const defaults = initialStrategyType
      ? getDefaultParameters(initialStrategyType)
      : {};

    if (initialData?.parameters) {
      return {
        ...defaults,
        ...initialData.parameters,
      };
    }

    return defaults;
  }, [initialStrategyType, initialData]);

  const [activeStep, setActiveStep] = useState(0);
  const [parameters, setParameters] =
    useState<StrategyConfig>(initialParameters);

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

  const strategySchema = selectedStrategyType
    ? STRATEGY_CONFIG_SCHEMAS[selectedStrategyType]
    : undefined;

  const previousStrategyTypeRef = useRef<string>(initialStrategyType || '');
  const previousInitialDataRef =
    useRef<ConfigurationFormProps['initialData']>(initialData);

  // Update parameters when strategy type or initial data changes
  useEffect(() => {
    const currentType = selectedStrategyType || '';
    const previousType = previousStrategyTypeRef.current;
    const initialDataChanged = previousInitialDataRef.current !== initialData;

    if (!currentType) {
      if (previousType) {
        setParameters({});
        setValue('parameters', {});
      }
      previousStrategyTypeRef.current = currentType;
      previousInitialDataRef.current = initialData;
      return;
    }

    if (!initialDataChanged && currentType === previousType) {
      return;
    }

    const defaults = getDefaultParameters(currentType);
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
  }, [selectedStrategyType, initialData, setValue]);

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
    const newParameters: StrategyConfig = { ...parameters, [key]: value };
    setParameters(newParameters);
    setValue('parameters', newParameters);
  };

  const handleStrategyConfigChange = (config: StrategyConfig) => {
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

  const selectedStrategy = STRATEGY_TYPES.find(
    (s) => s.value === selectedStrategyType
  );

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
    const dependentValue = parameters[fieldSchema.dependsOn.field];
    return fieldSchema.dependsOn.values.includes(String(dependentValue));
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
            <Controller<ConfigurationFormData>
              name="strategy_type"
              control={control}
              render={({ field }) => (
                <FormControl fullWidth error={!!errors.strategy_type}>
                  <InputLabel>Strategy Type</InputLabel>
                  <Select
                    {...field}
                    label="Strategy Type"
                    disabled={!!initialData?.strategy_type}
                  >
                    {STRATEGY_TYPES.map((strategy) => (
                      <MenuItem key={strategy.value} value={strategy.value}>
                        <Box>
                          <Typography variant="body1">
                            {strategy.label}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {strategy.description}
                          </Typography>
                        </Box>
                      </MenuItem>
                    ))}
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
                  {selectedStrategy.label}
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
              Set the parameters for your{' '}
              {selectedStrategy?.label || 'strategy'}
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
                      {selectedStrategy?.label}
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
                      {selectedStrategy?.label}
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
