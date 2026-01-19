// RunningTaskView page - displays real-time task execution with all monitoring components
import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Container,
  Box,
  Typography,
  Grid,
  Alert,
  Breadcrumbs,
  Link,
  Paper,
} from '@mui/material';
import { Home as HomeIcon, ArrowBack as BackIcon } from '@mui/icons-material';
import { ExecutionStatusCard } from '../components/tasks/display/ExecutionStatusCard';
import { EquityChart } from '../components/tasks/charts/EquityChart';
import { EventFeed } from '../components/tasks/display/EventFeed';
import { FloorStrategyTimeline } from '../components/tasks/charts/FloorStrategyTimeline';
import { MetricsPanel } from '../components/tasks/display/MetricsPanel';
import { TaskControlButtons } from '../components/tasks/actions/TaskControlButtons';
import { useExecutionStatus } from '../hooks/useExecutionStatus';
import { TaskType } from '../types';

export const RunningTaskView: React.FC = () => {
  const { taskType, taskId, executionId } = useParams<{
    taskType: string;
    taskId: string;
    executionId: string;
  }>();
  const navigate = useNavigate();

  const parsedTaskType =
    taskType === 'backtest' ? TaskType.BACKTEST : TaskType.TRADING;
  const parsedTaskId = taskId ? parseInt(taskId, 10) : null;
  const parsedExecutionId = executionId ? parseInt(executionId, 10) : null;

  const { data: status, error: statusError } =
    useExecutionStatus(parsedExecutionId);

  if (!parsedTaskId || !parsedExecutionId) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Alert severity="error">Invalid task or execution ID</Alert>
      </Container>
    );
  }

  const handleBack = () => {
    if (taskType === 'backtest') {
      navigate(`/backtest-tasks/${taskId}`);
    } else {
      navigate(`/trading-tasks/${taskId}`);
    }
  };

  const handleControlSuccess = () => {
    // Optionally show a success message
    console.log('Control action successful');
  };

  const handleControlError = (error: Error) => {
    // Optionally show an error message
    console.error('Control action failed:', error);
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Breadcrumbs */}
      <Breadcrumbs sx={{ mb: 2 }}>
        <Link
          color="inherit"
          href="/"
          onClick={(e) => {
            e.preventDefault();
            navigate('/');
          }}
          sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
        >
          <HomeIcon fontSize="small" />
          Home
        </Link>
        <Link
          color="inherit"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            handleBack();
          }}
          sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
        >
          <BackIcon fontSize="small" />
          {taskType === 'backtest' ? 'Backtest Tasks' : 'Trading Tasks'}
        </Link>
        <Typography color="text.primary">
          Execution #{parsedExecutionId}
        </Typography>
      </Breadcrumbs>

      {/* Page Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          {taskType === 'backtest' ? 'Backtest' : 'Trading'} Execution Monitor
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Real-time monitoring of execution #{parsedExecutionId}
        </Typography>
      </Box>

      {/* Error Alert */}
      {statusError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Failed to load execution status: {statusError.message}
        </Alert>
      )}

      {/* Control Buttons */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <TaskControlButtons
          taskId={parsedTaskId}
          taskType={parsedTaskType}
          currentStatus={status?.status || 'unknown'}
          onSuccess={handleControlSuccess}
          onError={handleControlError}
        />
      </Paper>

      {/* Main Content Grid */}
      <Grid container spacing={3}>
        {/* Status Card - Full Width */}
        <Grid size={{ xs: 12 }}>
          <ExecutionStatusCard executionId={parsedExecutionId} />
        </Grid>

        {/* Metrics Panel - Full Width */}
        <Grid size={{ xs: 12 }}>
          <MetricsPanel executionId={parsedExecutionId} />
        </Grid>

        {/* Equity Chart - Full Width */}
        <Grid size={{ xs: 12 }}>
          <EquityChart executionId={parsedExecutionId} height={400} />
        </Grid>

        {/* Floor Strategy Timeline - Full Width (if applicable) */}
        <Grid size={{ xs: 12 }}>
          <FloorStrategyTimeline executionId={parsedExecutionId} height={400} />
        </Grid>

        {/* Event Feed - Full Width */}
        <Grid size={{ xs: 12 }}>
          <EventFeed
            executionId={parsedExecutionId}
            maxHeight={600}
            autoScroll
          />
        </Grid>
      </Grid>
    </Container>
  );
};

export default RunningTaskView;
