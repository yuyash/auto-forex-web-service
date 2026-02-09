/**
 * TradingTaskDetail Component
 *
 * Main detail view for trading tasks using task-based API endpoints.
 * Displays task info and tab navigation for Events, Logs, Trades, and Equity.
 *
 * Requirements: 11.14, 11.15
 */

import React, { useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
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
  Grid,
  Divider,
} from '@mui/material';
import { useTradingTask } from '../../hooks/useTradingTasks';
import { useToast } from '../common';
import { TaskControlButtons } from '../tasks/actions/TaskControlButtons';
import { TaskEventsTable } from '../tasks/detail/TaskEventsTable';
import { StatusBadge } from '../tasks/display/StatusBadge';
import { TaskLogsTable } from '../tasks/detail/TaskLogsTable';
import { TaskTradesTable } from '../tasks/detail/TaskTradesTable';
import { TaskEquityChart } from '../tasks/detail/TaskEquityChart';
import { TaskStatus, TaskType } from '../../types/common';

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

export const TradingTaskDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const taskId = id || '';
  const { showError } = useToast();

  // Get tab from URL, default to 'overview'
  const tabParam = searchParams.get('tab') || 'overview';
  const tabMap: Record<string, number> = {
    overview: 0,
    events: 1,
    logs: 2,
    trades: 3,
    equity: 4,
  };
  const tabNames = ['overview', 'events', 'logs', 'trades', 'equity'];
  const [tabValue, setTabValue] = useState(tabMap[tabParam] || 0);

  const { data: task, isLoading, error, refetch } = useTradingTask(taskId);

  // Derive tab value from URL parameter (use this for rendering)
  const currentTabValue =
    tabMap[tabParam] !== undefined ? tabMap[tabParam] : tabValue;

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
    // Update URL with tab name
    const tabName = tabNames[newValue];
    setSearchParams({ tab: tabName });
  };

  const handleBack = () => {
    navigate('/trading-tasks');
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
          Trading Tasks
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
              <StatusBadge status={task.status} />
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
              taskType={TaskType.TRADING}
              currentStatus={task.status}
              onSuccess={refetch}
              onError={(error) => showError(error.message)}
            />
          </Box>
        </Box>
      </Paper>

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={currentTabValue}
          onChange={handleTabChange}
          aria-label="task detail tabs"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label="Overview" {...a11yProps(0)} />
          <Tab label="Events" {...a11yProps(1)} />
          <Tab label="Logs" {...a11yProps(2)} />
          <Tab label="Trades" {...a11yProps(3)} />
          <Tab label="Equity" {...a11yProps(4)} />
        </Tabs>

        {/* Overview Tab */}
        <TabPanel value={currentTabValue} index={0}>
          <Box sx={{ p: 3 }}>
            <Grid container spacing={3}>
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography variant="h6" gutterBottom>
                  Task Information
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Name
                    </Typography>
                    <Typography variant="body1">{task.name}</Typography>
                  </Box>

                  {task.description && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Description
                      </Typography>
                      <Typography variant="body1">
                        {task.description}
                      </Typography>
                    </Box>
                  )}

                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Instrument
                    </Typography>
                    <Typography variant="body1">{task.instrument}</Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Pip Size
                    </Typography>
                    <Typography variant="body1">{task.pip_size}</Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Trading Mode
                    </Typography>
                    <Typography
                      variant="body1"
                      sx={{ textTransform: 'capitalize' }}
                    >
                      {task.trading_mode}
                    </Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Status
                    </Typography>
                    <Box sx={{ mt: 0.5 }}>
                      <StatusBadge
                        status={task.status}
                        size="small"
                        showIcon={false}
                      />
                    </Box>
                  </Box>
                </Box>
              </Grid>

              <Grid size={{ xs: 12, md: 6 }}>
                <Typography variant="h6" gutterBottom>
                  Configuration
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Strategy Configuration
                    </Typography>
                    <Link
                      component="button"
                      variant="body1"
                      onClick={() =>
                        navigate(`/configurations/${task.config_id}`)
                      }
                      sx={{ textAlign: 'left' }}
                    >
                      {task.config_name}
                    </Link>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Strategy Type
                    </Typography>
                    <Typography
                      variant="body1"
                      sx={{ textTransform: 'capitalize' }}
                    >
                      {task.strategy_type}
                    </Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      OANDA Account
                    </Typography>
                    <Typography variant="body1">
                      {task.oanda_account_name || 'N/A'}
                    </Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Sell on Stop
                    </Typography>
                    <Typography variant="body1">
                      {task.sell_on_stop ? 'Yes' : 'No'}
                    </Typography>
                  </Box>
                </Box>
              </Grid>

              {(task.started_at || task.completed_at) && (
                <Grid size={{ xs: 12 }}>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="h6" gutterBottom>
                    Execution Timeline
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {task.started_at && (
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Started At
                        </Typography>
                        <Typography variant="body1">
                          {new Date(task.started_at).toLocaleString()}
                        </Typography>
                      </Box>
                    )}
                    {task.completed_at && (
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Completed At
                        </Typography>
                        <Typography variant="body1">
                          {new Date(task.completed_at).toLocaleString()}
                        </Typography>
                      </Box>
                    )}
                  </Box>
                </Grid>
              )}
            </Grid>
          </Box>
        </TabPanel>

        {/* Task-based tab content */}
        <TabPanel value={currentTabValue} index={1}>
          <TaskEventsTable
            taskId={taskId}
            taskType={TaskType.TRADING}
            enableRealTimeUpdates={task.status === TaskStatus.RUNNING}
          />
        </TabPanel>

        <TabPanel value={currentTabValue} index={2}>
          <TaskLogsTable
            taskId={taskId}
            taskType={TaskType.TRADING}
            enableRealTimeUpdates={task.status === TaskStatus.RUNNING}
          />
        </TabPanel>

        <TabPanel value={currentTabValue} index={3}>
          <TaskTradesTable
            taskId={taskId}
            taskType={TaskType.TRADING}
            enableRealTimeUpdates={task.status === TaskStatus.RUNNING}
          />
        </TabPanel>

        <TabPanel value={currentTabValue} index={4}>
          <TaskEquityChart
            taskId={taskId}
            taskType={TaskType.TRADING}
            enableRealTimeUpdates={task.status === TaskStatus.RUNNING}
          />
        </TabPanel>
      </Paper>
    </Container>
  );
};

export default TradingTaskDetail;
