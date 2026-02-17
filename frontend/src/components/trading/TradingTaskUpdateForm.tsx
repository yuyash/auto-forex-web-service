import { useState } from 'react';

import { Box, Button, Typography, Paper, Alert } from '@mui/material';
import Grid from '@mui/material/Grid';
import { useNavigate } from 'react-router-dom';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ConfigurationSelector } from '../tasks/forms/ConfigurationSelector';
import { useUpdateTradingTask } from '../../hooks/useTradingTaskMutations';
import {
  useConfiguration,
  useConfigurations,
} from '../../hooks/useConfigurations';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';

// Update schema - only editable fields
const tradingTaskUpdateSchema = z.object({
  config_id: z.string().min(1, 'Configuration is required'),
});

type TradingTaskUpdateData = z.infer<typeof tradingTaskUpdateSchema>;

interface TradingTaskUpdateFormProps {
  taskId: string;
  taskName: string;
  taskDescription?: string;
  accountName: string;
  initialData: TradingTaskUpdateData;
}

export default function TradingTaskUpdateForm({
  taskId,
  taskName,
  taskDescription,
  accountName,
  initialData,
}: TradingTaskUpdateFormProps) {
  const navigate = useNavigate();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const updateTask = useUpdateTradingTask();

  const {
    control,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<TradingTaskUpdateData>({
    resolver: zodResolver(tradingTaskUpdateSchema),
    defaultValues: initialData,
  });

  // Fetch all configurations and strategies
  const { data: configurationsData } = useConfigurations({ page_size: 100 });
  const configurations = configurationsData?.results || [];
  const { strategies } = useStrategies();

  // Watch selected config
  // eslint-disable-next-line react-hooks/incompatible-library
  const selectedConfigId = watch('config_id');
  const { data: selectedConfig } = useConfiguration(selectedConfigId);

  const onSubmit = async (data: TradingTaskUpdateData) => {
    setSubmitError(null);

    try {
      await updateTask.mutate({
        id: taskId,
        data: {
          config: data.config_id,
        },
      });

      navigate('/trading-tasks');
    } catch (error: unknown) {
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
          <Grid size={{ xs: 12, md: 6 }}>
            <Typography variant="subtitle2" color="text.secondary">
              OANDA Account
            </Typography>
            <Typography variant="body1">{accountName}</Typography>
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
          Update the strategy configuration for this trading task
        </Typography>

        <Grid container spacing={3}>
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

        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
          <Button variant="outlined" onClick={() => navigate('/trading-tasks')}>
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
