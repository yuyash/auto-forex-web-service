import { useState, useEffect, useRef, useMemo } from 'react';

import {
  Box,
  Stepper,
  Step,
  StepLabel,
  Button,
  Typography,
  Paper,
  TextField,
  Alert,
  FormControlLabel,
  Checkbox,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  FormHelperText,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { useNavigate } from 'react-router-dom';
import { useForm, Controller, type Resolver } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { ConfigurationSelector } from '../tasks/forms/ConfigurationSelector';
import { DateRangePicker } from '../tasks/forms/DateRangePicker';
import { BalanceInput } from '../tasks/forms/BalanceInput';
import {
  backtestTaskSchema,
  type BacktestTaskSchemaOutput,
} from '../tasks/forms/validationSchemas';
import { type BacktestTaskCreateData } from '../../types/backtestTask';
import { DataSource } from '../../types/common';
import {
  useCreateBacktestTask,
  useUpdateBacktestTask,
} from '../../hooks/useBacktestTaskMutations';
import {
  useConfiguration,
  useConfigurations,
} from '../../hooks/useConfigurations';
import { invalidateBacktestTasksCache } from '../../hooks/useBacktestTasks';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';

const steps = ['Configuration', 'Parameters', 'Review'];
const DEFAULT_DATE_RANGE_DAYS = 30;

const createDefaultDateRange = () => {
  const end = new Date();
  const start = new Date(
    end.getTime() - DEFAULT_DATE_RANGE_DAYS * 24 * 60 * 60 * 1000
  );
  return {
    start_time: start.toISOString(),
    end_time: end.toISOString(),
  };
};

interface BacktestTaskFormProps {
  taskId?: string;
  initialData?: Partial<BacktestTaskSchemaOutput>;
}

// Separate component to avoid infinite loop with watch()
interface ReviewContentProps {
  selectedConfig: {
    name: string;
    id: string;
    description?: string;
    parameters?: Record<string, unknown>;
  };
  formValues: {
    config_id: string;
    name: string;
    description?: string;
    data_source: DataSource;
    start_time: string;
    end_time: string;
    initial_balance: number;
    commission_per_trade: number;
    pip_size?: number;
    instrument: string;
    trading_mode?: 'netting' | 'hedging';
    sell_at_completion?: boolean;
  };
}

function ReviewContent({ selectedConfig, formValues }: ReviewContentProps) {
  const {
    name,
    description,
    start_time,
    end_time,
    initial_balance,
    commission_per_trade,
    pip_size,
    instrument,
    trading_mode,
    sell_at_completion,
  } = formValues;

  return (
    <Grid container spacing={2}>
      <Grid size={{ xs: 12 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Task Name
        </Typography>
        <Typography variant="body1">{name}</Typography>
      </Grid>

      {description && (
        <Grid size={{ xs: 12 }}>
          <Typography variant="subtitle2" color="text.secondary">
            Description
          </Typography>
          <Typography variant="body1">{description}</Typography>
        </Grid>
      )}

      <Grid size={{ xs: 12 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Configuration
        </Typography>
        <Typography variant="body1">{selectedConfig.name}</Typography>
        {selectedConfig.description && (
          <Typography variant="body2" color="text.secondary">
            {selectedConfig.description}
          </Typography>
        )}
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Data Source
        </Typography>
        <Typography variant="body1">PostgreSQL</Typography>
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Date Range
        </Typography>
        <Typography variant="body1">
          {new Date(start_time).toLocaleDateString()} -{' '}
          {new Date(end_time).toLocaleDateString()}
        </Typography>
      </Grid>

      <Grid size={{ xs: 12 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Instrument
        </Typography>
        <Typography variant="body1">{instrument}</Typography>
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Trading Mode
        </Typography>
        <Typography variant="body1">
          {trading_mode === 'hedging'
            ? 'Hedging Mode (Independent Trades)'
            : 'Netting Mode (Aggregated Positions)'}
        </Typography>
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Initial Balance
        </Typography>
        <Typography variant="body1">
          {new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
          }).format(Number(initial_balance))}
        </Typography>
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Commission Per Trade
        </Typography>
        <Typography variant="body1">
          {new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
          }).format(Number(commission_per_trade))}
        </Typography>
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Pip Size
        </Typography>
        <Typography variant="body1">
          {pip_size !== undefined && pip_size !== null
            ? pip_size
            : 'Auto (derived from instrument)'}
        </Typography>
      </Grid>

      <Grid size={{ xs: 12 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Close Positions at Completion
        </Typography>
        <Typography variant="body1">
          {sell_at_completion ? 'Yes' : 'No'}
        </Typography>
      </Grid>
    </Grid>
  );
}

export default function BacktestTaskForm({
  taskId,
  initialData,
}: BacktestTaskFormProps) {
  const navigate = useNavigate();
  const defaultDateRange = useMemo(() => {
    const range = createDefaultDateRange();
    return {
      start_time: initialData?.start_time || range.start_time,
      end_time: initialData?.end_time || range.end_time,
    };
  }, [initialData?.start_time, initialData?.end_time]);

  const resolvedDefaultValues = useMemo(() => {
    const baseDefaults: BacktestTaskSchemaOutput = {
      config_id: '',
      name: '',
      description: '',
      data_source: DataSource.POSTGRESQL,
      start_time: defaultDateRange.start_time,
      end_time: defaultDateRange.end_time,
      initial_balance: 10000,
      commission_per_trade: 0,
      pip_size: undefined,
      instrument: 'USD_JPY',
      trading_mode: 'netting' as const,
      sell_at_completion: false,
    };

    return {
      ...baseDefaults,
      ...initialData,
      start_time: initialData?.start_time || baseDefaults.start_time,
      end_time: initialData?.end_time || baseDefaults.end_time,
    } as BacktestTaskSchemaOutput;
  }, [defaultDateRange.end_time, defaultDateRange.start_time, initialData]);

  const [activeStep, setActiveStep] = useState(0);
  const [formData, setFormData] = useState<Partial<BacktestTaskSchemaOutput>>(
    initialData || {}
  );
  const canSubmitRef = useRef(false); // Flag to prevent auto-submission
  const createTask = useCreateBacktestTask();
  const updateTask = useUpdateBacktestTask();

  const {
    control,
    handleSubmit,
    watch,
    getValues,
    setValue,
    formState: { errors },
    trigger,
  } = useForm<BacktestTaskSchemaOutput>({
    resolver: zodResolver(
      backtestTaskSchema
    ) as Resolver<BacktestTaskSchemaOutput>,
    mode: 'onChange',
    reValidateMode: 'onChange',
    shouldUnregister: false,
    defaultValues: resolvedDefaultValues,
  });

  // eslint-disable-next-line react-hooks/incompatible-library
  const selectedConfigId = watch('config_id');

  // Sync saved formData back into React Hook Form when changing steps
  // This ensures form values persist when navigating between steps
  useEffect(() => {
    if (Object.keys(formData).length > 0) {
      // Manually set each field value to restore saved state
      Object.entries(formData).forEach(([key, value]) => {
        if (value !== undefined) {
          setValue(key as keyof BacktestTaskSchemaOutput, value, {
            shouldValidate: false,
          });
        }
      });
    }
  }, [formData, setValue]); // Removed activeStep dependency so it runs on initial render too

  // Fetch all configurations and strategies
  const { data: configurationsData } = useConfigurations({ page_size: 100 });
  const configurations = configurationsData?.results || [];
  const { strategies } = useStrategies();

  // config_id is now a UUID string
  const configIdString = selectedConfigId || '';

  const { data: selectedConfig } = useConfiguration(configIdString);

  const handleNext = async () => {
    // Save current form values to state BEFORE validation
    const currentValues = getValues();
    setFormData((prev) => ({ ...prev, ...currentValues }));

    // Validate current step before proceeding
    let fieldsToValidate: (keyof BacktestTaskSchemaOutput)[] = [];

    switch (activeStep) {
      case 0: // Configuration step
        fieldsToValidate = ['config_id', 'name'];
        break;
      case 1: // Parameters step
        fieldsToValidate = ['start_time', 'end_time', 'initial_balance'];
        break;
      default:
        // No validation needed for review step
        break;
    }

    // Only validate if we have fields to validate
    if (fieldsToValidate.length > 0) {
      const isValid = await trigger(fieldsToValidate);

      if (!isValid) {
        // Validation failed, don't proceed
        return;
      }
    }

    // Validation passed or no validation needed, proceed to next step
    canSubmitRef.current = false; // Reset submit flag when navigating
    setActiveStep((prevActiveStep) => prevActiveStep + 1);
  };

  const handleBack = () => {
    // Save current form values to state before going back
    const currentValues = getValues();
    setFormData((prev) => ({ ...prev, ...currentValues }));

    canSubmitRef.current = false; // Reset submit flag when navigating
    setActiveStep((prevActiveStep) => prevActiveStep - 1);
  };

  const onSubmit = async (data: BacktestTaskSchemaOutput) => {
    // Prevent auto-submission - only allow explicit user submission
    if (!canSubmitRef.current) {
      return;
    }

    // Merge the saved formData with the current form data to ensure we have all values
    const completeData = { ...formData, ...data } as BacktestTaskSchemaOutput;

    // Zod has already validated and converted types, so we can use the data directly
    const apiData: BacktestTaskCreateData = {
      config: completeData.config_id,
      name: completeData.name,
      description: completeData.description,
      data_source: DataSource.POSTGRESQL,
      start_time: completeData.start_time,
      end_time: completeData.end_time,
      initial_balance: completeData.initial_balance,
      commission_per_trade: completeData.commission_per_trade,
      ...(completeData.pip_size != null && { pip_size: completeData.pip_size }),
      instrument: completeData.instrument,
      sell_at_completion: completeData.sell_at_completion,
    };

    try {
      if (taskId) {
        await updateTask.mutate({ id: taskId, data: apiData });
      } else {
        await createTask.mutate(apiData);
      }

      // Invalidate cache so the task list refreshes
      invalidateBacktestTasksCache();

      navigate('/backtest-tasks');
    } catch (error: unknown) {
      const err = error as {
        details?: Record<string, string | string[]>;
        message?: string;
      };

      // Extract backend validation errors if available
      let errorMessage = 'Failed to create task';
      if (err?.details && typeof err.details === 'object') {
        const backendErrors = err.details as Record<string, string | string[]>;
        const errorMessages: string[] = [];

        // Map backend field names to frontend field names
        const fieldMapping: Record<string, string> = {
          config: 'Configuration',
          name: 'Task Name',
          start_time: 'Start Date',
          end_time: 'End Date',
          initial_balance: 'Initial Balance',
        };

        Object.entries(backendErrors).forEach(([field, messages]) => {
          const fieldName = fieldMapping[field] || field;
          const fieldErrors = Array.isArray(messages) ? messages : [messages];
          fieldErrors.forEach((msg: string) => {
            errorMessages.push(`${fieldName}: ${msg}`);
          });
        });

        if (errorMessages.length > 0) {
          errorMessage = errorMessages.join('\n');
        }
      } else if (err?.message) {
        errorMessage = err.message;
      }

      alert(errorMessage);
    }
  };

  const getStepContent = (step: number) => {
    switch (step) {
      case 0:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Select Configuration
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Choose a strategy configuration for this backtest task
            </Typography>

            <Grid container spacing={3}>
              <Grid size={{ xs: 12 }}>
                <Controller
                  name="config_id"
                  control={control}
                  render={({ field }) => (
                    <ConfigurationSelector
                      configurations={configurations}
                      value={field.value as string | undefined}
                      onChange={field.onChange}
                      error={errors.config_id?.message}
                      helperText={errors.config_id?.message}
                      required
                    />
                  )}
                />
              </Grid>

              {selectedConfig && (
                <Grid size={{ xs: 12 }}>
                  <Alert severity="info">
                    <Typography variant="subtitle2" gutterBottom>
                      Configuration Preview
                    </Typography>
                    <Typography variant="body2">
                      <strong>Type:</strong>{' '}
                      {getStrategyDisplayName(
                        strategies,
                        selectedConfig.strategy_type
                      )}
                    </Typography>
                    <Typography variant="body2">
                      <strong>Description:</strong>{' '}
                      {selectedConfig.description || 'No description'}
                    </Typography>
                  </Alert>
                </Grid>
              )}

              <Grid size={{ xs: 12 }}>
                <Controller
                  name="name"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      fullWidth
                      label="Task Name"
                      required
                      error={!!errors.name}
                      helperText={errors.name?.message}
                    />
                  )}
                />
              </Grid>

              <Grid size={{ xs: 12 }}>
                <Controller
                  name="description"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      fullWidth
                      label="Description"
                      multiline
                      rows={3}
                      error={!!errors.description}
                      helperText={errors.description?.message}
                    />
                  )}
                />
              </Grid>
            </Grid>
          </Box>
        );

      case 1:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Backtest Parameters
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Configure the backtest time range, instrument, and initial
              settings
            </Typography>

            <Grid container spacing={3}>
              <Grid size={{ xs: 12 }}>
                <Controller
                  name="start_time"
                  control={control}
                  render={({ field: startField }) => (
                    <Controller
                      name="end_time"
                      control={control}
                      render={({ field: endField }) => (
                        <DateRangePicker
                          startDate={startField.value}
                          endDate={endField.value}
                          onStartDateChange={startField.onChange}
                          onEndDateChange={endField.onChange}
                          maxDate={new Date()}
                          required
                          helperText="Backtesting requires historical data. Future dates are not allowed."
                        />
                      )}
                    />
                  )}
                />
              </Grid>

              <Grid size={{ xs: 12, md: 6 }}>
                <Controller
                  name="initial_balance"
                  control={control}
                  render={({ field }) => (
                    <BalanceInput
                      value={field.value}
                      onChange={field.onChange}
                      label="Initial Balance"
                      currency="USD"
                      error={errors.initial_balance?.message}
                      helperText={errors.initial_balance?.message}
                    />
                  )}
                />
              </Grid>

              <Grid size={{ xs: 12, md: 6 }}>
                <Controller
                  name="commission_per_trade"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      fullWidth
                      label="Commission Per Trade"
                      type="number"
                      inputProps={{ min: 0, step: 0.01 }}
                      error={!!errors.commission_per_trade}
                      helperText={errors.commission_per_trade?.message}
                    />
                  )}
                />
              </Grid>

              <Grid size={{ xs: 12, md: 6 }}>
                <Controller
                  name="instrument"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      fullWidth
                      label="Instrument"
                      placeholder="e.g., EUR_USD, USD_JPY"
                      error={!!errors.instrument}
                      helperText={
                        errors.instrument?.message || 'Trading pair to backtest'
                      }
                    />
                  )}
                />
              </Grid>

              <Grid size={{ xs: 12, md: 6 }}>
                <Controller
                  name="pip_size"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      value={field.value ?? ''}
                      onChange={(e) => {
                        const val = e.target.value;
                        field.onChange(val === '' ? undefined : Number(val));
                      }}
                      fullWidth
                      label="Pip Size (Optional)"
                      type="number"
                      inputProps={{ min: 0, step: 0.00001 }}
                      error={!!errors.pip_size}
                      helperText={
                        errors.pip_size?.message ||
                        'Leave empty to auto-derive from instrument. Common values: 0.0001 (EUR_USD), 0.01 (USD_JPY)'
                      }
                    />
                  )}
                />
              </Grid>

              <Grid size={{ xs: 12, md: 6 }}>
                <Controller
                  name="trading_mode"
                  control={control}
                  render={({ field }) => (
                    <FormControl fullWidth error={!!errors.trading_mode}>
                      <InputLabel>Trading Mode</InputLabel>
                      <Select {...field} label="Trading Mode">
                        <MenuItem value="netting">
                          Netting Mode (Aggregated Positions)
                        </MenuItem>
                        <MenuItem value="hedging">
                          Hedging Mode (Independent Trades)
                        </MenuItem>
                      </Select>
                      <FormHelperText>
                        {errors.trading_mode?.message ||
                          'Netting: positions aggregated per instrument (FIFO). Hedging: multiple independent trades per instrument.'}
                      </FormHelperText>
                    </FormControl>
                  )}
                />
              </Grid>

              <Grid size={{ xs: 12 }}>
                <Controller
                  name="sell_at_completion"
                  control={control}
                  render={({ field }) => (
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={field.value || false}
                          onChange={(e) => field.onChange(e.target.checked)}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body1">
                            Close all positions at backtest completion
                          </Typography>
                          <Typography
                            variant="body2"
                            color="text.secondary"
                            sx={{ mt: 0.5 }}
                          >
                            When enabled, all open positions will be
                            automatically closed at the final market price when
                            the backtest finishes. This provides realistic P&L
                            calculations. When disabled, positions remain open
                            for analysis.
                          </Typography>
                        </Box>
                      }
                    />
                  )}
                />
              </Grid>
            </Grid>
          </Box>
        );

      case 2: {
        // Use the saved formData state which contains all values from all steps
        const formValues = {
          config_id: formData.config_id as string,
          name: formData.name as string,
          description: formData.description,
          data_source: formData.data_source as DataSource,
          start_time: formData.start_time as string,
          end_time: formData.end_time as string,
          initial_balance: formData.initial_balance as number,
          commission_per_trade: formData.commission_per_trade as number,
          pip_size: formData.pip_size as number | undefined,
          instrument: formData.instrument as string,
          trading_mode: formData.trading_mode as
            | 'netting'
            | 'hedging'
            | undefined,
          sell_at_completion: formData.sell_at_completion as boolean,
        };

        // Field name mapping for user-friendly error messages
        const fieldNameMapping: Record<string, string> = {
          config_id: 'Configuration',
          name: 'Task Name',
          description: 'Description',
          data_source: 'Data Source',
          start_time: 'Start Date',
          end_time: 'End Date',
          initial_balance: 'Initial Balance',
          commission_per_trade: 'Commission Per Trade',
          pip_size: 'Pip Size',
          instrument: 'Instrument',
        };

        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Review & Submit
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Review your backtest task configuration before submitting
            </Typography>

            {/* Show validation errors on review step */}
            {Object.keys(errors).length > 0 && (
              <Alert severity="error" sx={{ mb: 3 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Please fix the following errors before submitting:
                </Typography>
                {Object.entries(errors).map(([field, error]) => {
                  const errorObj = error as { message?: string };
                  const errorMessage =
                    typeof error === 'object' && error !== null
                      ? errorObj.message || JSON.stringify(error)
                      : String(error);

                  // Use friendly field name from mapping
                  const friendlyFieldName =
                    fieldNameMapping[field] ||
                    field
                      .replace(/_/g, ' ')
                      .replace(/\b\w/g, (l) => l.toUpperCase());

                  return (
                    <Typography key={field} variant="body2">
                      • <strong>{friendlyFieldName}:</strong> {errorMessage}
                    </Typography>
                  );
                })}
                <Typography variant="body2" sx={{ mt: 1, fontStyle: 'italic' }}>
                  Click "Back" to return to previous steps and correct these
                  errors.
                </Typography>
              </Alert>
            )}

            <Paper sx={{ p: 3 }}>
              {selectedConfig ? (
                <ReviewContent
                  selectedConfig={selectedConfig}
                  formValues={formValues}
                />
              ) : (
                <Alert severity="error">
                  Configuration not found. Please go back and select a valid
                  configuration.
                </Alert>
              )}
            </Paper>
          </Box>
        );
      }

      default:
        return 'Unknown step';
    }
  };

  return (
    <Box>
      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {steps.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      <form onSubmit={handleSubmit(onSubmit)}>
        {getStepContent(activeStep)}

        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
          <Button
            disabled={activeStep === 0}
            onClick={handleBack}
            variant="outlined"
          >
            Back
          </Button>

          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="outlined"
              onClick={() => navigate('/backtest-tasks')}
            >
              Cancel
            </Button>

            {activeStep === steps.length - 1 ? (
              <Button
                type="submit"
                variant="contained"
                disabled={createTask.isLoading || updateTask.isLoading}
                onClick={() => {
                  canSubmitRef.current = true;
                }}
              >
                {taskId ? 'Update Task' : 'Create Task'}
              </Button>
            ) : (
              <Button variant="contained" onClick={handleNext}>
                Next
              </Button>
            )}
          </Box>
        </Box>
      </form>
    </Box>
  );
}
