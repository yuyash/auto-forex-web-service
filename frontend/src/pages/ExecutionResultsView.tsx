// ExecutionResultsView page - displays complete execution results with all components
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Container,
  Box,
  Typography,
  Alert,
  Breadcrumbs,
  Link,
  Tabs,
  Tab,
  CircularProgress,
} from '@mui/material';
import {
  Home as HomeIcon,
  ArrowBack as BackIcon,
  Assessment as SummaryIcon,
  ShowChart as ChartIcon,
  List as TradesIcon,
  Timeline as TimelineIcon,
  Compare as CompareIcon,
} from '@mui/icons-material';
import { ExecutionSummaryCard } from '../components/tasks/display/ExecutionSummaryCard';
import { CompleteEquityChart } from '../components/tasks/charts/CompleteEquityChart';
import { TradeHistoryTable } from '../components/tasks/display/TradeHistoryTable';
import { EventTimeline } from '../components/tasks/display/EventTimeline';
import { MetricsComparisonPanel } from '../components/tasks/display/MetricsComparisonPanel';
import { useTaskExecutions } from '../hooks/useTaskExecutions';
import { apiClient } from '../services/api/client';
import { TaskType } from '../types';
import type {
  TaskExecution,
  EquityPoint,
  Trade,
  BacktestStrategyEvent,
} from '../types';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`results-tabpanel-${index}`}
      aria-labelledby={`results-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
}

export const ExecutionResultsView: React.FC = () => {
  const { taskType, taskId, executionId } = useParams<{
    taskType: string;
    taskId: string;
    executionId: string;
  }>();
  const navigate = useNavigate();

  const [currentTab, setCurrentTab] = useState(0);
  const [execution, setExecution] = useState<TaskExecution | null>(null);
  const [equityPoints, setEquityPoints] = useState<EquityPoint[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [events, setEvents] = useState<BacktestStrategyEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const parsedTaskId = taskId ? parseInt(taskId, 10) : null;
  const parsedExecutionId = executionId ? parseInt(executionId, 10) : null;
  const parsedTaskType =
    taskType === 'backtest' ? TaskType.BACKTEST : TaskType.TRADING;

  // Fetch all executions for comparison (only if we have taskId and taskType)
  const shouldFetchExecutions = parsedTaskId !== null && taskType !== undefined;
  const { data: executionsResponse } = useTaskExecutions(
    parsedTaskId || 0,
    parsedTaskType,
    { page_size: 10, include_metrics: true }
  );

  const executionsData = shouldFetchExecutions
    ? executionsResponse?.results || []
    : [];

  // Fetch execution details
  useEffect(() => {
    const fetchExecutionData = async () => {
      if (!parsedExecutionId) return;

      try {
        setLoading(true);
        setError(null);

        // Fetch execution details
        const execResponse = await apiClient.get<TaskExecution>(
          `/trading/executions/${parsedExecutionId}/`
        );

        console.log('Execution API response:', execResponse);
        console.log('Execution metrics:', execResponse.metrics);

        // If execution is still running, redirect to running task view
        if (
          execResponse.status === 'running' ||
          execResponse.status === 'paused'
        ) {
          // Get taskType and taskId from execution if not in URL
          const execTaskType =
            execResponse.task_type === 'backtest' ? 'backtest' : 'trading';
          const execTaskId = execResponse.task_id;

          if (execTaskType === 'backtest') {
            navigate(`/backtest-tasks/${execTaskId}/running`);
          } else {
            navigate(`/trading-tasks/${execTaskId}/running`);
          }
          return;
        }

        setExecution(execResponse);

        // Fetch equity points
        try {
          const equityResponse = await apiClient.get<{
            results: EquityPoint[];
          }>(`/trading/executions/${parsedExecutionId}/equity/`, {
            page_size: 10000,
          });
          setEquityPoints(equityResponse.results || []);
        } catch (err) {
          console.error('Failed to fetch equity points:', err);
        }

        // Fetch trades
        try {
          const tradesResponse = await apiClient.get<{
            results: Trade[];
          }>(`/trading/executions/${parsedExecutionId}/trades/`, {
            page_size: 10000,
          });
          setTrades(tradesResponse.results || []);
        } catch (err) {
          console.error('Failed to fetch trades:', err);
        }

        // Fetch events
        try {
          const eventsResponse = await apiClient.get<{
            results: BacktestStrategyEvent[];
          }>(`/trading/executions/${parsedExecutionId}/events/`, {
            page_size: 10000,
          });
          setEvents(eventsResponse.results || []);
        } catch (err) {
          console.error('Failed to fetch events:', err);
        }
      } catch (err) {
        const error = err as Error;
        setError(error.message || 'Failed to load execution data');
      } finally {
        setLoading(false);
      }
    };

    fetchExecutionData();
  }, [parsedExecutionId, navigate]);

  if (!parsedExecutionId) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Alert severity="error">Invalid execution ID</Alert>
      </Container>
    );
  }

  const handleBack = () => {
    // If we have taskType and taskId from URL, use them
    if (taskType && taskId) {
      if (taskType === 'backtest') {
        navigate(`/backtest-tasks/${taskId}`);
      } else {
        navigate(`/trading-tasks/${taskId}`);
      }
    } else if (execution) {
      // Otherwise, use execution data
      const execTaskType =
        execution.task_type === 'backtest' ? 'backtest' : 'trading';
      if (execTaskType === 'backtest') {
        navigate(`/backtest-tasks/${execution.task_id}`);
      } else {
        navigate(`/trading-tasks/${execution.task_id}`);
      }
    } else {
      // Fallback to dashboard
      navigate('/dashboard');
    }
  };

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
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
          {execution
            ? execution.task_type === 'backtest'
              ? 'Backtest Tasks'
              : 'Trading Tasks'
            : taskType === 'backtest'
              ? 'Backtest Tasks'
              : 'Trading Tasks'}
        </Link>
        <Typography color="text.primary">
          Execution #{parsedExecutionId} Results
        </Typography>
      </Breadcrumbs>

      {/* Page Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          {execution
            ? execution.task_type === 'backtest'
              ? 'Backtest'
              : 'Trading'
            : taskType === 'backtest'
              ? 'Backtest'
              : 'Trading'}{' '}
          Execution Results
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Complete results and analysis for execution #{parsedExecutionId}
        </Typography>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Loading State */}
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Main Content */}
      {!loading && execution && (
        <>
          {/* Tabs */}
          <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
            <Tabs
              value={currentTab}
              onChange={handleTabChange}
              aria-label="execution results tabs"
              variant="scrollable"
              scrollButtons="auto"
            >
              <Tab
                icon={<SummaryIcon />}
                label="Summary"
                iconPosition="start"
                id="results-tab-0"
                aria-controls="results-tabpanel-0"
              />
              <Tab
                icon={<ChartIcon />}
                label="Equity Curve"
                iconPosition="start"
                id="results-tab-1"
                aria-controls="results-tabpanel-1"
              />
              <Tab
                icon={<TradesIcon />}
                label="Trade History"
                iconPosition="start"
                id="results-tab-2"
                aria-controls="results-tabpanel-2"
              />
              <Tab
                icon={<TimelineIcon />}
                label="Event Timeline"
                iconPosition="start"
                id="results-tab-3"
                aria-controls="results-tabpanel-3"
              />
              {executionsData && executionsData.length > 1 && (
                <Tab
                  icon={<CompareIcon />}
                  label="Compare"
                  iconPosition="start"
                  id="results-tab-4"
                  aria-controls="results-tabpanel-4"
                />
              )}
            </Tabs>
          </Box>

          {/* Tab Panels */}
          <TabPanel value={currentTab} index={0}>
            <ExecutionSummaryCard execution={execution} />
          </TabPanel>

          <TabPanel value={currentTab} index={1}>
            <CompleteEquityChart
              equityPoints={equityPoints}
              height={600}
              isLoading={false}
            />
          </TabPanel>

          <TabPanel value={currentTab} index={2}>
            <TradeHistoryTable trades={trades} />
          </TabPanel>

          <TabPanel value={currentTab} index={3}>
            <EventTimeline events={events} isLoading={false} />
          </TabPanel>

          {executionsData && executionsData.length > 1 && (
            <TabPanel value={currentTab} index={4}>
              <MetricsComparisonPanel
                executions={executionsData.slice(0, 5)}
                title="Compare Recent Executions"
              />
            </TabPanel>
          )}
        </>
      )}
    </Container>
  );
};

export default ExecutionResultsView;
