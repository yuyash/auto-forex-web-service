import { useState, useEffect } from 'react';
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
import type { StrategyConfigCreateData } from '../../types/configuration';

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
  initialData?: Partial<ConfigurationFormData>;
  onSubmit: (data: StrategyConfigCreateData) => Promise<void>;
  onCancel: () => void;
  isLoading?: boolean;
}

// Available strategy types with descriptions
const STRATEGY_TYPES = [
  {
    value: 'floor',
    label: 'Floor Strategy',
    description: 'Dynamic scaling strategy with ATR-based volatility lock',
  },
  {
    value: 'ma_crossover',
    label: 'MA Crossover',
    description: 'Moving average crossover strategy',
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
    value: 'trend_following',
    label: 'Trend Following',
    description: 'Trend following strategy with multiple indicators',
  },
  {
    value: 'mean_reversion',
    label: 'Mean Reversion',
    description: 'Mean reversion using Bollinger Bands',
  },
  {
    value: 'breakout',
    label: 'Breakout Strategy',
    description: 'Price breakout strategy',
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
    value: 'london_breakout',
    label: 'London Breakout',
    description: 'London session breakout strategy',
  },
  {
    value: 'asian_range',
    label: 'Asian Range',
    description: 'Asian session range trading strategy',
  },
  {
    value: 'news_spike',
    label: 'News Spike',
    description: 'News event spike trading strategy',
  },
  {
    value: 'stochastic',
    label: 'Stochastic Strategy',
    description: 'Stochastic oscillator strategy',
  },
];

// Default parameters for each strategy type
const DEFAULT_PARAMETERS: Record<string, Record<string, unknown>> = {
  floor: {
    position_size: 1000,
    stop_loss_pips: 50,
    take_profit_pips: 100,
    enable_position_differentiation: false,
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
    stop_loss_pips: 50,
    take_profit_pips: 100,
  },
  macd: {
    fast_period: 12,
    slow_period: 26,
    signal_period: 9,
    position_size: 1000,
    stop_loss_pips: 50,
    take_profit_pips: 100,
  },
  trend_following: {
    position_size: 1000,
    stop_loss_pips: 50,
    take_profit_pips: 100,
  },
  mean_reversion: {
    period: 20,
    std_dev: 2,
    position_size: 1000,
    stop_loss_pips: 50,
    take_profit_pips: 100,
  },
  breakout: {
    position_size: 1000,
    stop_loss_pips: 50,
    take_profit_pips: 100,
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
  london_breakout: {
    position_size: 1000,
    stop_loss_pips: 50,
    take_profit_pips: 100,
  },
  asian_range: {
    position_size: 1000,
    stop_loss_pips: 50,
    take_profit_pips: 100,
  },
  news_spike: {
    position_size: 1000,
    stop_loss_pips: 50,
    take_profit_pips: 100,
  },
  stochastic: {
    k_period: 14,
    d_period: 3,
    oversold: 20,
    overbought: 80,
    position_size: 1000,
    stop_loss_pips: 50,
    take_profit_pips: 100,
  },
};

const ConfigurationForm = ({
  initialData,
  onSubmit,
  onCancel,
  isLoading = false,
}: ConfigurationFormProps) => {
  const [activeStep, setActiveStep] = useState(0);
  const [parameters, setParameters] = useState<Record<string, unknown>>(
    initialData?.parameters || {}
  );

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
      strategy_type: initialData?.strategy_type || '',
      description: initialData?.description || '',
      parameters: initialData?.parameters || {},
    },
  });

  // Watch strategy_type for reactivity
  // eslint-disable-next-line react-hooks/incompatible-library
  const selectedStrategyType = watch('strategy_type');

  // Update parameters when strategy type changes
  useEffect(() => {
    if (selectedStrategyType && !initialData) {
      const defaultParams = DEFAULT_PARAMETERS[selectedStrategyType] || {};
      setParameters(defaultParams);
      setValue('parameters', defaultParams);
    }
  }, [selectedStrategyType, initialData, setValue]);

  const handleNext = () => {
    setActiveStep((prev) => prev + 1);
  };

  const handleBack = () => {
    setActiveStep((prev) => prev - 1);
  };

  const handleParameterChange = (key: string, value: unknown) => {
    const newParameters = { ...parameters, [key]: value };
    setParameters(newParameters);
    setValue('parameters', newParameters);
  };

  const onFormSubmit = async (data: ConfigurationFormData) => {
    await onSubmit({
      name: data.name,
      strategy_type: data.strategy_type,
      description: data.description,
      parameters: parameters,
    });
  };

  const steps = ['Basic Information', 'Strategy Type', 'Parameters', 'Review'];

  const selectedStrategy = STRATEGY_TYPES.find(
    (s) => s.value === selectedStrategyType
  );

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
        {/* Step 1: Basic Information */}
        {activeStep === 0 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Basic Information
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Provide a name and description for your strategy configuration
            </Typography>

            <Controller
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

            <Controller
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

        {/* Step 2: Strategy Type */}
        {activeStep === 1 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Select Strategy Type
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Choose the trading strategy algorithm
            </Typography>

            <Controller
              name="strategy_type"
              control={control}
              render={({ field }) => (
                <FormControl fullWidth error={!!errors.strategy_type}>
                  <InputLabel>Strategy Type</InputLabel>
                  <Select {...field} label="Strategy Type">
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

        {/* Step 3: Parameters */}
        {activeStep === 2 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Configure Parameters
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Set the parameters for your{' '}
              {selectedStrategy?.label || 'strategy'}
            </Typography>

            {Object.entries(parameters).map(([key, value]) => (
              <TextField
                key={key}
                fullWidth
                label={key
                  .replace(/_/g, ' ')
                  .replace(/\b\w/g, (l) => l.toUpperCase())}
                value={value as string | number}
                onChange={(e) => {
                  const newValue =
                    typeof value === 'number'
                      ? Number(e.target.value)
                      : e.target.value;
                  handleParameterChange(key, newValue);
                }}
                type={typeof value === 'number' ? 'number' : 'text'}
                sx={{ mb: 2 }}
              />
            ))}

            {Object.keys(parameters).length === 0 && (
              <Alert severity="warning">
                No parameters available for this strategy type. Please select a
                strategy type first.
              </Alert>
            )}
          </Box>
        )}

        {/* Step 4: Review */}
        {activeStep === 3 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Review Configuration
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Review your configuration before saving
            </Typography>

            <Card variant="outlined" sx={{ mb: 2 }}>
              <CardContent>
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

                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  gutterBottom
                >
                  Parameters
                </Typography>
                <Box sx={{ pl: 2 }}>
                  {Object.entries(parameters).map(([key, value]) => (
                    <Box
                      key={key}
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        mb: 1,
                      }}
                    >
                      <Typography variant="body2" color="text.secondary">
                        {key
                          .replace(/_/g, ' ')
                          .replace(/\b\w/g, (l) => l.toUpperCase())}
                        :
                      </Typography>
                      <Typography variant="body2" fontWeight={500}>
                        {String(value)}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              </CardContent>
            </Card>
          </Box>
        )}

        {/* Navigation Buttons */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
          <Button onClick={onCancel} disabled={isLoading}>
            Cancel
          </Button>
          <Box sx={{ display: 'flex', gap: 2 }}>
            {activeStep > 0 && (
              <Button onClick={handleBack} disabled={isLoading}>
                Back
              </Button>
            )}
            {activeStep < steps.length - 1 ? (
              <Button
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
