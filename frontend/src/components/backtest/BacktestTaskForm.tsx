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
  Alert,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { useNavigate } from 'react-router-dom';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { ConfigurationSelector } from '../tasks/forms/ConfigurationSelector';
import { DateRangePicker } from '../tasks/forms/DateRangePicker';
import { InstrumentSelector } from '../tasks/forms/InstrumentSelector';
import { BalanceInput } from '../tasks/forms/BalanceInput';
import { DataSourceSelector } from '../tasks/forms/DataSourceSelector';
import { backtestTaskSchema } from '../tasks/forms/validationSchemas';
import { type BacktestTaskCreateData } from '../../types/backtestTask';
import { DataSource } from '../../types/common';
import {
  useCreateBacktestTask,
  useUpdateBacktestTask,
} from '../../hooks/useBacktestTaskMutations';
import {
  useConfiguration,
  useConfigurations,
} from '../../hooks/useConfigurations';

const steps = ['Configuration', 'Parameters', 'Review'];

interface BacktestTaskFormProps {
  taskId?: number;
  initialData?: Partial<BacktestTaskCreateData>;
}

export default function BacktestTaskForm({
  taskId,
  initialData,
}: BacktestTaskFormProps) {
  const navigate = useNavigate();
  const [activeStep, setActiveStep] = useState(0);
  const createTask = useCreateBacktestTask();
  const updateTask = useUpdateBacktestTask();

  const {
    control,
    handleSubmit,
    watch,
    formState: { errors },
    trigger,
  } = useForm<BacktestTaskCreateData>({
    resolver: zodResolver(backtestTaskSchema),
    defaultValues: initialData || {
      config_id: 0,
      name: '',
      description: '',
      data_source: DataSource.POSTGRESQL,
      start_time: '',
      end_time: '',
      initial_balance: 10000,
      commission_per_trade: 0,
      instruments: [],
    },
  });

  const selectedConfigId = watch('config_id');

  // Fetch all configurations
  const { data: configurationsData } = useConfigurations({ page_size: 100 });
  const configurations = configurationsData?.results || [];

  const { data: selectedConfig } = useConfiguration(selectedConfigId || 0);

  const handleNext = async () => {
    // Validate current step before proceeding
    let fieldsToValidate: (keyof BacktestTaskCreateData)[] = [];

    switch (activeStep) {
      case 0: // Configuration step
        fieldsToValidate = ['config_id', 'name'];
        break;
      case 1: // Parameters step
        fieldsToValidate = [
          'data_source',
          'start_time',
          'end_time',
          'initial_balance',
          'instruments',
        ];
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

  const onSubmit = async (data: BacktestTaskCreateData) => {
    try {
      if (taskId) {
        await updateTask.mutate({ id: taskId, data });
      } else {
        await createTask.mutate(data);
      }
      navigate('/backtest-tasks');
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
              Select Configuration
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Choose a strategy configuration for this backtest task
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
                      <strong>Type:</strong> {selectedConfig.strategy_type}
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

      case 1:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Backtest Parameters
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Configure the backtest time range, instruments, and initial
              settings
            </Typography>

            <Grid container spacing={3}>
              <Grid size={{ xs: 12 }}>
                <Controller
                  name="data_source"
                  control={control}
                  render={({ field }) => (
                    <DataSourceSelector
                      value={field.value}
                      onChange={field.onChange}
                      error={errors.data_source?.message}
                      helperText={errors.data_source?.message}
                    />
                  )}
                />
              </Grid>

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
                          required
                        />
                      )}
                    />
                  )}
                />
              </Grid>

              <Grid size={{ xs: 12 }}>
                <Controller
                  name="instruments"
                  control={control}
                  render={({ field }) => (
                    <InstrumentSelector
                      value={field.value}
                      onChange={field.onChange}
                      error={errors.instruments?.message}
                      helperText={errors.instruments?.message as string}
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
            </Grid>
          </Box>
        );

      case 2: {
        // Get form data for review step - extract values outside of render
        // eslint-disable-next-line react-hooks/incompatible-library
        const configId = watch('config_id');
        const name = watch('name');
        const description = watch('description');
        const dataSource = watch('data_source');
        const startTime = watch('start_time');
        const endTime = watch('end_time');
        const initialBalance = watch('initial_balance');
        const commissionPerTrade = watch('commission_per_trade');
        const instruments = watch('instruments');

        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Review & Submit
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Review your backtest task configuration before submitting
            </Typography>

            <Paper sx={{ p: 3 }}>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12 }}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Task Name
                  </Typography>
                  <Typography variant="body1">{name}</Typography>
                </Grid>

                {description && (
                  <Grid size={{ xs: 12 }}>
                    <Typography variant="subtitle2" color="text.secondary">
                      Description
                    </Typography>
                    <Typography variant="body1">{description}</Typography>
                  </Grid>
                )}

                <Grid size={{ xs: 12 }}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Configuration
                  </Typography>
                  <Typography variant="body1">
                    {selectedConfig?.name || `ID: ${configId}`}
                  </Typography>
                </Grid>

                <Grid size={{ xs: 12, md: 6 }}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Data Source
                  </Typography>
                  <Typography variant="body1">
                    {dataSource === DataSource.POSTGRESQL
                      ? 'PostgreSQL'
                      : 'AWS Athena'}
                  </Typography>
                </Grid>

                <Grid size={{ xs: 12, md: 6 }}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Date Range
                  </Typography>
                  <Typography variant="body1">
                    {new Date(startTime).toLocaleDateString()} -{' '}
                    {new Date(endTime).toLocaleDateString()}
                  </Typography>
                </Grid>

                <Grid size={{ xs: 12 }}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Instruments
                  </Typography>
                  <Typography variant="body1">
                    {instruments.join(', ')}
                  </Typography>
                </Grid>

                <Grid size={{ xs: 12, md: 6 }}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Initial Balance
                  </Typography>
                  <Typography variant="body1">
                    ${Number(initialBalance).toLocaleString()}
                  </Typography>
                </Grid>

                <Grid size={{ xs: 12, md: 6 }}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Commission Per Trade
                  </Typography>
                  <Typography variant="body1">
                    ${Number(commissionPerTrade).toFixed(2)}
                  </Typography>
                </Grid>
              </Grid>
            </Paper>
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
        {getStepContent(activeStep)}

        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
          <Button
            disabled={activeStep === 0}
            onClick={handleBack}
            variant="outlined"
          >
            Back
          </Button>

          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="outlined"
              onClick={() => navigate('/backtest-tasks')}
            >
              Cancel
            </Button>

            {activeStep === steps.length - 1 ? (
              <Button
                type="submit"
                variant="contained"
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
        </Box>
      </form>
    </Box>
  );
}
