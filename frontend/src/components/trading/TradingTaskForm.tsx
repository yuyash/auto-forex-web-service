import { useState } from 'react';
import {
  Box,
  Stepper,
  Step,
  StepLabel,
  Button,
  Typography,
  Paper,
  TextField,
  Grid,
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
import { Warning as WarningIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ConfigurationSelector } from '../tasks/forms/ConfigurationSelector';
import { TradingTaskCreateData } from '../../types/tradingTask';
import {
  useCreateTradingTask,
  useUpdateTradingTask,
} from '../../hooks/useTradingTaskMutations';
import { useConfiguration } from '../../hooks/useConfigurations';
import { useAccounts, useAccount } from '../../hooks/useAccounts';
import { useTradingTasks } from '../../hooks/useTradingTasks';
import { TaskStatus } from '../../types/common';

const steps = ['Account', 'Configuration', 'Review'];

// Validation schema
const tradingTaskSchema = z.object({
  account_id: z.number().min(1, 'Account is required'),
  config_id: z.number().min(1, 'Configuration is required'),
  name: z.string().min(1, 'Name is required').max(255),
  description: z.string().optional(),
  risk_acknowledged: z.boolean().refine((val) => val === true, {
    message: 'You must acknowledge the risks of live trading',
  }),
});

type TradingTaskFormData = z.infer<typeof tradingTaskSchema>;

interface TradingTaskFormProps {
  taskId?: number;
  initialData?: Partial<TradingTaskCreateData>;
}

export default function TradingTaskForm({
  taskId,
  initialData,
}: TradingTaskFormProps) {
  const navigate = useNavigate();
  const [activeStep, setActiveStep] = useState(0);
  const createTask = useCreateTradingTask();
  const updateTask = useUpdateTradingTask();

  const {
    control,
    handleSubmit,
    watch,
    formState: { errors },
    trigger,
  } = useForm<TradingTaskFormData>({
    resolver: zodResolver(tradingTaskSchema),
    defaultValues: {
      account_id: initialData?.account_id || 0,
      config_id: initialData?.config_id || 0,
      name: initialData?.name || '',
      description: initialData?.description || '',
      risk_acknowledged: false,
    },
  });

  const selectedAccountId = watch('account_id');
  const selectedConfigId = watch('config_id');

  // Fetch accounts
  const { data: accountsData } = useAccounts({ page_size: 100 });
  const { data: selectedAccount } = useAccount(selectedAccountId, {
    enabled: selectedAccountId > 0,
  });

  // Fetch selected configuration
  const { data: selectedConfig } = useConfiguration(selectedConfigId, {
    enabled: selectedConfigId > 0,
  });

  // Check if account already has an active task
  const { data: existingTasks } = useTradingTasks({
    account_id: selectedAccountId,
    status: TaskStatus.RUNNING,
  });

  const hasActiveTask =
    existingTasks && existingTasks.results.length > 0 && !taskId;

  const handleNext = async () => {
    // Validate current step before proceeding
    let fieldsToValidate: (keyof TradingTaskFormData)[] = [];

    switch (activeStep) {
      case 0: // Account step
        fieldsToValidate = ['account_id'];
        break;
      case 1: // Configuration step
        fieldsToValidate = ['config_id', 'name'];
        break;
      case 2: // Review step
        fieldsToValidate = ['risk_acknowledged'];
        break;
    }

    const isValid = await trigger(fieldsToValidate);

    if (isValid) {
      setActiveStep((prevActiveStep) => prevActiveStep + 1);
    }
  };

  const handleBack = () => {
    setActiveStep((prevActiveStep) => prevActiveStep - 1);
  };

  const onSubmit = async (data: TradingTaskFormData) => {
    try {
      const taskData: TradingTaskCreateData = {
        account_id: data.account_id,
        config_id: data.config_id,
        name: data.name,
        description: data.description,
      };

      if (taskId) {
        await updateTask.mutate({ id: taskId, data: taskData });
      } else {
        await createTask.mutate(taskData);
      }
      navigate('/trading-tasks');
    } catch (error) {
      console.error('Failed to save task:', error);
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
              <Grid item xs={12}>
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
                      >
                        <MenuItem value="">
                          <em>Select an account</em>
                        </MenuItem>
                        {accountsData?.results.map((account) => (
                          <MenuItem key={account.id} value={account.id}>
                            {account.account_id} ({account.api_type}) - Balance:{' '}
                            ${account.balance.toFixed(2)}
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
                <Grid item xs={12}>
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
                      {selectedAccount.balance.toFixed(2)}
                    </Typography>
                    <Typography variant="body2">
                      <strong>Currency:</strong> {selectedAccount.currency}
                    </Typography>
                  </Alert>
                </Grid>
              )}

              {hasActiveTask && (
                <Grid item xs={12}>
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
              <Grid item xs={12}>
                <Controller
                  name="config_id"
                  control={control}
                  render={({ field }) => (
                    <ConfigurationSelector
                      value={field.value}
                      onChange={field.onChange}
                      error={!!errors.config_id}
                      helperText={errors.config_id?.message}
                    />
                  )}
                />
              </Grid>

              {selectedConfig && (
                <Grid item xs={12}>
                  <Alert severity="info">
                    <Typography variant="subtitle2" gutterBottom>
                      Configuration Preview
                    </Typography>
                    <Typography variant="body2">
                      <strong>Type:</strong> {selectedConfig.strategy_type}
                    </Typography>
                    <Typography variant="body2">
                      <strong>Description:</strong>{' '}
                      {selectedConfig.description || 'No description'}
                    </Typography>
                  </Alert>
                </Grid>
              )}

              <Grid item xs={12}>
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

              <Grid item xs={12}>
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
              <Grid item xs={12}>
                <Paper sx={{ p: 3 }}>
                  <Typography variant="subtitle1" gutterBottom>
                    Task Summary
                  </Typography>

                  <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      Task Name
                    </Typography>
                    <Typography variant="body1" gutterBottom>
                      {watch('name')}
                    </Typography>
                  </Box>

                  {watch('description') && (
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="body2" color="text.secondary">
                        Description
                      </Typography>
                      <Typography variant="body1" gutterBottom>
                        {watch('description')}
                      </Typography>
                    </Box>
                  )}

                  <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      Account
                    </Typography>
                    <Typography variant="body1" gutterBottom>
                      {selectedAccount?.account_id} ({selectedAccount?.api_type}
                      )
                    </Typography>
                  </Box>

                  <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      Configuration
                    </Typography>
                    <Typography variant="body1" gutterBottom>
                      {selectedConfig?.name} ({selectedConfig?.strategy_type})
                    </Typography>
                  </Box>
                </Paper>
              </Grid>

              <Grid item xs={12}>
                <Alert severity="error" icon={<WarningIcon />}>
                  <Typography variant="subtitle2" gutterBottom>
                    <strong>RISK WARNING</strong>
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    Live trading involves substantial risk of loss. You should
                    carefully consider whether trading is appropriate for you in
                    light of your experience, objectives, financial resources,
                    and other relevant circumstances.
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

              <Grid item xs={12}>
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
