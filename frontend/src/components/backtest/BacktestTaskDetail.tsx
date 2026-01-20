/**
 * BacktestTaskDetail Component
 *
 * Main detail view for backtest tasks using execution-based API endpoints.
 * Uses ExecutionDataProvider to fetch execution_id and displays task info,
 * latest metrics, and tab navigation for Events, Logs, Trades, Equity, and Metrics.
 *
 * Requirements: 11.5, 11.6
 */

import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Paper,
  Typography,
  Tabs,
  Tab,
  Breadcrumbs,
  Link,
  CircularProgress,
  Alert,
  Chip,
} from '@mui/material';
import { useBacktestTask } from '../../hooks/useBacktestTasks';
import { ExecutionDataProvider, useToast } from '../common';
import { TaskControlButtons } from '../tasks/actions/TaskControlButtons';
import { EventsTable } from './detail/EventsTable';
import { LogsTable } from './detail/LogsTable';
import { TradesTable } from './detail/TradesTable';
import { EquityChart } from './detail/EquityChart';
import { MetricsChart } from './detail/MetricsChart';
import { TaskStatus, TaskType } from '../../types/common';
import { ExecutionsService } from '../../api/generated/services/ExecutionsService';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  if (value !== index) {
    return null;
  }

  return (
    <div
      role="tabpanel"
      id={`task-tabpanel-${index}`}
      aria-labelledby={`task-tab-${index}`}
      {...other}
    >
      <Box sx={{ py: 3 }}>{children}</Box>
    </div>
  );
}

function a11yProps(index: number) {
  return {
    id: `task-tab-${index}`,
    'aria-controls': `task-tabpanel-${index}`,
  };
}

interface LatestMetrics {
  realized_pnl: string;
  unrealized_pnl: string;
  total_pnl: string;
  open_positions: number;
  total_trades: number;
  timestamp: string;
}

export const BacktestTaskDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const taskId = parseInt(id || '0', 10);
  const { showError } = useToast();

  const [tabValue, setTabValue] = useState(0);
  const [latestMetrics, setLatestMetrics] = useState<LatestMetrics | null>(
    null
  );
  const [metricsLoading, setMetricsLoading] = useState(false);

  const { data: task, isLoading, error, refetch } = useBacktestTask(taskId);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleBack = () => {
    navigate('/backtest-tasks');
  };

  const fetchLatestMetrics = async (executionId: number) => {
    try {
      setMetricsLoading(true);
      const response =
        await ExecutionsService.getExecutionLatestMetrics(executionId);
      setLatestMetrics(response);
    } catch (err) {
      console.error('Failed to fetch latest metrics:', err);
      setLatestMetrics(null);
    } finally {
      setMetricsLoading(false);
    }
  };

  const getStatusColor = (
    status: TaskStatus
  ):
    | 'default'
    | 'primary'
    | 'secondary'
    | 'success'
    | 'error'
    | 'warning'
    | 'info' => {
    switch (status) {
      case TaskStatus.RUNNING:
        return 'primary';
      case TaskStatus.COMPLETED:
        return 'success';
      case TaskStatus.FAILED:
        return 'error';
      case TaskStatus.STOPPED:
        return 'warning';
      default:
        return 'default';
    }
  };

  if (isLoading) {
    return (
      <Container maxWidth={false} sx={{ py: 4 }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '400px',
          }}
        >
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (error || !task) {
    return (
      <Container maxWidth={false} sx={{ py: 4 }}>
        <Alert severity="error">{error?.message || 'Task not found'}</Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth={false} sx={{ py: 4 }}>
      {/* Breadcrumbs */}
      <Breadcrumbs sx={{ mb: 2 }}>
        <Link
          component="button"
          variant="body1"
          onClick={handleBack}
          sx={{ cursor: 'pointer', textDecoration: 'none' }}
        >
          Backtest Tasks
        </Link>
        <Typography color="text.primary">{task.name}</Typography>
      </Breadcrumbs>

      {/* Header */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
          <Box sx={{ flex: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
              <Typography variant="h4" component="h1">
                {task.name}
              </Typography>
              <Chip
                label={task.status}
                color={getStatusColor(task.status)}
                size="small"
              />
            </Box>

            <Typography variant="body2" color="text.secondary">
              Configuration: {task.config_name} • Strategy: {task.strategy_type}
            </Typography>

            {task.description && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {task.description}
              </Typography>
            )}
          </Box>

          <Box sx={{ display: 'flex', gap: 1 }}>
            <TaskControlButtons
              taskId={taskId}
              taskType={TaskType.BACKTEST}
              currentStatus={task.status}
              onSuccess={refetch}
              onError={(error) => showError(error.message)}
            />
          </Box>
        </Box>

        {/* Use ExecutionDataProvider to get execution_id */}
        <ExecutionDataProvider taskId={taskId} taskType={TaskType.BACKTEST}>
          {(executionId, isLoadingExecution) => (
            <Box sx={{ mt: 2 }}>
              {isLoadingExecution ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CircularProgress size={16} />
                  <Typography variant="body2" color="text.secondary">
                    Loading execution data...
                  </Typography>
                </Box>
              ) : executionId ? (
                <>
                  <Typography variant="body2" color="text.secondary">
                    Execution ID: {executionId}
                  </Typography>

                  {/* Fetch and display latest metrics */}
                  {!latestMetrics && !metricsLoading && (
                    <Box sx={{ mt: 1 }}>
                      <Link
                        component="button"
                        variant="body2"
                        onClick={() => fetchLatestMetrics(executionId)}
                      >
                        Load latest metrics
                      </Link>
                    </Box>
                  )}

                  {metricsLoading && (
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        mt: 1,
                      }}
                    >
                      <CircularProgress size={16} />
                      <Typography variant="body2" color="text.secondary">
                        Loading metrics...
                      </Typography>
                    </Box>
                  )}

                  {latestMetrics && (
                    <Box
                      sx={{ mt: 2, display: 'flex', gap: 3, flexWrap: 'wrap' }}
                    >
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Realized PnL
                        </Typography>
                        <Typography variant="body1" fontWeight="medium">
                          ${parseFloat(latestMetrics.realized_pnl).toFixed(2)}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Unrealized PnL
                        </Typography>
                        <Typography variant="body1" fontWeight="medium">
                          ${parseFloat(latestMetrics.unrealized_pnl).toFixed(2)}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Total PnL
                        </Typography>
                        <Typography variant="body1" fontWeight="medium">
                          ${parseFloat(latestMetrics.total_pnl).toFixed(2)}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Open Positions
                        </Typography>
                        <Typography variant="body1" fontWeight="medium">
                          {latestMetrics.open_positions}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Total Trades
                        </Typography>
                        <Typography variant="body1" fontWeight="medium">
                          {latestMetrics.total_trades}
                        </Typography>
                      </Box>
                    </Box>
                  )}
                </>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No execution data available
                </Typography>
              )}
            </Box>
          )}
        </ExecutionDataProvider>
      </Paper>

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          aria-label="task detail tabs"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label="Events" {...a11yProps(0)} />
          <Tab label="Logs" {...a11yProps(1)} />
          <Tab label="Trades" {...a11yProps(2)} />
          <Tab label="Equity" {...a11yProps(3)} />
          <Tab label="Metrics" {...a11yProps(4)} />
        </Tabs>

        {/* Use ExecutionDataProvider for tab content */}
        <ExecutionDataProvider taskId={taskId} taskType={TaskType.BACKTEST}>
          {(executionId) => (
            <>
              <TabPanel value={tabValue} index={0}>
                {executionId ? (
                  <EventsTable
                    executionId={executionId}
                    enableRealTimeUpdates={task.status === TaskStatus.RUNNING}
                  />
                ) : (
                  <Box sx={{ p: 3 }}>
                    <Alert severity="info">
                      No execution data available. Start the task to see events.
                    </Alert>
                  </Box>
                )}
              </TabPanel>

              <TabPanel value={tabValue} index={1}>
                {executionId ? (
                  <LogsTable
                    executionId={executionId}
                    enableRealTimeUpdates={task.status === TaskStatus.RUNNING}
                  />
                ) : (
                  <Box sx={{ p: 3 }}>
                    <Alert severity="info">
                      No execution data available. Start the task to see logs.
                    </Alert>
                  </Box>
                )}
              </TabPanel>

              <TabPanel value={tabValue} index={2}>
                {executionId ? (
                  <TradesTable
                    executionId={executionId}
                    enableRealTimeUpdates={task.status === TaskStatus.RUNNING}
                  />
                ) : (
                  <Box sx={{ p: 3 }}>
                    <Alert severity="info">
                      No execution data available. Start the task to see trades.
                    </Alert>
                  </Box>
                )}
              </TabPanel>

              <TabPanel value={tabValue} index={3}>
                {executionId ? (
                  <EquityChart
                    executionId={executionId}
                    enableRealTimeUpdates={task.status === TaskStatus.RUNNING}
                  />
                ) : (
                  <Box sx={{ p: 3 }}>
                    <Alert severity="info">
                      No execution data available. Start the task to see equity
                      chart.
                    </Alert>
                  </Box>
                )}
              </TabPanel>

              <TabPanel value={tabValue} index={4}>
                {executionId ? (
                  <MetricsChart
                    executionId={executionId}
                    enableRealTimeUpdates={task.status === TaskStatus.RUNNING}
                  />
                ) : (
                  <Box sx={{ p: 3 }}>
                    <Alert severity="info">
                      No execution data available. Start the task to see
                      metrics.
                    </Alert>
                  </Box>
                )}
              </TabPanel>
            </>
          )}
        </ExecutionDataProvider>
      </Paper>
    </Container>
  );
};

export default BacktestTaskDetail;
