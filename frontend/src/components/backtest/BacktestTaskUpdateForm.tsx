import { useState } from 'react';

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
  taskId: number;
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
  const { data: configurationsData } = useConfigurations({ page_size: 100 });
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
        data?: Record<string, string | string[]>;
        message?: string;
      };

      let errorMessage = 'Failed to update task';
      if (err?.data) {
        const backendErrors = err.data;
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
          Task Information (Read-only)
        </Typography>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 6 }}>
            <Typography variant="subtitle2" color="text.secondary">
              Task Name
            </Typography>
            <Typography variant="body1">{taskName}</Typography>
          </Grid>
          {taskDescription && (
            <Grid size={{ xs: 12 }}>
              <Typography variant="subtitle2" color="text.secondary">
                Description
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
          Configuration
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Update the strategy configuration for this backtest task
        </Typography>

        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid size={{ xs: 12 }}>
            <Controller
              name="config_id"
              control={control}
              render={({ field }) => (
                <ConfigurationSelector
                  configurations={configurations}
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
        </Grid>

        <Typography variant="h6" gutterBottom>
          Backtest Parameters
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Update the backtest time range, instrument, and initial settings
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
              name="pip_size"
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label="Pip Size (Optional)"
                  type="number"
                  inputProps={{ min: 0, step: 0.00001 }}
                  error={!!errors.pip_size}
                  helperText={
                    errors.pip_size?.message ||
                    'Leave empty to auto-fetch from OANDA account'
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
                        Close all positions at backtest completion
                      </Typography>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{ mt: 0.5 }}
                      >
                        When enabled, all open positions will be automatically
                        closed at the final market price when the backtest
                        finishes. This provides realistic P&L calculations. When
                        disabled, positions remain open for analysis.
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
            Cancel
          </Button>

          <Button
            type="submit"
            variant="contained"
            disabled={updateTask.isLoading}
          >
            Update Task
          </Button>
        </Box>
      </form>
    </Box>
  );
}
