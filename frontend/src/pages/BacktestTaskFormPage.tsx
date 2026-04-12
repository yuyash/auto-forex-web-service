import { Container, Box, Typography, Paper } from '@mui/material';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { ComponentProps } from 'react';
import BacktestTaskForm from '../components/backtest/BacktestTaskForm';
import BacktestTaskUpdateForm from '../components/backtest/BacktestTaskUpdateForm';
import { useBacktestTask } from '../hooks/useBacktestTasks';
import { LoadingSpinner, Breadcrumbs } from '../components/common';

type BacktestTaskUpdateInitialData = ComponentProps<
  typeof BacktestTaskUpdateForm
>['initialData'];

export default function BacktestTaskFormPage() {
  const { t } = useTranslation('backtest');
  const { id } = useParams<{ id: string }>();
  const taskId = id || undefined;

  const { data: task, isLoading } = useBacktestTask(taskId);
  const updateInitialData: BacktestTaskUpdateInitialData | null = task
    ? {
        config_id: task.config_id,
        data_source: task.data_source,
        start_time: task.start_time,
        end_time: task.end_time,
        initial_balance: parseFloat(task.initial_balance),
        commission_per_trade: parseFloat(task.commission_per_trade),
        pip_size: task.pip_size ? parseFloat(task.pip_size) : undefined,
        instrument: task.instrument,
        tick_granularity:
          task.tick_granularity as BacktestTaskUpdateInitialData['tick_granularity'],
        tick_window_value_mode:
          task.tick_window_value_mode as BacktestTaskUpdateInitialData['tick_window_value_mode'],
        sell_at_completion: task.sell_at_completion ?? false,
        hedging_enabled: task.hedging_enabled ?? true,
      }
    : null;

  if (taskId && (isLoading || !task)) {
    return (
      <Container maxWidth="lg">
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '60vh',
          }}
        >
          <LoadingSpinner />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Breadcrumbs />

        <Typography variant="h4" component="h1" gutterBottom>
          {taskId ? t('pages.editTitle') : t('pages.createTitle')}
        </Typography>

        <Paper sx={{ p: 4, mt: 3 }}>
          {taskId && task ? (
            <BacktestTaskUpdateForm
              taskId={taskId}
              taskName={task.name}
              taskDescription={task.description}
              debugOptions={task.debug_options}
              initialData={updateInitialData!}
            />
          ) : (
            <BacktestTaskForm />
          )}
        </Paper>
      </Box>
    </Container>
  );
}
