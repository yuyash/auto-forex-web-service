import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Box,
  Button,
  Typography,
  Paper,
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
import { useUpdateTradingTask } from '../../hooks/useTradingTaskMutations';
import { useConfiguration } from '../../hooks/useConfigurations';
import { useAccount } from '../../hooks/useAccounts';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';

// Update schema - only editable fields
const tradingTaskUpdateSchema = z.object({
  config_id: z.string().min(1, 'Configuration is required'),
  hedging_enabled: z.boolean().optional(),
});

type TradingTaskUpdateData = z.infer<typeof tradingTaskUpdateSchema>;

interface TradingTaskUpdateFormProps {
  taskId: string;
  taskName: string;
  taskDescription?: string;
  accountId: number;
  accountName: string;
  initialData: TradingTaskUpdateData;
  debugOptions?: Record<string, unknown>;
}

export default function TradingTaskUpdateForm({
  taskId,
  taskName,
  taskDescription,
  accountId,
  accountName,
  initialData,
  debugOptions,
}: TradingTaskUpdateFormProps) {
  const { t } = useTranslation(['trading', 'common']);
  const navigate = useNavigate();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [tracemalloc, setTracemalloc] = useState(
    Boolean(debugOptions?.tracemalloc)
  );
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

  const { strategies } = useStrategies();

  // Fetch account details to check hedging support
  const { data: accountDetail } = useAccount(accountId, {
    enabled: accountId > 0,
  });
  const accountHedgingEnabled = accountDetail
    ? (accountDetail as { hedging_enabled?: boolean }).hedging_enabled
    : undefined;

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
          hedging_enabled:
            accountHedgingEnabled === false ? false : data.hedging_enabled,
          debug_options: { tracemalloc },
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
          hedging_enabled: 'Hedging',
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
              {t('trading:form.taskName')}
            </Typography>
            <Typography variant="body1">{taskName}</Typography>
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <Typography variant="subtitle2" color="text.secondary">
              {t('common:labels.oandaAccount')}
            </Typography>
            <Typography variant="body1">{accountName}</Typography>
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
          {t('trading:updateForm.updateStrategyConfig')}
        </Typography>

        <Grid container spacing={3}>
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

        <Typography variant="h6" gutterBottom sx={{ mt: 4 }}>
          {t('trading:form.hedgingEnabled', 'Hedging')}
        </Typography>
        <Grid container spacing={3}>
          <Grid size={{ xs: 12 }}>
            <Controller
              name="hedging_enabled"
              control={control}
              render={({ field }) => (
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={field.value ?? true}
                      onChange={field.onChange}
                      disabled={accountHedgingEnabled === false}
                    />
                  }
                  label={t(
                    'trading:form.hedgingEnabled',
                    'Enable Hedging (simultaneous long/short positions)'
                  )}
                />
              )}
            />
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', ml: 4 }}
            >
              {t(
                'trading:form.hedgingDescription',
                'When enabled, the strategy can hold both long and short positions simultaneously. Requires a hedging-enabled OANDA account.'
              )}
            </Typography>
            {accountHedgingEnabled === false && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                {t(
                  'trading:form.hedgingUnsupported',
                  'This OANDA account uses netting mode and does not support hedging. Hedging has been disabled for this task.'
                )}
              </Alert>
            )}
          </Grid>
        </Grid>

        <Typography variant="h6" gutterBottom sx={{ mt: 4 }}>
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

        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
          <Button variant="outlined" onClick={() => navigate('/trading-tasks')}>
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
