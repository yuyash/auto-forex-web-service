import { Container, Box, Typography } from '@mui/material';
import { useParams } from 'react-router-dom';
import TradingTaskForm from '../components/trading/TradingTaskForm';
import { useTradingTask } from '../hooks/useTradingTasks';
import { LoadingSpinner, Breadcrumbs } from '../components/common';

export default function TradingTaskFormPage() {
  const { id } = useParams<{ id: string }>();
  const taskId = id ? parseInt(id, 10) : undefined;

  const { data: task, isLoading } = useTradingTask(taskId || 0);

  const isEditMode = !!taskId;

  if (isEditMode && isLoading) {
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

        <TradingTaskForm
          taskId={taskId}
          initialData={
            task
              ? {
                  account_id: task.account_id,
                  config_id: task.config_id,
                  name: task.name,
                  description: task.description,
                }
              : undefined
          }
        />
      </Box>
    </Container>
  );
}
