import { Container, Box, Typography, Paper } from '@mui/material';
import { useParams } from 'react-router-dom';
import TradingTaskForm from '../components/trading/TradingTaskForm';
import TradingTaskUpdateForm from '../components/trading/TradingTaskUpdateForm';
import { useTradingTask } from '../hooks/useTradingTasks';
import { LoadingSpinner, Breadcrumbs } from '../components/common';

export default function TradingTaskFormPage() {
  const { id } = useParams<{ id: string }>();
  const taskId = id || undefined;

  const { data: task, isLoading } = useTradingTask(taskId, {
    enabled: !!taskId,
  });

  const isEditMode = !!taskId;

  if (isEditMode && (isLoading || !task)) {
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
          {isEditMode ? 'Edit Trading Task' : 'Create Trading Task'}
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
          {isEditMode
            ? 'Update your trading task configuration'
            : 'Set up a new automated trading task'}
        </Typography>

        <Paper sx={{ p: 4, mt: 3 }}>
          {isEditMode && task ? (
            <TradingTaskUpdateForm
              taskId={taskId}
              taskName={task.name}
              taskDescription={task.description}
              accountName={task.account_name}
              initialData={{
                config_id: task.config_id,
              }}
            />
          ) : (
            <TradingTaskForm />
          )}
        </Paper>
      </Box>
    </Container>
  );
}
