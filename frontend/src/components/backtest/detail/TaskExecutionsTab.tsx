import { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Alert,
  List,
  ListItemButton,
  Collapse,
  Grid,
  Divider,
  CircularProgress,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  PlayArrow as PlayArrowIcon,
} from '@mui/icons-material';
import { useTaskExecutions } from '../../../hooks/useTaskExecutions';
import { StatusBadge } from '../../tasks/display/StatusBadge';
import { ErrorDisplay } from '../../tasks/display/ErrorDisplay';
import { TaskStatus, TaskType } from '../../../types/common';
import type { TaskExecution } from '../../../types/execution';

interface TaskExecutionsTabProps {
  taskId: number;
  taskType?: TaskType;
}

interface ExecutionItemProps {
  execution: TaskExecution;
}

function ExecutionItem({ execution }: ExecutionItemProps) {
  const [expanded, setExpanded] = useState(false);

  const handleToggle = () => {
    setExpanded(!expanded);
  };

  const formatDuration = (duration?: string) => {
    if (!duration) return 'N/A';
    return duration;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const getStatusIcon = (status: TaskStatus) => {
    switch (status) {
      case TaskStatus.COMPLETED:
        return <CheckCircleIcon color="success" />;
      case TaskStatus.FAILED:
        return <ErrorIcon color="error" />;
      case TaskStatus.RUNNING:
        return <PlayArrowIcon color="primary" />;
      default:
        return null;
    }
  };

  return (
    <Paper variant="outlined" sx={{ mb: 2 }}>
      <ListItemButton onClick={handleToggle}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            width: '100%',
            gap: 2,
          }}
        >
          {getStatusIcon(execution.status)}

          <Box sx={{ flex: 1 }}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 2,
                mb: 0.5,
              }}
            >
              <Typography variant="subtitle1" fontWeight="medium">
                Execution #{execution.execution_number}
              </Typography>
              <StatusBadge status={execution.status} size="small" />
            </Box>

            <Typography variant="body2" color="text.secondary">
              Started: {formatDate(execution.started_at)}
              {execution.completed_at &&
                ` • Completed: ${formatDate(execution.completed_at)}`}
              {execution.duration &&
                ` • Duration: ${formatDuration(execution.duration)}`}
            </Typography>
          </Box>

          {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </Box>
      </ListItemButton>

      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <Box sx={{ p: 3, pt: 2 }}>
          <Divider sx={{ mb: 2 }} />

          {/* Execution Details */}
          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid item xs={12} sm={6}>
              <Typography variant="body2" color="text.secondary">
                Execution ID
              </Typography>
              <Typography variant="body1">{execution.id}</Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Typography variant="body2" color="text.secondary">
                Status
              </Typography>
              <Typography variant="body1">
                {execution.status.charAt(0).toUpperCase() +
                  execution.status.slice(1)}
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Typography variant="body2" color="text.secondary">
                Started At
              </Typography>
              <Typography variant="body1">
                {formatDate(execution.started_at)}
              </Typography>
            </Grid>

            {execution.completed_at && (
              <Grid item xs={12} sm={6}>
                <Typography variant="body2" color="text.secondary">
                  Completed At
                </Typography>
                <Typography variant="body1">
                  {formatDate(execution.completed_at)}
                </Typography>
              </Grid>
            )}

            {execution.duration && (
              <Grid item xs={12} sm={6}>
                <Typography variant="body2" color="text.secondary">
                  Duration
                </Typography>
                <Typography variant="body1">
                  {formatDuration(execution.duration)}
                </Typography>
              </Grid>
            )}
          </Grid>

          {/* Metrics Summary */}
          {execution.metrics && (
            <>
              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle2" sx={{ mb: 2 }}>
                Performance Metrics
              </Typography>

              <Grid container spacing={2}>
                <Grid item xs={6} sm={4} md={3}>
                  <Typography variant="body2" color="text.secondary">
                    Total Return
                  </Typography>
                  <Typography
                    variant="body1"
                    fontWeight="medium"
                    color={
                      parseFloat(execution.metrics.total_return) >= 0
                        ? 'success.main'
                        : 'error.main'
                    }
                  >
                    {parseFloat(execution.metrics.total_return).toFixed(2)}%
                  </Typography>
                </Grid>

                <Grid item xs={6} sm={4} md={3}>
                  <Typography variant="body2" color="text.secondary">
                    Total P&L
                  </Typography>
                  <Typography
                    variant="body1"
                    fontWeight="medium"
                    color={
                      parseFloat(execution.metrics.total_pnl) >= 0
                        ? 'success.main'
                        : 'error.main'
                    }
                  >
                    ${parseFloat(execution.metrics.total_pnl).toFixed(2)}
                  </Typography>
                </Grid>

                <Grid item xs={6} sm={4} md={3}>
                  <Typography variant="body2" color="text.secondary">
                    Total Trades
                  </Typography>
                  <Typography variant="body1" fontWeight="medium">
                    {execution.metrics.total_trades}
                  </Typography>
                </Grid>

                <Grid item xs={6} sm={4} md={3}>
                  <Typography variant="body2" color="text.secondary">
                    Win Rate
                  </Typography>
                  <Typography variant="body1" fontWeight="medium">
                    {parseFloat(execution.metrics.win_rate).toFixed(2)}%
                  </Typography>
                </Grid>

                <Grid item xs={6} sm={4} md={3}>
                  <Typography variant="body2" color="text.secondary">
                    Max Drawdown
                  </Typography>
                  <Typography variant="body1" fontWeight="medium">
                    {parseFloat(execution.metrics.max_drawdown).toFixed(2)}%
                  </Typography>
                </Grid>

                {execution.metrics.sharpe_ratio && (
                  <Grid item xs={6} sm={4} md={3}>
                    <Typography variant="body2" color="text.secondary">
                      Sharpe Ratio
                    </Typography>
                    <Typography variant="body1" fontWeight="medium">
                      {parseFloat(execution.metrics.sharpe_ratio).toFixed(2)}
                    </Typography>
                  </Grid>
                )}

                {execution.metrics.profit_factor && (
                  <Grid item xs={6} sm={4} md={3}>
                    <Typography variant="body2" color="text.secondary">
                      Profit Factor
                    </Typography>
                    <Typography variant="body1" fontWeight="medium">
                      {parseFloat(execution.metrics.profit_factor).toFixed(2)}
                    </Typography>
                  </Grid>
                )}
              </Grid>
            </>
          )}

          {/* Error Details */}
          {execution.status === TaskStatus.FAILED &&
            execution.error_message && (
              <>
                <Divider sx={{ my: 2 }} />
                <Alert severity="error">
                  <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    Error Message
                  </Typography>
                  <Typography variant="body2">
                    {execution.error_message}
                  </Typography>

                  {execution.error_traceback && (
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="subtitle2" sx={{ mb: 1 }}>
                        Stack Trace
                      </Typography>
                      <Box
                        component="pre"
                        sx={{
                          p: 1,
                          bgcolor: 'grey.900',
                          color: 'grey.100',
                          borderRadius: 1,
                          overflow: 'auto',
                          fontSize: '0.75rem',
                          maxHeight: '200px',
                        }}
                      >
                        {execution.error_traceback}
                      </Box>
                    </Box>
                  )}
                </Alert>
              </>
            )}
        </Box>
      </Collapse>
    </Paper>
  );
}

export function TaskExecutionsTab({
  taskId,
  taskType = TaskType.BACKTEST,
}: TaskExecutionsTabProps) {
  const {
    data: executionsData,
    isLoading,
    error,
  } = useTaskExecutions(taskId, taskType);

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

  const executions = executionsData?.results || [];

  if (executions.length === 0) {
    return (
      <Box sx={{ px: 3 }}>
        <Alert severity="info">
          No execution history available. This task has not been executed yet.
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ px: 3 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Execution History
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {executions.length} execution{executions.length !== 1 ? 's' : ''}{' '}
          found
        </Typography>
      </Box>

      <List sx={{ p: 0 }}>
        {executions.map((execution) => (
          <ExecutionItem key={execution.id} execution={execution} />
        ))}
      </List>

      {/* Future: Add comparison functionality */}
      {executions.length > 1 && (
        <Box sx={{ mt: 3 }}>
          <Alert severity="info">
            <Typography variant="body2">
              <strong>Coming Soon:</strong> Compare multiple executions
              side-by-side to analyze performance differences.
            </Typography>
          </Alert>
        </Box>
      )}
    </Box>
  );
}
