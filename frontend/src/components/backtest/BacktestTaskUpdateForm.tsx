import { useState } from 'react';
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
import { DataSource } from '../../types/common';
import { useUpdateBacktestTask } from '../../hooks/useBacktestTaskMutations';
import { useConfiguration } from '../../hooks/useConfigurations';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';
import { useAuth } from '../../contexts/AuthContext';
import { logger } from '../../utils/logger';

// Update schema - only editable fields
const backtestTaskUpdateSchema = z
  .object({
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
  })
  .refine((data) => data.start_time < data.end_time, {
    message: 'Start date must be before end date',
    path: ['start_time'],
  });

type BacktestTaskUpdateData = z.infer<typeof backtestTaskUpdateSchema>;

interface BacktestTaskUpdateFormProps {
  taskId: string;
  taskName: string;
  taskDescription?: string;
  initialData: BacktestTaskUpdateData;
  debugOptions?: Record<string, unknown>;
}

export default function BacktestTaskUpdateForm({
  taskId,
  taskName,
  taskDescription,
  initialData,
  debugOptions,
}: BacktestTaskUpdateFormProps) {
  const { t } = useTranslation(['backtest', 'common']);
  const { user } = useAuth();
  const navigate = useNavigate();
  const timezone = user?.timezone || 'UTC';
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [tracemalloc, setTracemalloc] = useState(
    Boolean(debugOptions?.tracemalloc)
  );
  const updateTask = useUpdateBacktestTask();

  const {
    control,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<BacktestTaskUpdateData>({
    resolver: zodResolver(
      backtestTaskUpdateSchema
    ) as Resolver<BacktestTaskUpdateData>,
    defaultValues: { ...initialData, data_source: DataSource.POSTGRESQL },
  });

  const { strategies } = useStrategies();

  // Watch selected config
  // eslint-disable-next-line react-hooks/incompatible-library
  const selectedConfigId = watch('config_id');
  const configIdString = selectedConfigId || '';

  const { data: selectedConfig } = useConfiguration(configIdString);
  const initialTickGranularity = initialData.tick_granularity;
  const initialTickWindowValueMode = initialData.tick_window_value_mode;
  const selectedTickGranularity = watch('tick_granularity');
  const selectedTickWindowValueMode = watch('tick_window_value_mode');
  const replaySettingsChanged =
    selectedTickGranularity !== initialTickGranularity ||
    selectedTickWindowValueMode !== initialTickWindowValueMode;

  const onSubmit = async (data: BacktestTaskUpdateData) => {
    setSubmitError(null);

    try {
      await updateTask.mutate({
        id: taskId,
        data: {
          config: data.config_id,
          data_source: DataSource.POSTGRESQL,
          start_time: data.start_time,
          end_time: data.end_time,
          initial_balance: data.initial_balance.toString(),
          commission_per_trade: data.commission_per_trade?.toString(),
          pip_size: data.pip_size?.toString(),
          instrument: data.instrument,
          tick_granularity: data.tick_granularity,
          tick_window_value_mode: data.tick_window_value_mode,
          sell_at_completion: data.sell_at_completion,
          hedging_enabled: data.hedging_enabled,
          debug_options: { tracemalloc },
        },
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
          config: 'Configuration',
          start_time: 'Start Date',
          end_time: 'End Date',
          initial_balance: 'Initial Balance',
          instrument: 'Instrument',
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
    <Box>
      <Paper sx={{ p: 3, mb: 3, bgcolor: 'action.hover' }}>
        <Typography variant="h6" gutterBottom>
          {t('trading:updateForm.taskInfoReadOnly')}
        </Typography>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 6 }}>
            <Typography variant="subtitle2" color="text.secondary">
              {t('backtest:form.taskName')}
            </Typography>
            <Typography variant="body1">{taskName}</Typography>
          </Grid>
          {taskDescription && (
            <Grid size={{ xs: 12 }}>
              <Typography variant="subtitle2" color="text.secondary">
                {t('common:labels.description')}
              </Typography>
              <Typography variant="body1">{taskDescription}</Typography>
            </Grid>
          )}
        </Grid>
      </Paper>

      <form onSubmit={handleSubmit(onSubmit)}>
        {submitError && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {submitError}
          </Alert>
        )}

        <Typography variant="h6" gutterBottom>
          {t('common:labels.configuration')}
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
                  {selectedConfig.description ||
                    t('trading:form.noDescription')}
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
                  error={errors.instrument?.message}
                  helperText={errors.instrument?.message as string}
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
              name="pip_size"
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label={t('backtest:form.pipSizeOptional')}
                  type="number"
                  inputProps={{ min: 0, step: 0.00001 }}
                  error={!!errors.pip_size}
                  helperText={
                    errors.pip_size?.message ||
                    t('backtest:form.pipSizeHelperText')
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
                        {t(
                          `backtest:form.tickWindowValueModeOptions.${option}`
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
            <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
              {t('common:debug.title')}
            </Typography>
            <FormControlLabel
              control={
                <Checkbox
                  checked={tracemalloc}
                  onChange={(e) => setTracemalloc(e.target.checked)}
                />
              }
              label={
                <Box>
                  <Typography variant="body1">
                    {t('common:debug.tracemalloc')}
                  </Typography>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mt: 0.5 }}
                  >
                    {t('common:debug.tracemallocDescription')}
                  </Typography>
                </Box>
              }
            />
          </Grid>
        </Grid>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
          <Button
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
      </form>
    </Box>
  );
}
