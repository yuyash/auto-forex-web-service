import { useEffect, useMemo, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Box,
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
import { z } from 'zod';
import { ConfigurationSelector } from '../tasks/forms/ConfigurationSelector';
import { DateRangePicker } from '../tasks/forms/DateRangePicker';
import { InstrumentSelector } from '../tasks/forms/InstrumentSelector';
import { BalanceInput } from '../tasks/forms/BalanceInput';
import { CurrencyCodeField } from '../tasks/forms/CurrencyCodeField';
import { DataSource } from '../../types/common';
import { useUpdateBacktestTask } from '../../hooks/useBacktestTaskMutations';
import {
  useConfiguration,
  useConfigurations,
} from '../../hooks/useConfigurations';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';
import { useAuth } from '../../contexts/AuthContext';
import { logger } from '../../utils/logger';
import { buildBacktestTaskUpdatePayload } from '../tasks/forms/backtestTaskPayload';
import { hasDirtyExecutionSettings } from '../tasks/forms/executionEditGuards';
import { DebugOptionsSection } from '../tasks/forms/DebugOptionsSection';
import {
  currencyCodeSchema,
  optionalCurrencyCodeSchema,
} from '../tasks/forms/currencyValidation';
import { BacktestInitialPositionsEditor } from './BacktestInitialPositionsEditor';
import {
  useFirstTick,
  useSupportedInstruments,
} from '../../hooks/useMarketConfig';
import { DEFAULT_ACCOUNT_CURRENCY } from '../../constants/currencies';
import {
  currencyOptionsForInstrument,
  normalizeInstrumentName,
  preferredCurrencyForInstrument,
  preferredCurrencyFromOptions,
} from '../../utils/instruments';

// Update schema - only editable fields
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

const optionalPositiveNumberSchema = z.preprocess(
  (value) => (value === '' ? undefined : value),
  z.coerce.number().positive().optional().nullable()
);

const initialPositionSchema = z.object({
  layer_number: z.coerce.number().int().min(1),
  retracement_count: z.coerce.number().int().min(0),
  units: z.coerce.number().int().positive(),
  entry_price: z.coerce.number().positive(),
  planned_exit_price: optionalPositiveNumberSchema,
  stop_loss_price: optionalPositiveNumberSchema,
  status: z
    .enum(['open', 'closed', 'pending_rebuild'])
    .optional()
    .default('open'),
  exit_price: optionalPositiveNumberSchema,
  close_reason: z.string().optional(),
});

const initialPositionCycleSchema = z.object({
  direction: z.enum(['long', 'short']),
  positions: z.array(initialPositionSchema).min(1),
});

function expectedInitialPositionSlot(
  positionIndex: number,
  rMax = 7
): { layer: number; retracement: number } {
  const perLayer = rMax + 1;
  return {
    layer: Math.floor(positionIndex / perLayer) + 1,
    retracement: positionIndex % perLayer,
  };
}

const backtestTaskUpdateSchema = z
  .object({
    name: z
      .string()
      .min(1, 'Task name is required')
      .max(100, 'Task name must be less than 100 characters'),
    description: z
      .string()
      .max(500, 'Description must be less than 500 characters')
      .optional(),
    config_id: z
      .string()
      .min(1, 'Configuration is required')
      .uuid('Configuration must be a valid ID'),
    data_source: z.nativeEnum(DataSource),
    start_time: z.string().min(1, 'Start date is required'),
    end_time: z.string().min(1, 'End date is required'),
    initial_balance: z.coerce
      .number({
        message: 'Initial balance must be a number',
      })
      .positive('Initial balance must be greater than zero'),
    account_currency: currencyCodeSchema,
    display_currency: optionalCurrencyCodeSchema,
    commission_per_trade: z.coerce
      .number({
        message: 'Commission must be a number',
      })
      .nonnegative('Commission cannot be negative')
      .optional(),
    pip_size: z.coerce
      .number({
        message: 'Pip size must be a number',
      })
      .positive('Pip size must be greater than zero')
      .optional(),
    instrument: z.string().min(1, 'Instrument is required'),
    tick_granularity: z.enum([
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
    ]),
    tick_window_value_mode: z.enum(['first', 'last', 'average', 'median']),
    sell_at_completion: z.boolean().optional().default(false),
    hedging_enabled: z.boolean().optional().default(true),
    drain_duration_hours: z.coerce
      .number({ message: 'Drain duration must be a number' })
      .int('Drain duration must be an integer')
      .min(0, 'Drain duration cannot be negative')
      .optional(),
    market_idle_pre_close_minutes: z.coerce
      .number({ message: 'Must be a non-negative integer' })
      .int('Must be an integer')
      .min(0, 'Must be non-negative')
      .max(720, 'Must not exceed 720 minutes (12 hours)')
      .optional(),
    market_idle_resume_delay_minutes: z.coerce
      .number({ message: 'Must be a non-negative integer' })
      .int('Must be an integer')
      .min(0, 'Must be non-negative')
      .max(720, 'Must not exceed 720 minutes (12 hours)')
      .optional(),
    market_close_enabled: z.boolean().optional().default(false),
    market_close_weekday: z.coerce
      .number({ message: 'Weekday must be a number' })
      .int('Weekday must be an integer')
      .min(0, 'Weekday must be between 0 (Monday) and 6 (Sunday)')
      .max(6, 'Weekday must be between 0 (Monday) and 6 (Sunday)')
      .optional(),
    market_close_hour_utc: z.coerce
      .number({ message: 'Hour must be a number' })
      .int('Hour must be an integer')
      .min(0, 'Hour must be between 0 and 23')
      .max(23, 'Hour must be between 0 and 23')
      .optional(),
    market_open_weekday: z.coerce
      .number({ message: 'Weekday must be a number' })
      .int('Weekday must be an integer')
      .min(0, 'Weekday must be between 0 (Monday) and 6 (Sunday)')
      .max(6, 'Weekday must be between 0 (Monday) and 6 (Sunday)')
      .optional(),
    market_open_hour_utc: z.coerce
      .number({ message: 'Hour must be a number' })
      .int('Hour must be an integer')
      .min(0, 'Hour must be between 0 and 23')
      .max(23, 'Hour must be between 0 and 23')
      .optional(),
    max_tick_gap_hours: z.coerce
      .number({ message: 'Tick gap threshold must be a number' })
      .int('Tick gap threshold must be an integer')
      .min(1, 'Tick gap threshold must be at least 1 hour')
      .optional(),
    initial_positions_enabled: z.boolean().optional().default(false),
    initial_position_cycles: z
      .array(initialPositionCycleSchema)
      .optional()
      .default([]),
  })
  .superRefine((data, ctx) => {
    if (!data.initial_positions_enabled) {
      return;
    }
    if (!data.initial_position_cycles.length) {
      ctx.addIssue({
        code: 'custom',
        path: ['initial_position_cycles'],
        message: 'At least one initial cycle is required',
      });
    }
    data.initial_position_cycles.forEach((cycle, cycleIndex) => {
      const seen = new Set<string>();
      cycle.positions.forEach((position, positionIndex) => {
        const expected = expectedInitialPositionSlot(positionIndex);
        if (
          position.layer_number !== expected.layer ||
          position.retracement_count !== expected.retracement
        ) {
          ctx.addIssue({
            code: 'custom',
            path: [
              'initial_position_cycles',
              cycleIndex,
              'positions',
              positionIndex,
            ],
            message: `Positions must be stacked from L1/R0. Expected L${expected.layer}/R${expected.retracement}.`,
          });
        }
        const key = `${position.layer_number}:${position.retracement_count}`;
        if (seen.has(key)) {
          ctx.addIssue({
            code: 'custom',
            path: [
              'initial_position_cycles',
              cycleIndex,
              'positions',
              positionIndex,
              'retracement_count',
            ],
            message: `Duplicate L${position.layer_number}/R${position.retracement_count}`,
          });
        }
        seen.add(key);
      });
    });
  })
  .refine((data) => data.start_time < data.end_time, {
    message: 'Start date must be before end date',
    path: ['start_time'],
  });

type BacktestTaskUpdateData = z.infer<typeof backtestTaskUpdateSchema>;
type BacktestTaskUpdateInitialData = Omit<
  BacktestTaskUpdateData,
  'name' | 'description'
>;

export interface BacktestTaskUpdateFormProps {
  taskId: string;
  taskName: string;
  taskDescription?: string;
  initialData: BacktestTaskUpdateInitialData;
  debugOptions?: Record<string, unknown>;
  restartRequiredForExecutionEdits?: boolean;
}

export default function BacktestTaskUpdateForm({
  taskId,
  taskName,
  taskDescription,
  initialData,
  debugOptions,
  restartRequiredForExecutionEdits = false,
}: BacktestTaskUpdateFormProps) {
  const { t } = useTranslation(['backtest', 'common']);
  const { user } = useAuth();
  const navigate = useNavigate();
  const timezone = user?.timezone || 'UTC';
  const language = user?.language;
  const isSuperuser = Boolean(user?.is_superuser);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [tracemalloc, setTracemalloc] = useState(
    Boolean(debugOptions?.tracemalloc)
  );
  const updateTask = useUpdateBacktestTask();

  const defaultCurrency =
    preferredCurrencyForInstrument(
      initialData.instrument || 'USD_JPY',
      language
    ) || DEFAULT_ACCOUNT_CURRENCY;

  const {
    control,
    handleSubmit,
    watch,
    setValue,
    formState: { dirtyFields, errors },
  } = useForm<BacktestTaskUpdateData>({
    resolver: zodResolver(
      backtestTaskUpdateSchema
    ) as Resolver<BacktestTaskUpdateData>,
    defaultValues: {
      ...initialData,
      name: taskName,
      description: taskDescription ?? '',
      account_currency: initialData.account_currency || defaultCurrency,
      display_currency: initialData.display_currency || defaultCurrency,
    },
  });

  const { strategies } = useStrategies();

  // Watch selected config
  // eslint-disable-next-line react-hooks/incompatible-library
  const selectedConfigId = watch('config_id');
  const configIdString = selectedConfigId || '';

  const { data: selectedConfig } = useConfiguration(configIdString);
  const { data: configurationsData } = useConfigurations({
    page: 1,
    page_size: 200,
  });
  const selectedListConfig = useMemo(
    () =>
      (configurationsData?.results ?? []).find(
        (config) => config.id === configIdString
      ),
    [configIdString, configurationsData?.results]
  );
  const selectedStrategyType =
    selectedConfig?.strategy_type ?? selectedListConfig?.strategy_type;
  const selectedStrategy = useMemo(
    () =>
      selectedStrategyType
        ? strategies.find((strategy) => strategy.id === selectedStrategyType)
        : undefined,
    [selectedStrategyType, strategies]
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
  const initialTickGranularity = initialData.tick_granularity;
  const initialTickWindowValueMode = initialData.tick_window_value_mode;
  const selectedTickGranularity = watch('tick_granularity');
  const selectedTickWindowValueMode = watch('tick_window_value_mode');
  const watchedInitialPositionsEnabled = watch('initial_positions_enabled');
  const watchedPipSize = watch('pip_size');
  const watchedAccountCurrency =
    watch('account_currency') || DEFAULT_ACCOUNT_CURRENCY;
  const watchedDisplayCurrency = watch('display_currency') || '';
  const watchedInstrument = watch('instrument');
  const currencyOptions = useMemo(
    () => currencyOptionsForInstrument(watchedInstrument || 'USD_JPY'),
    [watchedInstrument]
  );
  const defaultCurrencyForSelectedInstrument =
    preferredCurrencyFromOptions(currencyOptions, language) ||
    DEFAULT_ACCOUNT_CURRENCY;
  useEffect(() => {
    if (!currencyOptions.length) return;
    if (!currencyOptions.includes(watchedAccountCurrency)) {
      setValue('account_currency', defaultCurrencyForSelectedInstrument, {
        shouldDirty: true,
        shouldValidate: true,
      });
    }
    if (
      !watchedDisplayCurrency ||
      !currencyOptions.includes(watchedDisplayCurrency)
    ) {
      setValue('display_currency', defaultCurrencyForSelectedInstrument, {
        shouldDirty: true,
        shouldValidate: true,
      });
    }
  }, [
    currencyOptions,
    defaultCurrencyForSelectedInstrument,
    setValue,
    watchedAccountCurrency,
    watchedDisplayCurrency,
  ]);
  const watchedStartTime = watch('start_time');
  const watchedEndTime = watch('end_time');
  const {
    firstTick,
    error: firstTickError,
    isLoading: firstTickLoading,
  } = useFirstTick(watchedInstrument, watchedStartTime, watchedEndTime, {
    enabled: watchedInitialPositionsEnabled === true,
  });
  const { instruments: availableInstruments, metadata: instrumentMetadata } =
    useSupportedInstruments();
  const selectedInstrumentMetadata = watchedInstrument
    ? instrumentMetadata[normalizeInstrumentName(watchedInstrument)]
    : undefined;
  const pipSizeHelperText = selectedInstrumentMetadata
    ? t('backtest:form.pipSizeMetadataHelperText', {
        defaultValue:
          'Default pip size for {{instrument}} is {{pipSize}} ({{base}}/{{quote}}).',
        instrument: selectedInstrumentMetadata.normalized_name,
        pipSize: selectedInstrumentMetadata.pip_size,
        base: selectedInstrumentMetadata.base_currency,
        quote: selectedInstrumentMetadata.quote_currency,
      })
    : t('backtest:form.pipSizeHelperText');
  const replaySettingsChanged =
    selectedTickGranularity !== initialTickGranularity ||
    selectedTickWindowValueMode !== initialTickWindowValueMode;
  const watchedMarketCloseEnabled = watch('market_close_enabled');
  const showRestartRequiredGuard =
    restartRequiredForExecutionEdits &&
    hasDirtyExecutionSettings(dirtyFields as Record<string, unknown>);

  const onSubmit = async (data: BacktestTaskUpdateData) => {
    setSubmitError(null);

    try {
      await updateTask.mutate({
        id: taskId,
        data: buildBacktestTaskUpdatePayload(
          {
            ...data,
            hedging_enabled: strategySupportsHedging
              ? data.hedging_enabled
              : false,
          },
          isSuperuser ? { tracemalloc } : undefined
        ),
      });

      navigate('/backtest-tasks');
    } catch (error: unknown) {
      logger.error('Failed to update backtest task', {
        taskId,
        error: error instanceof Error ? error.message : String(error),
      });
      const err = error as {
        details?: Record<string, string | string[]>;
        message?: string;
      };

      let errorMessage = 'Failed to update task';
      if (err?.details && typeof err.details === 'object') {
        const backendErrors = err.details as Record<string, string | string[]>;
        const errorMessages: string[] = [];

        const fieldMapping: Record<string, string> = {
          config: t('common:labels.configuration'),
          name: t('backtest:form.taskName'),
          description: t('common:labels.description'),
          start_time: t('backtest:config.startDate'),
          end_time: t('backtest:config.endDate'),
          initial_balance: t('backtest:detail.initialBalance'),
          instrument: t('common:labels.instrument'),
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

      setSubmitError(errorMessage);
    }
  };

  return (
    <Box
      component="form"
      onSubmit={handleSubmit(onSubmit)}
      onKeyDown={preventInputEnterSubmit}
    >
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          {t('common:labels.taskDetails')}
        </Typography>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 6 }}>
            <Controller
              name="name"
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label={t('backtest:form.taskName')}
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
      </Paper>

      {submitError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {submitError}
        </Alert>
      )}
      {restartRequiredForExecutionEdits && (
        <Alert
          severity={showRestartRequiredGuard ? 'warning' : 'info'}
          sx={{ mb: 3 }}
        >
          {t('backtest:form.restartRequiredForExecutionEdits')}
        </Alert>
      )}

      <Typography variant="h6" gutterBottom>
        {t('common:labels.strategyConfiguration')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        {t('backtest:form.chooseStrategyConfig')}
      </Typography>

      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12 }}>
          <Controller
            name="config_id"
            control={control}
            render={({ field }) => (
              <ConfigurationSelector
                value={field.value}
                onChange={field.onChange}
                error={errors.config_id?.message}
                helperText={errors.config_id?.message}
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
                {selectedConfig.description || t('trading:form.noDescription')}
              </Typography>
            </Alert>
          </Grid>
        )}
      </Grid>

      <Typography variant="h6" gutterBottom>
        {t('backtest:form.backtestParameters')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        {t('backtest:form.updateParameters')}
      </Typography>

      {replaySettingsChanged && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          {t('backtest:form.replaySettingsRestartNotice')}
        </Alert>
      )}

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
                    startLabel={t('backtest:config.startDate')}
                    endLabel={t('backtest:config.endDate')}
                    maxDate={new Date()}
                    required
                    helperText={t('backtest:form.dateRangeHelperText')}
                    timezone={timezone}
                  />
                )}
              />
            )}
          />
        </Grid>

        <Grid size={{ xs: 12 }}>
          <Controller
            name="instrument"
            control={control}
            render={({ field }) => (
              <InstrumentSelector
                value={field.value}
                onChange={field.onChange}
                availableInstrument={availableInstruments}
                error={errors.instrument?.message}
                helperText={
                  (errors.instrument?.message as string) ||
                  t('backtest:form.instrumentHelperText')
                }
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
                label={t('backtest:detail.initialBalance')}
                currency={watchedAccountCurrency}
                error={errors.initial_balance?.message}
                helperText={errors.initial_balance?.message}
              />
            )}
          />
        </Grid>

        <Grid size={{ xs: 12, md: 3 }}>
          <Controller
            name="account_currency"
            control={control}
            render={({ field }) => (
              <CurrencyCodeField
                id="backtest-update-account-currency"
                label={t('common:labels.accountCurrency', {
                  defaultValue: 'Account currency',
                })}
                value={field.value}
                onChange={field.onChange}
                options={currencyOptions}
                error={!!errors.account_currency}
                helperText={errors.account_currency?.message}
                required
              />
            )}
          />
        </Grid>

        <Grid size={{ xs: 12, md: 3 }}>
          <Controller
            name="display_currency"
            control={control}
            render={({ field }) => (
              <CurrencyCodeField
                id="backtest-update-display-currency"
                label={t('common:labels.displayCurrency', {
                  defaultValue: 'Display currency',
                })}
                value={field.value || defaultCurrencyForSelectedInstrument}
                onChange={field.onChange}
                options={currencyOptions}
                error={!!errors.display_currency}
                helperText={errors.display_currency?.message}
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
                type="text"
                inputMode="decimal"
                inputProps={{ min: 0, step: 0.01 }}
                error={!!errors.commission_per_trade}
                helperText={errors.commission_per_trade?.message}
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
                fullWidth
                label={t('backtest:form.pipSizeOptional')}
                type="text"
                inputMode="decimal"
                inputProps={{ min: 0, step: 0.00001 }}
                error={!!errors.pip_size}
                helperText={errors.pip_size?.message || pipSizeHelperText}
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
                <InputLabel id="backtest-update-tick-granularity-label">
                  {t('backtest:form.tickGranularity')}
                </InputLabel>
                <Select
                  {...field}
                  labelId="backtest-update-tick-granularity-label"
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
                  ].map((option) => (
                    <MenuItem key={option} value={option}>
                      {t(`backtest:form.tickGranularityOptions.${option}`)}
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
              <FormControl fullWidth error={!!errors.tick_window_value_mode}>
                <InputLabel id="backtest-update-tick-window-value-mode-label">
                  {t('backtest:form.tickWindowValueMode')}
                </InputLabel>
                <Select
                  {...field}
                  labelId="backtest-update-tick-window-value-mode-label"
                  label={t('backtest:form.tickWindowValueMode')}
                >
                  {['first', 'last', 'average', 'median'].map((option) => (
                    <MenuItem key={option} value={option}>
                      {t(`backtest:form.tickWindowValueModeOptions.${option}`)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
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

        <Grid size={{ xs: 12 }}>
          <Controller
            name="initial_position_cycles"
            control={control}
            render={({ field }) => (
              <BacktestInitialPositionsEditor
                enabled={watchedInitialPositionsEnabled ?? false}
                onEnabledChange={(enabled) =>
                  setValue('initial_positions_enabled', enabled, {
                    shouldDirty: true,
                    shouldValidate: true,
                  })
                }
                value={field.value ?? []}
                onChange={field.onChange}
                selectedConfig={
                  selectedConfig ?? selectedListConfig ?? undefined
                }
                strategyType={selectedStrategyType}
                pipSize={watchedPipSize}
                firstTick={firstTick}
                firstTickLoading={firstTickLoading}
                firstTickError={firstTickError}
                error={
                  errors.initial_position_cycles?.message as string | undefined
                }
              />
            )}
          />
        </Grid>

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
                type="text"
                inputMode="decimal"
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
                type="text"
                inputMode="decimal"
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
                type="text"
                inputMode="decimal"
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
                type="text"
                inputMode="decimal"
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
                  <FormControl fullWidth error={!!errors.market_close_weekday}>
                    <InputLabel id="backtest-update-market-close-weekday-label">
                      {t(
                        'backtest:form.marketCloseWeekday',
                        'Close weekday (UTC)'
                      )}
                    </InputLabel>
                    <Select
                      labelId="backtest-update-market-close-weekday-label"
                      label={t(
                        'backtest:form.marketCloseWeekday',
                        'Close weekday (UTC)'
                      )}
                      value={field.value ?? 4}
                      onChange={(e) => field.onChange(Number(e.target.value))}
                    >
                      {weekdayOptions.map((opt) => (
                        <MenuItem key={opt.value} value={opt.value}>
                          {t(`backtest:form.weekdays.${opt.key}`, opt.label)}
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
                      field.onChange(val === '' ? undefined : Number(val));
                    }}
                    fullWidth
                    type="text"
                    inputMode="decimal"
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
                  <FormControl fullWidth error={!!errors.market_open_weekday}>
                    <InputLabel id="backtest-update-market-open-weekday-label">
                      {t(
                        'backtest:form.marketOpenWeekday',
                        'Open weekday (UTC)'
                      )}
                    </InputLabel>
                    <Select
                      labelId="backtest-update-market-open-weekday-label"
                      label={t(
                        'backtest:form.marketOpenWeekday',
                        'Open weekday (UTC)'
                      )}
                      value={field.value ?? 6}
                      onChange={(e) => field.onChange(Number(e.target.value))}
                    >
                      {weekdayOptions.map((opt) => (
                        <MenuItem key={opt.value} value={opt.value}>
                          {t(`backtest:form.weekdays.${opt.key}`, opt.label)}
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
                      field.onChange(val === '' ? undefined : Number(val));
                    }}
                    fullWidth
                    type="text"
                    inputMode="decimal"
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

        {isSuperuser && (
          <Grid size={{ xs: 12 }}>
            <DebugOptionsSection
              tracemalloc={tracemalloc}
              onTracemallocChange={setTracemalloc}
              sx={{ mt: 2 }}
            />
          </Grid>
        )}
      </Grid>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
        <Button
          type="button"
          variant="outlined"
          onClick={() => navigate('/backtest-tasks')}
        >
          {t('common:actions.cancel')}
        </Button>

        <Button
          type="submit"
          variant="contained"
          disabled={updateTask.isLoading}
        >
          {t('common:actions.updateTask')}
        </Button>
      </Box>
    </Box>
  );
}

function preventInputEnterSubmit(event: KeyboardEvent<HTMLFormElement>) {
  if (event.key !== 'Enter' || event.nativeEvent.isComposing) {
    return;
  }

  if (event.target instanceof HTMLInputElement) {
    const allowedInputTypes = new Set([
      'button',
      'checkbox',
      'radio',
      'reset',
      'submit',
    ]);
    if (!allowedInputTypes.has(event.target.type)) {
      event.preventDefault();
    }
  }
}
