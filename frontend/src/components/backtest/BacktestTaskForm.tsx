import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';

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
import {
  fetchTickDataRange,
  type TickDataRange,
} from '../../services/api/market';

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
    sell_at_completion?: boolean;
    hedging_enabled?: boolean;
  };
}

function ReviewContent({ selectedConfig, formValues }: ReviewContentProps) {
  const { t } = useTranslation(['backtest', 'common']);
  const {
    name,
    description,
    start_time,
    end_time,
    initial_balance,
    commission_per_trade,
    pip_size,
    instrument,
    sell_at_completion,
  } = formValues;

  return (
    <Grid container spacing={2}>
      <Grid size={{ xs: 12 }}>
        <Typography variant="subtitle2" color="text.secondary">
          {t('backtest:form.taskName')}
        </Typography>
        <Typography variant="body1">{name}</Typography>
      </Grid>

      {description && (
        <Grid size={{ xs: 12 }}>
          <Typography variant="subtitle2" color="text.secondary">
            {t('common:labels.description')}
          </Typography>
          <Typography variant="body1">{description}</Typography>
        </Grid>
      )}

      <Grid size={{ xs: 12 }}>
        <Typography variant="subtitle2" color="text.secondary">
          {t('common:labels.configuration')}
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
          {t('backtest:detail.dataSource')}
        </Typography>
        <Typography variant="body1">PostgreSQL</Typography>
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <Typography variant="subtitle2" color="text.secondary">
          {t('backtest:config.dateRange')}
        </Typography>
        <Typography variant="body1">
          {new Date(start_time).toLocaleDateString()} -{' '}
          {new Date(end_time).toLocaleDateString()}
        </Typography>
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <Typography variant="subtitle2" color="text.secondary">
          {t('common:labels.instrument')}
        </Typography>
        <Typography variant="body1">{instrument}</Typography>
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <Typography variant="subtitle2" color="text.secondary">
          {t('backtest:detail.initialBalance')}
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
          {t('backtest:detail.commissionPerTrade')}
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
          {t('common:labels.pipSize')}
        </Typography>
        <Typography variant="body1">
          {pip_size !== undefined && pip_size !== null
            ? pip_size
            : t('backtest:form.pipSizeHelperText')}
        </Typography>
      </Grid>

      <Grid size={{ xs: 12 }}>
        <Typography variant="subtitle2" color="text.secondary">
          {t('backtest:form.closePositionsAtCompletion')}
        </Typography>
        <Typography variant="body1">
          {sell_at_completion ? t('common:labels.yes') : t('common:labels.no')}
        </Typography>
      </Grid>

      <Grid size={{ xs: 12 }}>
        <Typography variant="subtitle2" color="text.secondary">
          {t('backtest:form.hedgingEnabled')}
        </Typography>
        <Typography variant="body1">
          {formValues.hedging_enabled !== false
            ? t('common:labels.yes')
            : t('common:labels.no')}
        </Typography>
      </Grid>
    </Grid>
  );
}

export default function BacktestTaskForm({
  taskId,
  initialData,
}: BacktestTaskFormProps) {
  const { t } = useTranslation(['backtest', 'common']);
  const navigate = useNavigate();
  const steps = [
    t('backtest:form.steps.configuration'),
    t('backtest:form.steps.parameters'),
    t('backtest:form.steps.review'),
  ];
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
      pip_size: 0.01,
      instrument: 'USD_JPY',
      sell_at_completion: false,
      hedging_enabled: true,
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

  // Tick data availability state
  const [dataRange, setDataRange] = useState<TickDataRange | null>(null);
  const [dataRangeError, setDataRangeError] = useState<string | null>(null);
  const [dataRangeLoading, setDataRangeLoading] = useState(false);

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

  // Fetch tick data range when instrument changes
  const checkDataRange = useCallback(async (instrument: string) => {
    if (!instrument) {
      setDataRange(null);
      setDataRangeError(null);
      return;
    }
    setDataRangeLoading(true);
    setDataRangeError(null);
    try {
      const range = await fetchTickDataRange(instrument);
      setDataRange(range);
    } catch {
      setDataRangeError('Failed to fetch tick data range');
      setDataRange(null);
    } finally {
      setDataRangeLoading(false);
    }
  }, []);

  const watchedInstrument = watch('instrument');
  const watchedStartTime = watch('start_time');
  const watchedEndTime = watch('end_time');

  useEffect(() => {
    checkDataRange(watchedInstrument);
  }, [watchedInstrument, checkDataRange]);

  // Compute data coverage warning
  const dataCoverageWarning = useMemo<string | null>(() => {
    if (!dataRange || !dataRange.has_data) {
      if (dataRange && !dataRange.has_data && watchedInstrument) {
        return `No tick data found for ${watchedInstrument} in the database.`;
      }
      return null;
    }
    const warnings: string[] = [];
    if (watchedStartTime && dataRange.min_timestamp) {
      const start = new Date(watchedStartTime);
      const minTs = new Date(dataRange.min_timestamp);
      if (start < minTs) {
        warnings.push(
          `Start time is before the earliest data timestamp (${minTs.toLocaleString()}).`
        );
      }
    }
    if (watchedEndTime && dataRange.max_timestamp) {
      const end = new Date(watchedEndTime);
      const maxTs = new Date(dataRange.max_timestamp);
      if (end > maxTs) {
        warnings.push(
          `End time is after the latest data timestamp (${maxTs.toLocaleString()}).`
        );
      }
    }
    return warnings.length > 0 ? warnings.join(' ') : null;
  }, [dataRange, watchedInstrument, watchedStartTime, watchedEndTime]);

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

    // Block proceeding from Parameters step if data coverage is insufficient
    if (activeStep === 1 && dataCoverageWarning) {
      return;
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
      hedging_enabled: completeData.hedging_enabled,
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
              {t('backtest:form.selectConfiguration')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {t('backtest:form.chooseStrategyConfig')}
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
                      {t('trading:form.configurationPreview')}
                    </Typography>
                    <Typography variant="body2">
                      <strong>{t('trading:form.type')}:</strong>{' '}
                      {getStrategyDisplayName(
                        strategies,
                        selectedConfig.strategy_type
                      )}
                    </Typography>
                    <Typography variant="body2">
                      <strong>{t('common:labels.description')}:</strong>{' '}
                      {selectedConfig.description ||
                        t('trading:form.noDescription')}
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
                      label={t('backtest:form.taskName')}
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
                      label={t('common:labels.description')}
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
              {t('backtest:form.backtestParameters')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {t('backtest:form.configureParameters')}
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
                          helperText={t('backtest:form.dateRangeHelperText')}
                        />
                      )}
                    />
                  )}
                />
              </Grid>

              {/* Tick data availability info */}
              {dataRangeLoading && (
                <Grid size={{ xs: 12 }}>
                  <Alert severity="info">
                    {t('backtest:form.checkingTickDataRange')}
                  </Alert>
                </Grid>
              )}
              {dataRangeError && (
                <Grid size={{ xs: 12 }}>
                  <Alert severity="warning">{dataRangeError}</Alert>
                </Grid>
              )}
              {dataRange && dataRange.has_data && (
                <Grid size={{ xs: 12 }}>
                  <Alert severity="info">
                    {dataRange.instrument} data range:{' '}
                    {new Date(dataRange.min_timestamp!).toLocaleString()} –{' '}
                    {new Date(dataRange.max_timestamp!).toLocaleString()}
                  </Alert>
                </Grid>
              )}
              {dataCoverageWarning && (
                <Grid size={{ xs: 12 }}>
                  <Alert severity="warning">{dataCoverageWarning}</Alert>
                </Grid>
              )}

              <Grid size={{ xs: 12, md: 6 }}>
                <Controller
                  name="initial_balance"
                  control={control}
                  render={({ field }) => (
                    <BalanceInput
                      value={field.value}
                      onChange={field.onChange}
                      label={t('backtest:detail.initialBalance')}
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
                      label={t('backtest:form.commissionPerTrade')}
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
                      label={t('common:labels.instrument')}
                      placeholder={t('backtest:form.instrumentPlaceholder')}
                      error={!!errors.instrument}
                      helperText={
                        errors.instrument?.message ||
                        t('backtest:form.instrumentHelperText')
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
                      label={t('backtest:form.pipSizeOptional')}
                      type="number"
                      inputProps={{ min: 0, step: 0.00001 }}
                      error={!!errors.pip_size}
                      helperText={
                        errors.pip_size?.message ||
                        t('backtest:form.pipSizeHelperTextLong')
                      }
                    />
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
                            {t('backtest:form.closePositionsAtCompletion')}
                          </Typography>
                          <Typography
                            variant="body2"
                            color="text.secondary"
                            sx={{ mt: 0.5 }}
                          >
                            {t('backtest:form.closePositionsDescription')}
                          </Typography>
                        </Box>
                      }
                    />
                  )}
                />
              </Grid>

              <Grid size={{ xs: 12 }}>
                <Controller
                  name="hedging_enabled"
                  control={control}
                  render={({ field }) => (
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={field.value ?? true}
                          onChange={(e) => field.onChange(e.target.checked)}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body1">
                            {t('backtest:form.hedgingEnabled')}
                          </Typography>
                          <Typography
                            variant="body2"
                            color="text.secondary"
                            sx={{ mt: 0.5 }}
                          >
                            {t('backtest:form.hedgingDescription')}
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
          sell_at_completion: formData.sell_at_completion as boolean,
          hedging_enabled: formData.hedging_enabled as boolean | undefined,
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
              {t('backtest:form.reviewAndSubmit')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {t('backtest:form.reviewBeforeSubmitting')}
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
            {t('common:actions.back')}
          </Button>

          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="outlined"
              onClick={() => navigate('/backtest-tasks')}
            >
              {t('common:actions.cancel')}
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
                {taskId
                  ? t('common:actions.updateTask')
                  : t('common:actions.createTask')}
              </Button>
            ) : (
              <Button variant="contained" onClick={handleNext}>
                {t('common:actions.next')}
              </Button>
            )}
          </Box>
        </Box>
      </form>
    </Box>
  );
}
