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
import { useAccounts } from '../../hooks/useAccounts';
import { useTradingTasks } from '../../hooks/useTradingTasks';
import { TaskStatus } from '../../types/common';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';

const steps = ['Account', 'Configuration', 'Review'];

// Validation schema
const tradingTaskSchema = z.object({
  account_id: z.string().min(1, 'Account is required'),
  config_id: z.string().min(1, 'Configuration is required'),
  name: z.string().min(1, 'Name is required').max(255),
  description: z.string().optional(),
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
  const navigate = useNavigate();
  const [activeStep, setActiveStep] = useState(0);
  const [formData, setFormData] = useState<Partial<TradingTaskFormData>>(
    initialData || {}
  );
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

  const selectedAccount = accounts.find(
    (account) => String(account.id) === effectiveAccountId
  );

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
      };

      if (taskId) {
        await updateTask.mutate({ id: taskId, data: taskData });
      } else {
        await createTask.mutate(taskData);
      }
      navigate('/trading-tasks');
    } catch {
      // Error is already handled by the mutation hook
    }
  };

  const getStepContent = (step: number) => {
    switch (step) {
      case 0:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Select Trading Account
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Choose the OANDA account for live trading
            </Typography>

            <Grid container spacing={3}>
              <Grid size={{ xs: 12 }}>
                <Controller
                  name="account_id"
                  control={control}
                  render={({ field }) => (
                    <FormControl fullWidth error={!!errors.account_id} required>
                      <InputLabel>Account</InputLabel>
                      <Select
                        {...field}
                        label="Account"
                        value={field.value || ''}
                        onChange={(e) => {
                          const value = e.target.value;
                          field.onChange(
                            typeof value === 'string' && value === ''
                              ? 0
                              : Number(value)
                          );
                        }}
                      >
                        <MenuItem value="">
                          <em>Select an account</em>
                        </MenuItem>
                        {accounts.map((account) => (
                          <MenuItem key={account.id} value={account.id}>
                            {account.account_id} ({account.api_type}) - Balance:{' '}
                            ${parseFloat(account.balance).toFixed(2)}
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
                      Account Details
                    </Typography>
                    <Typography variant="body2">
                      <strong>Account ID:</strong> {selectedAccount.account_id}
                    </Typography>
                    <Typography variant="body2">
                      <strong>Type:</strong>{' '}
                      <Chip
                        label={selectedAccount.api_type.toUpperCase()}
                        size="small"
                        color={
                          selectedAccount.api_type === 'live'
                            ? 'error'
                            : 'warning'
                        }
                      />
                    </Typography>
                    <Typography variant="body2">
                      <strong>Balance:</strong> $
                      {parseFloat(selectedAccount.balance).toFixed(2)}
                    </Typography>
                    <Typography variant="body2">
                      <strong>Currency:</strong> {selectedAccount.currency}
                    </Typography>
                  </Alert>
                </Grid>
              )}

              {hasActiveTask && (
                <Grid size={{ xs: 12 }}>
                  <Alert severity="warning" icon={<WarningIcon />}>
                    <Typography variant="subtitle2" gutterBottom>
                      Active Task Detected
                    </Typography>
                    <Typography variant="body2">
                      This account already has an active trading task:{' '}
                      <strong>{existingTasks.results[0].name}</strong>
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      Starting a new task will automatically stop the existing
                      task.
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
              Select Configuration
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Choose a strategy configuration for this trading task
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

      case 2:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Review and Confirm
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Review your trading task configuration before creating
            </Typography>

            <Grid container spacing={3}>
              <Grid size={{ xs: 12 }}>
                <Paper sx={{ p: 3 }}>
                  <Typography variant="subtitle1" gutterBottom>
                    Task Summary
                  </Typography>

                  <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      Task Name
                    </Typography>
                    <Typography variant="body1" gutterBottom>
                      {watchedName}
                    </Typography>
                  </Box>

                  {watchedDescription && (
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="body2" color="text.secondary">
                        Description
                      </Typography>
                      <Typography variant="body1" gutterBottom>
                        {watchedDescription}
                      </Typography>
                    </Box>
                  )}

                  <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      Account
                    </Typography>
                    <Typography variant="body1" gutterBottom>
                      {selectedAccount ? (
                        <>
                          {selectedAccount.account_id} (
                          {selectedAccount.api_type})
                        </>
                      ) : selectedAccountId ? (
                        'Loading account...'
                      ) : (
                        'No account selected'
                      )}
                    </Typography>
                  </Box>

                  <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      Configuration
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
                        'Loading...'
                      )}
                    </Typography>
                  </Box>
                </Paper>
              </Grid>

              {selectedAccount?.api_type === 'live' && (
                <>
                  <Grid size={{ xs: 12 }}>
                    <Alert severity="error" icon={<WarningIcon />}>
                      <Typography variant="subtitle2" gutterBottom>
                        <strong>LIVE TRADING RISK WARNING</strong>
                      </Typography>
                      <Typography variant="body2" gutterBottom>
                        Live trading involves substantial risk of loss. You
                        should carefully consider whether trading is appropriate
                        for you in light of your experience, objectives,
                        financial resources, and other relevant circumstances.
                      </Typography>
                      <Typography variant="body2" gutterBottom>
                        • Real money will be at risk
                      </Typography>
                      <Typography variant="body2" gutterBottom>
                        • Past performance does not guarantee future results
                      </Typography>
                      <Typography variant="body2" gutterBottom>
                        • Monitor your trading task closely
                      </Typography>
                      <Typography variant="body2">
                        • You can stop the task at any time
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
                            label="I understand and acknowledge the risks of live trading"
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
                      <strong>Practice Account</strong>
                    </Typography>
                    <Typography variant="body2">
                      This is a practice account with virtual funds. No real
                      money is at risk. Use this to test your strategies before
                      deploying to a live account.
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
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      <Paper sx={{ p: 3 }}>
        {getStepContent(activeStep)}

        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 3 }}>
          <Button
            disabled={activeStep === 0}
            onClick={handleBack}
            sx={{ mr: 1 }}
          >
            Back
          </Button>
          {activeStep === steps.length - 1 ? (
            <Button
              variant="contained"
              onClick={handleSubmit(onSubmit)}
              disabled={createTask.isLoading || updateTask.isLoading}
            >
              {taskId ? 'Update Task' : 'Create Task'}
            </Button>
          ) : (
            <Button variant="contained" onClick={handleNext}>
              Next
            </Button>
          )}
        </Box>
      </Paper>
    </Box>
  );
}
