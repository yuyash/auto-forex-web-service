import { useState, useEffect } from 'react';

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
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormHelperText,
  Checkbox,
  FormControlLabel,
  Chip,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { Warning as WarningIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useForm, Controller, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { ConfigurationSelector } from '../tasks/forms/ConfigurationSelector';
import { type TradingTaskCreateData } from '../../types/tradingTask';
import type { Account } from '../../types/strategy';
import {
  useCreateTradingTask,
  useUpdateTradingTask,
} from '../../hooks/useTradingTaskMutations';
import {
  useConfiguration,
  useConfigurations,
} from '../../hooks/useConfigurations';
import { useAccounts, useAccount } from '../../hooks/useAccounts';
import { useTradingTasks } from '../../hooks/useTradingTasks';
import { TaskStatus } from '../../types/common';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';

const steps = [
  'trading:form.steps.account',
  'trading:form.steps.configuration',
  'trading:form.steps.review',
];

// Validation schema
const tradingTaskSchema = z.object({
  account_id: z.string().min(1, 'Account is required'),
  config_id: z.string().min(1, 'Configuration is required'),
  name: z.string().min(1, 'Name is required').max(255),
  description: z.string().optional(),
  dry_run: z.boolean().optional(),
  hedging_enabled: z.boolean().optional(),
  risk_acknowledged: z.boolean().optional(),
});

type TradingTaskFormData = z.infer<typeof tradingTaskSchema>;

interface TradingTaskFormProps {
  taskId?: string;
  initialData?: Partial<TradingTaskCreateData>;
}

export default function TradingTaskForm({
  taskId,
  initialData,
}: TradingTaskFormProps) {
  const { t } = useTranslation(['trading', 'common']);
  const navigate = useNavigate();
  const [activeStep, setActiveStep] = useState(0);
  const [formData, setFormData] = useState<Partial<TradingTaskFormData>>(
    initialData || {}
  );
  const [submitError, setSubmitError] = useState<string | null>(null);
  const createTask = useCreateTradingTask();
  const updateTask = useUpdateTradingTask();

  const {
    control,
    handleSubmit,
    formState: { errors },
    trigger,
    getValues,
    setValue,
  } = useForm<TradingTaskFormData>({
    resolver: zodResolver(tradingTaskSchema),
    defaultValues: {
      account_id: initialData?.account_id || '',
      config_id: initialData?.config_id || '',
      name: initialData?.name || '',
      description: initialData?.description || '',
      dry_run: false,
      hedging_enabled: true,
      risk_acknowledged: false,
    },
  });

  // Sync saved formData back into React Hook Form when changing steps
  useEffect(() => {
    if (Object.keys(formData).length > 0) {
      Object.entries(formData).forEach(([key, value]) => {
        if (value !== undefined) {
          setValue(key as keyof TradingTaskFormData, value, {
            shouldValidate: false,
          });
        }
      });
    }
  }, [formData, setValue]);

  const selectedAccountId = useWatch({ control, name: 'account_id' });

  const selectedConfigId = useWatch({ control, name: 'config_id' });

  const watchedName = useWatch({ control, name: 'name' });

  const watchedDescription = useWatch({ control, name: 'description' });

  // Fetch accounts
  const { data: accountsData } = useAccounts({ page_size: 100 });
  const accounts = (
    Array.isArray(accountsData)
      ? accountsData
      : (accountsData as unknown as { results?: Account[] })?.results || []
  ) as Account[];

  // For review step, use saved formData instead of watch
  // This ensures values persist across step changes
  const effectiveAccountId =
    activeStep === 2 && formData.account_id
      ? formData.account_id
      : selectedAccountId;

  const selectedAccountFromList = accounts.find(
    (account) => String(account.id) === effectiveAccountId
  );

  // Fetch live account details (balance, margin, etc.) from OANDA API
  const accountIdNum = effectiveAccountId ? Number(effectiveAccountId) : 0;
  const { data: accountDetail } = useAccount(accountIdNum, {
    enabled: accountIdNum > 0,
  });

  // Prefer live detail data over stale list data
  const selectedAccount = accountDetail
    ? (accountDetail as Account)
    : selectedAccountFromList;

  useEffect(() => {
    if (selectedAccount?.hedging_enabled === false) {
      setValue('hedging_enabled', false, {
        shouldValidate: false,
        shouldDirty: true,
      });
    }
  }, [selectedAccount?.hedging_enabled, setValue]);

  // Fetch all configurations and strategies
  const { data: configurationsData } = useConfigurations({ page_size: 100 });
  const configurations = configurationsData?.results || [];
  const { strategies } = useStrategies();

  const { data: selectedConfig } = useConfiguration(
    selectedConfigId || undefined
  );

  // Check if account already has an active task (only if valid account selected)
  const { data: existingTasks } = useTradingTasks(
    selectedAccountId
      ? {
          account_id: selectedAccountId,
          status: TaskStatus.RUNNING,
        }
      : undefined
  );

  const hasActiveTask =
    existingTasks && existingTasks.results.length > 0 && !taskId;

  const handleNext = async () => {
    // Save current form values to state BEFORE validation
    const currentValues = getValues();
    setFormData((prev) => ({ ...prev, ...currentValues }));

    // Validate current step before proceeding
    let fieldsToValidate: (keyof TradingTaskFormData)[] = [];

    switch (activeStep) {
      case 0: // Account step
        fieldsToValidate = ['account_id'];
        break;
      case 1: // Configuration step
        fieldsToValidate = ['config_id', 'name'];
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
    setActiveStep((prevActiveStep) => prevActiveStep + 1);
  };

  const handleBack = () => {
    // Save current form values to state before going back
    const currentValues = getValues();
    setFormData((prev) => ({ ...prev, ...currentValues }));
    setActiveStep((prevActiveStep) => prevActiveStep - 1);
  };

  const onSubmit = async (data: TradingTaskFormData) => {
    try {
      setSubmitError(null);

      // Merge the saved formData with the current form data to ensure we have all values
      const completeData = { ...formData, ...data } as TradingTaskFormData;

      // For live accounts, validate risk acknowledgment
      if (
        selectedAccount?.api_type === 'live' &&
        !completeData.risk_acknowledged
      ) {
        return;
      }

      const taskData: TradingTaskCreateData = {
        account_id: completeData.account_id,
        config_id: completeData.config_id,
        name: completeData.name,
        description: completeData.description,
        dry_run: completeData.dry_run,
        hedging_enabled:
          selectedAccount?.hedging_enabled === false
            ? false
            : completeData.hedging_enabled,
      };

      if (taskId) {
        await updateTask.mutate({ id: taskId, data: taskData });
      } else {
        await createTask.mutate(taskData);
      }
      navigate('/trading-tasks');
    } catch (error: unknown) {
      const err = error as {
        details?: Record<string, string | string[]>;
        message?: string;
      };

      let errorMessage = 'Failed to create trading task';
      if (err?.details && typeof err.details === 'object') {
        const backendErrors = err.details as Record<string, string | string[]>;
        const errorMessages: string[] = [];
        const fieldMapping: Record<string, string> = {
          account_id: 'Account',
          config_id: 'Configuration',
          name: 'Task Name',
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
          errorMessage = errorMessages.join(' ');
        }
      } else if (err?.message) {
        errorMessage = err.message;
      }

      setSubmitError(errorMessage);
    }
  };

  const getStepContent = (step: number) => {
    switch (step) {
      case 0:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              {t('trading:form.selectTradingAccount')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {t('trading:form.chooseOandaAccount')}
            </Typography>

            <Grid container spacing={3}>
              <Grid size={{ xs: 12 }}>
                <Controller
                  name="account_id"
                  control={control}
                  render={({ field }) => (
                    <FormControl fullWidth error={!!errors.account_id} required>
                      <InputLabel>{t('trading:form.account')}</InputLabel>
                      <Select
                        {...field}
                        label={t('trading:form.account')}
                        value={field.value || ''}
                        onChange={(e) => {
                          field.onChange(String(e.target.value));
                        }}
                      >
                        <MenuItem value="">
                          <em>{t('trading:form.selectAnAccount')}</em>
                        </MenuItem>
                        {accounts.map((account) => (
                          <MenuItem key={account.id} value={account.id}>
                            {account.account_id} ({account.api_type})
                          </MenuItem>
                        ))}
                      </Select>
                      {errors.account_id && (
                        <FormHelperText>
                          {errors.account_id.message}
                        </FormHelperText>
                      )}
                    </FormControl>
                  )}
                />
              </Grid>

              {selectedAccount && (
                <Grid size={{ xs: 12 }}>
                  <Alert severity="info">
                    <Typography variant="subtitle2" gutterBottom>
                      {t('trading:form.accountDetails')}
                    </Typography>
                    <Typography variant="body2">
                      <strong>{t('trading:form.accountId')}:</strong>{' '}
                      {selectedAccount.account_id}
                    </Typography>
                    <Typography variant="body2" component="div">
                      <strong>{t('trading:form.type')}:</strong>{' '}
                      <Chip
                        label={selectedAccount.api_type.toUpperCase()}
                        color={
                          selectedAccount.api_type === 'live'
                            ? 'error'
                            : 'warning'
                        }
                      />
                    </Typography>
                    <Typography variant="body2">
                      <strong>{t('trading:form.balance')}:</strong> $
                      {parseFloat(selectedAccount.balance).toFixed(2)}
                    </Typography>
                    <Typography variant="body2">
                      <strong>{t('trading:form.currency')}:</strong>{' '}
                      {selectedAccount.currency}
                    </Typography>
                  </Alert>
                </Grid>
              )}

              {hasActiveTask && (
                <Grid size={{ xs: 12 }}>
                  <Alert severity="error" icon={<WarningIcon />}>
                    <Typography variant="subtitle2" gutterBottom>
                      {t('trading:form.activeTaskDetected')}
                    </Typography>
                    <Typography variant="body2">
                      {t('trading:form.activeTaskWarning')}{' '}
                      <strong>{existingTasks.results[0].name}</strong>
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      {t('trading:form.activeTaskInstruction')}
                    </Typography>
                  </Alert>
                </Grid>
              )}
            </Grid>
          </Box>
        );

      case 1:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              {t('trading:form.selectConfiguration')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {t('trading:form.chooseStrategyConfig')}
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
                      label={t('trading:form.taskName')}
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

              <Grid size={{ xs: 12 }}>
                <Controller
                  name="dry_run"
                  control={control}
                  render={({ field }) => (
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={field.value ?? false}
                          onChange={field.onChange}
                        />
                      }
                      label={t('trading:form.dryRunMode')}
                    />
                  )}
                />
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', ml: 4 }}
                >
                  {t('trading:form.dryRunDescription')}
                </Typography>
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
                          onChange={field.onChange}
                          disabled={selectedAccount?.hedging_enabled === false}
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
                {selectedAccount?.hedging_enabled === false && (
                  <Alert severity="warning" sx={{ mt: 2 }}>
                    {t(
                      'trading:form.hedgingUnsupported',
                      'This OANDA account uses netting mode and does not support hedging. Hedging has been disabled for this task.'
                    )}
                  </Alert>
                )}
              </Grid>
            </Grid>
          </Box>
        );

      case 2:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              {t('trading:form.reviewAndConfirm')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {t('trading:form.reviewBeforeCreating')}
            </Typography>

            <Grid container spacing={3}>
              <Grid size={{ xs: 12 }}>
                <Paper sx={{ p: 3 }}>
                  <Typography variant="subtitle1" gutterBottom>
                    {t('trading:form.taskSummary')}
                  </Typography>

                  <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      {t('trading:form.taskName')}
                    </Typography>
                    <Typography variant="body1" gutterBottom>
                      {watchedName}
                    </Typography>
                  </Box>

                  {watchedDescription && (
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="body2" color="text.secondary">
                        {t('common:labels.description')}
                      </Typography>
                      <Typography variant="body1" gutterBottom>
                        {watchedDescription}
                      </Typography>
                    </Box>
                  )}

                  <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      {t('trading:form.account')}
                    </Typography>
                    <Typography variant="body1" gutterBottom>
                      {selectedAccount ? (
                        <>
                          {selectedAccount.account_id} (
                          {selectedAccount.api_type})
                        </>
                      ) : selectedAccountId ? (
                        t('trading:form.loadingAccounts')
                      ) : (
                        t('trading:form.noAccountsAvailable')
                      )}
                    </Typography>
                  </Box>

                  <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      {t('common:labels.configuration')}
                    </Typography>
                    <Typography variant="body1" gutterBottom>
                      {selectedConfig ? (
                        <>
                          {selectedConfig.name} (
                          {getStrategyDisplayName(
                            strategies,
                            selectedConfig.strategy_type
                          )}
                          )
                        </>
                      ) : (
                        t('common:status.loading')
                      )}
                    </Typography>
                  </Box>
                </Paper>
              </Grid>

              {formData.dry_run && (
                <Grid size={{ xs: 12 }}>
                  <Alert severity="warning">
                    <Typography variant="subtitle2" gutterBottom>
                      {t('trading:form.dryRunModeEnabled')}
                    </Typography>
                    <Typography variant="body2">
                      {t('trading:form.dryRunWarning')}
                    </Typography>
                  </Alert>
                </Grid>
              )}

              {selectedAccount?.api_type === 'live' && (
                <>
                  <Grid size={{ xs: 12 }}>
                    <Alert severity="error" icon={<WarningIcon />}>
                      <Typography variant="subtitle2" gutterBottom>
                        <strong>
                          {t('trading:risk.liveRiskWarningTitle')}
                        </strong>
                      </Typography>
                      <Typography variant="body2" gutterBottom>
                        {t('trading:risk.liveRiskWarningBody')}
                      </Typography>
                      <Typography variant="body2" gutterBottom>
                        • {t('trading:risk.realMoneyAtRisk')}
                      </Typography>
                      <Typography variant="body2" gutterBottom>
                        • {t('trading:risk.pastPerformance')}
                      </Typography>
                      <Typography variant="body2" gutterBottom>
                        • {t('trading:risk.monitorClosely')}
                      </Typography>
                      <Typography variant="body2">
                        • {t('trading:risk.canStopAnytime')}
                      </Typography>
                    </Alert>
                  </Grid>

                  <Grid size={{ xs: 12 }}>
                    <Controller
                      name="risk_acknowledged"
                      control={control}
                      render={({ field }) => (
                        <FormControl error={!!errors.risk_acknowledged}>
                          <FormControlLabel
                            control={
                              <Checkbox
                                checked={field.value}
                                onChange={field.onChange}
                              />
                            }
                            label={t('trading:risk.acknowledgeRisks')}
                          />
                          {errors.risk_acknowledged && (
                            <FormHelperText>
                              {errors.risk_acknowledged.message}
                            </FormHelperText>
                          )}
                        </FormControl>
                      )}
                    />
                  </Grid>
                </>
              )}

              {selectedAccount?.api_type === 'practice' && (
                <Grid size={{ xs: 12 }}>
                  <Alert severity="info">
                    <Typography variant="subtitle2" gutterBottom>
                      <strong>{t('trading:risk.practiceAccountTitle')}</strong>
                    </Typography>
                    <Typography variant="body2">
                      {t('trading:risk.practiceAccountBody')}
                    </Typography>
                  </Alert>
                </Grid>
              )}
            </Grid>
          </Box>
        );

      default:
        return 'Unknown step';
    }
  };

  return (
    <Box>
      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {steps.map((label) => (
          <Step key={label}>
            <StepLabel>{t(label)}</StepLabel>
          </Step>
        ))}
      </Stepper>

      <Paper sx={{ p: 3 }}>
        {getStepContent(activeStep)}

        {submitError && (
          <Alert severity="error" sx={{ mt: 3 }}>
            {submitError}
          </Alert>
        )}

        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 3 }}>
          <Button onClick={() => navigate(-1)} sx={{ mr: 'auto' }}>
            {t('common:actions.cancel')}
          </Button>
          <Button
            disabled={activeStep === 0}
            onClick={handleBack}
            sx={{ mr: 1 }}
          >
            {t('common:actions.back')}
          </Button>
          {activeStep === steps.length - 1 ? (
            <Button
              variant="contained"
              onClick={handleSubmit(onSubmit)}
              disabled={createTask.isLoading || updateTask.isLoading}
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
      </Paper>
    </Box>
  );
}
