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
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { useNavigate } from 'react-router-dom';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ConfigurationSelector } from '../tasks/forms/ConfigurationSelector';
import { DateRangePicker } from '../tasks/forms/DateRangePicker';
import { InstrumentSelector } from '../tasks/forms/InstrumentSelector';
import { BalanceInput } from '../tasks/forms/BalanceInput';
import { DataSource } from '../../types/common';
import { useUpdateBacktestTask } from '../../hooks/useBacktestTaskMutations';
import {
  useConfiguration,
  useConfigurations,
} from '../../hooks/useConfigurations';
import { invalidateBacktestTasksCache } from '../../hooks/useBacktestTasks';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';

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
    sell_at_completion: z.boolean().optional().default(false),
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
}

export default function BacktestTaskUpdateForm({
  taskId,
  taskName,
  taskDescription,
  initialData,
}: BacktestTaskUpdateFormProps) {
  const { t } = useTranslation(['backtest', 'common']);
  const navigate = useNavigate();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const updateTask = useUpdateBacktestTask();

  const {
    control,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<BacktestTaskUpdateData>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(backtestTaskUpdateSchema) as any,
    defaultValues: { ...initialData, data_source: DataSource.POSTGRESQL },
  });

  // Fetch all configurations and strategies
  const { data: configurationsData, isLoading: configurationsLoading } =
    useConfigurations({ page_size: 100 });
  const configurations = configurationsData?.results || [];
  const { strategies } = useStrategies();

  // Watch selected config
  // eslint-disable-next-line react-hooks/incompatible-library
  const selectedConfigId = watch('config_id');
  const configIdString = selectedConfigId || '';

  const { data: selectedConfig } = useConfiguration(configIdString);

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
          sell_at_completion: data.sell_at_completion,
        },
      });

      // Invalidate cache so the task list refreshes
      invalidateBacktestTasksCache();

      navigate('/backtest-tasks');
    } catch (error: unknown) {
      console.error('Failed to update task:', error);
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
      <Paper sx={{ p: 3, mb: 3, bgcolor: 'grey.50' }}>
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
                  configurations={configurations}
                  isLoading={configurationsLoading}
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
