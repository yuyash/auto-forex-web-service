import { Container, Box, Typography, Paper } from '@mui/material';
import { useParams } from 'react-router-dom';
import BacktestTaskForm from '../components/backtest/BacktestTaskForm';
import BacktestTaskUpdateForm from '../components/backtest/BacktestTaskUpdateForm';
import { useBacktestTask } from '../hooks/useBacktestTasks';
import { LoadingSpinner, Breadcrumbs } from '../components/common';

export default function BacktestTaskFormPage() {
  const { id } = useParams<{ id: string }>();
  const taskId = id ? parseInt(id, 10) : undefined;

  const { data: task, isLoading } = useBacktestTask(taskId);

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
          {taskId ? 'Edit Backtest Task' : 'Create Backtest Task'}
        </Typography>

        <Paper sx={{ p: 4, mt: 3 }}>
          {taskId && task ? (
            <BacktestTaskUpdateForm
              taskId={taskId}
              taskName={task.name}
              taskDescription={task.description}
              initialData={{
                config_id: task.config_id,
                data_source: task.data_source,
                start_time: task.start_time,
                end_time: task.end_time,
                initial_balance: parseFloat(task.initial_balance),
                commission_per_trade: parseFloat(task.commission_per_trade),
                instrument: task.instrument,
                sell_at_completion: task.sell_at_completion ?? false,
              }}
            />
          ) : (
            <BacktestTaskForm />
          )}
        </Paper>
      </Box>
    </Container>
  );
}
