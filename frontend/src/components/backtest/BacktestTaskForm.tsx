import { useState, useEffect, useRef, useMemo } from 'react';
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
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { useNavigate } from 'react-router-dom';
import { useForm, Controller, type Resolver } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { ConfigurationSelector } from '../tasks/forms/ConfigurationSelector';
import { DateRangePicker } from '../tasks/forms/DateRangePicker';
import { BalanceInput } from '../tasks/forms/BalanceInput';
import { InstrumentSelector } from '../tasks/forms/InstrumentSelector';
import { TaskReviewErrors } from '../tasks/forms/TaskReviewErrors';
import { DebugOptionsSection } from '../tasks/forms/DebugOptionsSection';
import {
  backtestTaskSchema,
  type BacktestTaskSchemaOutput,
} from '../tasks/forms/validationSchemas';
import { DataSource } from '../../types/common';
import { buildBacktestTaskCreatePayload } from '../tasks/forms/backtestTaskPayload';
import {
  useCreateBacktestTask,
  useUpdateBacktestTask,
} from '../../hooks/useBacktestTaskMutations';
import { useConfiguration } from '../../hooks/useConfigurations';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';
import {
  useSupportedInstruments,
  useTickDataRange,
} from '../../hooks/useMarketConfig';
import { useAuth } from '../../contexts/AuthContext';
import { useAppSettings } from '../../hooks/useAppSettings';
import { useNumberFormatter } from '../../hooks/useNumberFormatter';
import { useToast } from '../common/useToast';
import { currencySymbol } from '../../utils/numberFormat';
import {
  formatDateTimeInTimezone,
  formatTimestampWithTimezone,
} from '../../utils/timezone';

const DEFAULT_DATE_RANGE_DAYS = 30;

const weekdayOptions: ReadonlyArray<{
  value: number;
  key:
    | 'monday'
    | 'tuesday'
    | 'wednesday'
    | 'thursday'
    | 'friday'
    | 'saturday'
    | 'sunday';
  label: string;
}> = [
  { value: 0, key: 'monday', label: 'Monday' },
  { value: 1, key: 'tuesday', label: 'Tuesday' },
  { value: 2, key: 'wednesday', label: 'Wednesday' },
  { value: 3, key: 'thursday', label: 'Thursday' },
  { value: 4, key: 'friday', label: 'Friday' },
  { value: 5, key: 'saturday', label: 'Saturday' },
  { value: 6, key: 'sunday', label: 'Sunday' },
];

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
  timezone: string;
  language?: string;
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
    tick_granularity: string;
    tick_window_value_mode: string;
    sell_at_completion?: boolean;
    hedging_enabled?: boolean;
  };
}

function ReviewContent({
  timezone,
  language,
  selectedConfig,
  formValues,
}: ReviewContentProps) {
  const { t } = useTranslation(['backtest', 'common']);
  const { settings } = useAppSettings();
  const { formatNumber } = useNumberFormatter();
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
          {formatDateTimeInTimezone(start_time, timezone, language, {
            includeTimezone: true,
            dateFormat: settings.dateFormat,
          })}{' '}
          -{' '}
          {formatDateTimeInTimezone(end_time, timezone, language, {
            includeTimezone: true,
            dateFormat: settings.dateFormat,
          })}
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
          {currencySymbol('USD')}
          {formatNumber(Number(initial_balance), {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
        </Typography>
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <Typography variant="subtitle2" color="text.secondary">
          {t('backtest:detail.commissionPerTrade')}
        </Typography>
        <Typography variant="body1">
          {currencySymbol('USD')}
          {formatNumber(Number(commission_per_trade), {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
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

      <Grid size={{ xs: 12, md: 6 }}>
        <Typography variant="subtitle2" color="text.secondary">
          {t('backtest:form.tickGranularity')}
        </Typography>
        <Typography variant="body1">
          {t(
            `backtest:form.tickGranularityOptions.${formValues.tick_granularity}`
          )}
        </Typography>
      </Grid>

      {formValues.tick_granularity !== 'tick' && (
        <Grid size={{ xs: 12, md: 6 }}>
          <Typography variant="subtitle2" color="text.secondary">
            {t('backtest:form.tickWindowValueMode')}
          </Typography>
          <Typography variant="body1">
            {t(
              `backtest:form.tickWindowValueModeOptions.${formValues.tick_window_value_mode}`
            )}
          </Typography>
        </Grid>
      )}
    </Grid>
  );
}

export default function BacktestTaskForm({
  taskId,
  initialData,
}: BacktestTaskFormProps) {
  const { t } = useTranslation(['backtest', 'common']);
  const { user } = useAuth();
  const navigate = useNavigate();
  const { showError } = useToast();
  const timezone = user?.timezone || 'UTC';
  const language = user?.language;
  const isSuperuser = Boolean(user?.is_superuser);
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
      tick_granularity: 'tick',
      tick_window_value_mode: 'first',
      sell_at_completion: false,
      hedging_enabled: true,
      drain_duration_hours: 0,
      market_idle_pre_close_minutes: 0,
      market_idle_resume_delay_minutes: 0,
      market_close_enabled: false,
      market_close_weekday: 4,
      market_close_hour_utc: 21,
      market_open_weekday: 6,
      market_open_hour_utc: 21,
      max_tick_gap_hours: 120,
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
  const [tracemalloc, setTracemalloc] = useState(false);
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

  const watchedTickGranularity = watch('tick_granularity');
  const showTickWindowValueMode = watchedTickGranularity !== 'tick';

  const watchedMarketCloseEnabled = watch('market_close_enabled');

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
  const { strategies } = useStrategies();
  const {
    instruments: availableInstruments,
    usingFallback: usingInstrumentFallback,
  } = useSupportedInstruments();

  // config_id is now a UUID string
  const configIdString = selectedConfigId || '';

  const { data: selectedConfig } = useConfiguration(configIdString);
  const selectedStrategy = useMemo(
    () =>
      selectedConfig
        ? strategies.find(
            (strategy) => strategy.id === selectedConfig.strategy_type
          )
        : undefined,
    [selectedConfig, strategies]
  );
  const strategySupportsHedging =
    selectedStrategy?.capabilities?.runtime?.hedging !== false;

  useEffect(() => {
    if (!strategySupportsHedging) {
      setValue('hedging_enabled', false, {
        shouldValidate: false,
        shouldDirty: true,
      });
    }
  }, [setValue, strategySupportsHedging]);

  const watchedInstrument = watch('instrument');
  const watchedStartTime = watch('start_time');
  const watchedEndTime = watch('end_time');
  const {
    dataRange,
    error: dataRangeError,
    isLoading: dataRangeLoading,
  } = useTickDataRange(watchedInstrument);

  // When tick data range is loaded for a new task (no initialData dates),
  // set the default date range to [max - 1 month, max] with minutes/seconds
  // truncated to the hour.
  const dataRangeAppliedRef = useRef(false);
  useEffect(() => {
    if (
      dataRange?.has_data &&
      dataRange.max_timestamp &&
      !initialData?.start_time &&
      !initialData?.end_time &&
      !dataRangeAppliedRef.current
    ) {
      dataRangeAppliedRef.current = true;
      const maxDate = new Date(dataRange.max_timestamp);
      // Truncate to the hour
      maxDate.setMinutes(0, 0, 0);
      const startDate = new Date(maxDate);
      startDate.setMonth(startDate.getMonth() - 1);
      setValue('end_time', maxDate.toISOString());
      setValue('start_time', startDate.toISOString());
    }
  }, [dataRange, initialData?.start_time, initialData?.end_time, setValue]);

  // Reset when instrument changes so the next dataRange load re-applies defaults
  useEffect(() => {
    dataRangeAppliedRef.current = false;
  }, [watchedInstrument]);

  // Compute data coverage warning
  const dataCoverageWarning = useMemo<string | null>(() => {
    if (!dataRange || !dataRange.has_data) {
      if (dataRange && !dataRange.has_data && watchedInstrument) {
        return t('backtest:form.noTickDataFound', {
          instrument: watchedInstrument,
        });
      }
      return null;
    }
    const warnings: string[] = [];
    if (watchedStartTime && dataRange.min_timestamp) {
      const start = new Date(watchedStartTime);
      const minTs = new Date(dataRange.min_timestamp);
      if (start < minTs) {
        warnings.push(
          t('backtest:form.startTimeBeforeMinData', {
            timestamp: formatTimestampWithTimezone(minTs, timezone),
          })
        );
      }
    }
    if (watchedEndTime && dataRange.max_timestamp) {
      const end = new Date(watchedEndTime);
      const maxTs = new Date(dataRange.max_timestamp);
      if (end > maxTs) {
        warnings.push(
          t('backtest:form.endTimeAfterMaxData', {
            timestamp: formatTimestampWithTimezone(maxTs, timezone),
          })
        );
      }
    }
    return warnings.length > 0 ? warnings.join(' ') : null;
  }, [
    dataRange,
    t,
    timezone,
    watchedInstrument,
    watchedStartTime,
    watchedEndTime,
  ]);

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
        fieldsToValidate = [
          'start_time',
          'end_time',
          'initial_balance',
          'tick_granularity',
          'tick_window_value_mode',
        ];
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
    const apiData = buildBacktestTaskCreatePayload(
      {
        config_id: completeData.config_id,
        name: completeData.name,
        description: completeData.description,
        start_time: completeData.start_time,
        end_time: completeData.end_time,
        initial_balance: completeData.initial_balance,
        commission_per_trade: completeData.commission_per_trade,
        pip_size: completeData.pip_size,
        instrument: completeData.instrument,
        tick_granularity: completeData.tick_granularity,
        tick_window_value_mode: completeData.tick_window_value_mode,
        sell_at_completion: completeData.sell_at_completion,
        hedging_enabled: strategySupportsHedging
          ? completeData.hedging_enabled
          : false,
        drain_duration_hours: completeData.drain_duration_hours,
        market_idle_pre_close_minutes:
          completeData.market_idle_pre_close_minutes,
        market_idle_resume_delay_minutes:
          completeData.market_idle_resume_delay_minutes,
        market_close_enabled: completeData.market_close_enabled,
        market_close_weekday: completeData.market_close_weekday,
        market_close_hour_utc: completeData.market_close_hour_utc,
        market_open_weekday: completeData.market_open_weekday,
        market_open_hour_utc: completeData.market_open_hour_utc,
        max_tick_gap_hours: completeData.max_tick_gap_hours,
      },
      isSuperuser ? { tracemalloc } : undefined
    );

    try {
      if (taskId) {
        await updateTask.mutate({ id: taskId, data: apiData });
      } else {
        await createTask.mutate(apiData);
      }

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

      showError(errorMessage, 8000);
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
                          minDate={
                            dataRange?.min_timestamp
                              ? new Date(dataRange.min_timestamp)
                              : undefined
                          }
                          maxDate={
                            dataRange?.max_timestamp
                              ? new Date(dataRange.max_timestamp)
                              : new Date()
                          }
                          required
                          helperText={t('backtest:form.dateRangeHelperText')}
                          timezone={timezone}
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
                  <Alert severity="warning">
                    {t('backtest:form.tickDataRangeFetchFailed')}
                  </Alert>
                </Grid>
              )}
              {dataRange && dataRange.has_data && (
                <Grid size={{ xs: 12 }}>
                  <Alert severity="info">
                    {t('backtest:form.dataRange', {
                      instrument: dataRange.instrument,
                    })}{' '}
                    {formatTimestampWithTimezone(
                      dataRange.min_timestamp,
                      timezone
                    )}{' '}
                    –{' '}
                    {formatTimestampWithTimezone(
                      dataRange.max_timestamp,
                      timezone
                    )}
                  </Alert>
                </Grid>
              )}
              {dataCoverageWarning && (
                <Grid size={{ xs: 12 }}>
                  <Alert severity="warning">{dataCoverageWarning}</Alert>
                </Grid>
              )}
              {usingInstrumentFallback && (
                <Grid size={{ xs: 12 }}>
                  <Alert severity="warning">
                    {t('common:tables.trend.instrumentFallbackWarning')}
                  </Alert>
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
                    <InstrumentSelector
                      value={field.value}
                      onChange={field.onChange}
                      availableInstrument={availableInstruments}
                      label={t('common:labels.instrument')}
                      error={errors.instrument?.message}
                      helperText={
                        errors.instrument?.message ||
                        t('backtest:form.instrumentHelperText')
                      }
                      required
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

              <Grid size={{ xs: 12, md: 6 }}>
                <Controller
                  name="tick_granularity"
                  control={control}
                  render={({ field }) => (
                    <FormControl fullWidth error={!!errors.tick_granularity}>
                      <InputLabel id="backtest-tick-granularity-label">
                        {t('backtest:form.tickGranularity')}
                      </InputLabel>
                      <Select
                        {...field}
                        labelId="backtest-tick-granularity-label"
                        label={t('backtest:form.tickGranularity')}
                      >
                        {[
                          'tick',
                          '1s',
                          '10s',
                          '15s',
                          '30s',
                          '1m',
                          '5m',
                          '15m',
                          '30m',
                          '1h',
                        ].map((value) => (
                          <MenuItem key={value} value={value}>
                            {t(`backtest:form.tickGranularityOptions.${value}`)}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  )}
                />
              </Grid>

              <Grid size={{ xs: 12, md: 6 }}>
                <Controller
                  name="tick_window_value_mode"
                  control={control}
                  render={({ field }) => (
                    <FormControl
                      fullWidth
                      error={!!errors.tick_window_value_mode}
                      disabled={!showTickWindowValueMode}
                      sx={{
                        display: showTickWindowValueMode ? 'flex' : 'none',
                      }}
                    >
                      <InputLabel id="backtest-tick-window-value-mode-label">
                        {t('backtest:form.tickWindowValueMode')}
                      </InputLabel>
                      <Select
                        {...field}
                        labelId="backtest-tick-window-value-mode-label"
                        label={t('backtest:form.tickWindowValueMode')}
                      >
                        {['first', 'last', 'average', 'median'].map((value) => (
                          <MenuItem key={value} value={value}>
                            {t(
                              `backtest:form.tickWindowValueModeOptions.${value}`
                            )}
                          </MenuItem>
                        ))}
                      </Select>
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
                          checked={field.value ?? false}
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

              {strategySupportsHedging ? (
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
              ) : null}

              <Grid size={{ xs: 12 }} sx={{ mt: 2 }}>
                <Typography variant="subtitle1" fontWeight={600}>
                  {t('backtest:form.advancedSettings', 'Advanced settings')}
                </Typography>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mb: 2 }}
                >
                  {t(
                    'backtest:form.advancedSettingsDescription',
                    'Drain-on-stop and market-close idling behaviour. Market-idle thresholds are evaluated against the replayed tick timestamps, not wall-clock time.'
                  )}
                </Typography>
              </Grid>

              <Grid size={{ xs: 12, sm: 4 }}>
                <Controller
                  name="drain_duration_hours"
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
                      type="number"
                      label={t(
                        'backtest:form.drainDurationHours',
                        'Drain duration (hours)'
                      )}
                      helperText={
                        errors.drain_duration_hours?.message ||
                        t(
                          'backtest:form.drainDurationHoursHelp',
                          'Maximum hours to keep draining before giving up. 0 = wait forever for breakeven.'
                        )
                      }
                      error={!!errors.drain_duration_hours}
                      inputProps={{ min: 0, step: 1 }}
                    />
                  )}
                />
              </Grid>

              <Grid size={{ xs: 12, sm: 4 }}>
                <Controller
                  name="market_idle_pre_close_minutes"
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
                      type="number"
                      label={t(
                        'backtest:form.marketIdlePreCloseMinutes',
                        'Idle before market close (min)'
                      )}
                      helperText={
                        errors.market_idle_pre_close_minutes?.message ||
                        t(
                          'backtest:form.marketIdlePreCloseMinutesHelp',
                          'Switch to IDLE this many minutes before the weekly forex close. Evaluated against the replayed tick timestamp. 0 disables.'
                        )
                      }
                      error={!!errors.market_idle_pre_close_minutes}
                      inputProps={{ min: 0, max: 720, step: 1 }}
                    />
                  )}
                />
              </Grid>

              <Grid size={{ xs: 12, sm: 4 }}>
                <Controller
                  name="market_idle_resume_delay_minutes"
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
                      type="number"
                      label={t(
                        'backtest:form.marketIdleResumeDelayMinutes',
                        'Resume delay after open (min)'
                      )}
                      helperText={
                        errors.market_idle_resume_delay_minutes?.message ||
                        t(
                          'backtest:form.marketIdleResumeDelayMinutesHelp',
                          'Wait this many minutes (replayed clock) after the market reopens before resuming trading.'
                        )
                      }
                      error={!!errors.market_idle_resume_delay_minutes}
                      inputProps={{ min: 0, max: 720, step: 1 }}
                    />
                  )}
                />
              </Grid>

              <Grid size={{ xs: 12, sm: 4 }}>
                <Controller
                  name="max_tick_gap_hours"
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
                      type="number"
                      label={t(
                        'backtest:form.maxTickGapHours',
                        'Max tick gap before fail (hours)'
                      )}
                      helperText={
                        errors.max_tick_gap_hours?.message ||
                        t(
                          'backtest:form.maxTickGapHoursHelp',
                          'Fail the backtest if replayed ticks jump forward by more than this many hours. Default: 120 (5 days).'
                        )
                      }
                      error={!!errors.max_tick_gap_hours}
                      inputProps={{ min: 1, step: 1 }}
                    />
                  )}
                />
              </Grid>

              <Grid size={{ xs: 12 }} sx={{ mt: 1 }}>
                <Controller
                  name="market_close_enabled"
                  control={control}
                  render={({ field }) => (
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={field.value ?? false}
                          onChange={(e) => field.onChange(e.target.checked)}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body1">
                            {t(
                              'backtest:form.marketCloseEnabled',
                              'Apply weekly market close'
                            )}
                          </Typography>
                          <Typography
                            variant="body2"
                            color="text.secondary"
                            sx={{ mt: 0.5 }}
                          >
                            {t(
                              'backtest:form.marketCloseEnabledDescription',
                              'When disabled, the backtest never treats any replayed time as market-closed and the idle thresholds above have no effect.'
                            )}
                          </Typography>
                        </Box>
                      }
                    />
                  )}
                />
              </Grid>

              {watchedMarketCloseEnabled && (
                <>
                  <Grid size={{ xs: 12, sm: 3 }}>
                    <Controller
                      name="market_close_weekday"
                      control={control}
                      render={({ field }) => (
                        <FormControl
                          fullWidth
                          error={!!errors.market_close_weekday}
                        >
                          <InputLabel id="backtest-market-close-weekday-label">
                            {t(
                              'backtest:form.marketCloseWeekday',
                              'Close weekday (UTC)'
                            )}
                          </InputLabel>
                          <Select
                            labelId="backtest-market-close-weekday-label"
                            label={t(
                              'backtest:form.marketCloseWeekday',
                              'Close weekday (UTC)'
                            )}
                            value={field.value ?? 4}
                            onChange={(e) =>
                              field.onChange(Number(e.target.value))
                            }
                          >
                            {weekdayOptions.map((opt) => (
                              <MenuItem key={opt.value} value={opt.value}>
                                {t(
                                  `backtest:form.weekdays.${opt.key}`,
                                  opt.label
                                )}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      )}
                    />
                  </Grid>

                  <Grid size={{ xs: 12, sm: 3 }}>
                    <Controller
                      name="market_close_hour_utc"
                      control={control}
                      render={({ field }) => (
                        <TextField
                          {...field}
                          value={field.value ?? ''}
                          onChange={(e) => {
                            const val = e.target.value;
                            field.onChange(
                              val === '' ? undefined : Number(val)
                            );
                          }}
                          fullWidth
                          type="number"
                          label={t(
                            'backtest:form.marketCloseHourUtc',
                            'Close hour (UTC)'
                          )}
                          helperText={
                            errors.market_close_hour_utc?.message ||
                            t(
                              'backtest:form.marketCloseHourUtcHelp',
                              'Hour of day at which the market closes (0–23 UTC).'
                            )
                          }
                          error={!!errors.market_close_hour_utc}
                          inputProps={{ min: 0, max: 23, step: 1 }}
                        />
                      )}
                    />
                  </Grid>

                  <Grid size={{ xs: 12, sm: 3 }}>
                    <Controller
                      name="market_open_weekday"
                      control={control}
                      render={({ field }) => (
                        <FormControl
                          fullWidth
                          error={!!errors.market_open_weekday}
                        >
                          <InputLabel id="backtest-market-open-weekday-label">
                            {t(
                              'backtest:form.marketOpenWeekday',
                              'Open weekday (UTC)'
                            )}
                          </InputLabel>
                          <Select
                            labelId="backtest-market-open-weekday-label"
                            label={t(
                              'backtest:form.marketOpenWeekday',
                              'Open weekday (UTC)'
                            )}
                            value={field.value ?? 6}
                            onChange={(e) =>
                              field.onChange(Number(e.target.value))
                            }
                          >
                            {weekdayOptions.map((opt) => (
                              <MenuItem key={opt.value} value={opt.value}>
                                {t(
                                  `backtest:form.weekdays.${opt.key}`,
                                  opt.label
                                )}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      )}
                    />
                  </Grid>

                  <Grid size={{ xs: 12, sm: 3 }}>
                    <Controller
                      name="market_open_hour_utc"
                      control={control}
                      render={({ field }) => (
                        <TextField
                          {...field}
                          value={field.value ?? ''}
                          onChange={(e) => {
                            const val = e.target.value;
                            field.onChange(
                              val === '' ? undefined : Number(val)
                            );
                          }}
                          fullWidth
                          type="number"
                          label={t(
                            'backtest:form.marketOpenHourUtc',
                            'Open hour (UTC)'
                          )}
                          helperText={
                            errors.market_open_hour_utc?.message ||
                            t(
                              'backtest:form.marketOpenHourUtcHelp',
                              'Hour of day at which the market reopens (0–23 UTC).'
                            )
                          }
                          error={!!errors.market_open_hour_utc}
                          inputProps={{ min: 0, max: 23, step: 1 }}
                        />
                      )}
                    />
                  </Grid>
                </>
              )}
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
          tick_granularity: formData.tick_granularity as string,
          tick_window_value_mode: formData.tick_window_value_mode as string,
          sell_at_completion: formData.sell_at_completion as boolean,
          hedging_enabled: formData.hedging_enabled as boolean | undefined,
        };

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
          tick_granularity: 'Tick Granularity',
          tick_window_value_mode: 'Tick Window Value Mode',
        };

        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              {t('backtest:form.reviewAndSubmit')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {t('backtest:form.reviewBeforeSubmitting')}
            </Typography>

            <TaskReviewErrors
              errors={errors}
              fieldLabels={fieldNameMapping}
              title="Please fix the following errors before submitting:"
              correctionHint="Click Back to return to previous steps and correct these errors."
            />

            <Paper sx={{ p: 3 }}>
              {selectedConfig ? (
                <ReviewContent
                  timezone={timezone}
                  language={language}
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

            {isSuperuser && (
              <DebugOptionsSection
                tracemalloc={tracemalloc}
                onTracemallocChange={setTracemalloc}
                sx={{ mt: 3 }}
              />
            )}
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
        <Paper sx={{ p: 3 }}>{getStepContent(activeStep)}</Paper>

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
