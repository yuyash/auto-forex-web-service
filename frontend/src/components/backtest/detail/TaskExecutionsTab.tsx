import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';

import {
  Box,
  Paper,
  Typography,
  Alert,
  CircularProgress,
  Tabs,
  Tab,
} from '@mui/material';
import { useTaskExecutions } from '../../../hooks/useTaskExecutions';
import { ErrorDisplay } from '../../tasks/display/ErrorDisplay';
import { ExecutionHistoryTable } from '../../tasks/display/ExecutionHistoryTable';
import { ExecutionComparisonView } from '../../tasks/display/ExecutionComparisonView';
import { TaskStatus, TaskType } from '../../../types/common';

interface TaskExecutionsTabProps {
  taskId: string;
  taskType?: TaskType;
  taskStatus?: TaskStatus;
  task?: {
    start_time: string;
    end_time: string;
  };
}

export function TaskExecutionsTab({
  taskId,
  taskType = TaskType.BACKTEST,
  taskStatus,
  task,
}: TaskExecutionsTabProps) {
  const navigate = useNavigate();
  const [tabValue, setTabValue] = useState(0); // 0 = History, 1 = Compare
  const [selectedComparisonIds, setSelectedComparisonIds] = useState<string[]>(
    []
  );

  const {
    data: executionsData,
    isLoading,
    error,
    refetch: refetchExecutions,
  } = useTaskExecutions(
    taskId,
    taskType,
    { page: 1, page_size: 20 },
    {
      enablePolling: true,
      pollingInterval: 3000,
    }
  );

  const executions = useMemo(
    () => executionsData?.results || [],
    [executionsData?.results]
  );

  // Refetch executions when task status changes
  useEffect(() => {
    if (taskStatus) {
      refetchExecutions();
    }
  }, [taskStatus, refetchExecutions]);

  const handleExecutionClick = (executionId: string) => {
    navigate(`/executions/${executionId}/results`);
  };

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '200px',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ px: 3 }}>
        <ErrorDisplay error={error} title="Failed to load execution history" />
      </Box>
    );
  }

  if (executions.length === 0) {
    return (
      <Box sx={{ px: 3 }}>
        <Alert severity="info">
          No execution history available. This task has not been executed yet.
        </Alert>
      </Box>
    );
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  return (
    <Box sx={{ px: 3 }}>
      {/* Backtest Period */}
      {task && (
        <Paper sx={{ p: 2, mb: 3, bgcolor: 'grey.50' }}>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            Backtest Period
          </Typography>
          <Typography variant="body1">
            {formatDate(task.start_time)} → {formatDate(task.end_time)}
          </Typography>
        </Paper>
      )}

      {/* Tabs for History and Compare */}
      <Paper sx={{ mb: 2 }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          aria-label="execution tabs"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label="History" />
          <Tab label="Compare" />
        </Tabs>
      </Paper>

      {/* History Tab */}
      {tabValue === 0 && (
        <ExecutionHistoryTable
          taskId={taskId}
          taskType={taskType}
          onExecutionClick={handleExecutionClick}
        />
      )}

      {/* Compare Tab */}
      {tabValue === 1 && (
        <ExecutionComparisonView
          executions={executions}
          selectedExecutionIds={selectedComparisonIds}
          onSelectionChange={setSelectedComparisonIds}
        />
      )}
    </Box>
  );
}
