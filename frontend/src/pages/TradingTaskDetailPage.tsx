import { useState, useEffect, useRef } from 'react';
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
  IconButton,
  Button,
  Alert,
  Menu,
  MenuItem,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  ContentCopy as ContentCopyIcon,
  Edit as EditIcon,
  MoreVert as MoreVertIcon,
} from '@mui/icons-material';
import { useTradingTask } from '../hooks/useTradingTasks';
import {
  useStartTradingTask,
  useStopTradingTask,
  useResumeTradingTask,
  useRestartTradingTask,
  useRerunTradingTask,
  useCopyTradingTask,
  useDeleteTradingTask,
} from '../hooks/useTradingTaskMutations';
import { useTaskPolling } from '../hooks/useTaskPolling';
import { useInvalidateExecutions } from '../hooks/useTaskExecutions';
import { StatusBadge } from '../components/tasks/display/StatusBadge';
import { ErrorDisplay } from '../components/tasks/display/ErrorDisplay';
import { TaskActionButtons } from '../components/tasks/actions/TaskActionButtons';
import { CopyTaskDialog } from '../components/tasks/actions/CopyTaskDialog';
import { DeleteTaskDialog } from '../components/tasks/actions/DeleteTaskDialog';
import {
  StopOptionsDialog,
  type StopOption,
} from '../components/tasks/actions/StopOptionsDialog';
import { RestartOptionsDialog } from '../components/tasks/actions/RestartOptionsDialog';
import { LiveTaskTab } from '../components/trading/detail/LiveTaskTab';
import { TaskPerformanceTab } from '../components/trading/detail/TaskPerformanceTab';
import { useStrategies, getStrategyDisplayName } from '../hooks/useStrategies';
import { TaskExecutionsTab } from '../components/backtest/detail/TaskExecutionsTab';
import { TradingTaskConfigTab } from '../components/trading/detail/TradingTaskConfigTab';
import { TaskStatus, TaskType } from '../types/common';

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

export default function TradingTaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const taskId = parseInt(id || '0', 10);

  const [tabValue, setTabValue] = useState(2); // Default to Executions tab (index 2)
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [copyDialogOpen, setCopyDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [stopDialogOpen, setStopDialogOpen] = useState(false);
  const [restartDialogOpen, setRestartDialogOpen] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);

  const { data: task, isLoading, error, refetch } = useTradingTask(taskId);
  const { strategies } = useStrategies();

  // Use HTTP polling for task status updates (Requirements 1.2, 1.3, 4.3, 4.4)
  const { status: polledStatus } = useTaskPolling(taskId, 'trading', {
    enabled: !!taskId,
    pollStatus: true,
    interval: 3000, // Poll every 3 seconds for active tasks
  });

  // Refetch when status changes
  const prevStatusRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (polledStatus) {
      console.log('[TradingTaskDetail] Polled status update:', polledStatus);

      // Always clear transitioning state when polled status shows task is not running
      // This handles cases where task stops externally (e.g., stream error)
      if (
        polledStatus.status === TaskStatus.STOPPED ||
        polledStatus.status === TaskStatus.CREATED ||
        polledStatus.status === TaskStatus.FAILED ||
        polledStatus.status === TaskStatus.COMPLETED
      ) {
        setIsTransitioning(false);
      }

      if (
        task &&
        prevStatusRef.current &&
        polledStatus.status !== prevStatusRef.current
      ) {
        console.log('[TradingTaskDetail] Status changed, refetching task data');
        refetch().then(() => {
          setIsTransitioning(false);
        });
      }
      prevStatusRef.current = polledStatus.status;
    }
  }, [polledStatus, task, refetch]);

  // Refetch task data after mutations complete
  useEffect(() => {
    const handleMutationSuccess = () => {
      refetch();
    };

    // Listen for custom events from mutations
    window.addEventListener('trading-task-mutated', handleMutationSuccess);
    return () => {
      window.removeEventListener('trading-task-mutated', handleMutationSuccess);
    };
  }, [refetch]);

  const startTask = useStartTradingTask();
  const stopTask = useStopTradingTask();
  const resumeTask = useResumeTradingTask();
  const restartTask = useRestartTradingTask();
  const rerunTask = useRerunTradingTask();
  const copyTask = useCopyTradingTask();
  const deleteTask = useDeleteTradingTask();
  const { invalidateTradingExecutions } = useInvalidateExecutions();

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleBack = () => {
    navigate('/trading-tasks');
  };

  const handleEdit = () => {
    navigate(`/trading-tasks/${taskId}/edit`);
    handleMenuClose();
  };

  const handleStart = async () => {
    console.log('[TradingTask] Starting task:', {
      taskId,
      taskName: task?.name,
    });
    try {
      setIsTransitioning(true); // Optimistic update (Requirement 3.1)
      const result = await startTask.mutate(taskId);
      console.log('[TradingTask] Start task response:', result);
      await refetch(); // Force immediate refetch to show updated status
      invalidateTradingExecutions(taskId); // Refresh executions list
      handleMenuClose();
    } catch (error) {
      console.error('[TradingTask] Failed to start task:', error);
      // Error handled by mutation hook
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleResume = async () => {
    console.log('[TradingTask] Resuming task:', {
      taskId,
      taskName: task?.name,
    });
    try {
      setIsTransitioning(true);
      const result = await resumeTask.mutate(taskId);
      console.log('[TradingTask] Resume task response:', result);
      await refetch();
      invalidateTradingExecutions(taskId);
      handleMenuClose();
    } catch (error) {
      console.error('[TradingTask] Failed to resume task:', error);
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleRestart = () => {
    setRestartDialogOpen(true);
    handleMenuClose();
  };

  const handleRestartConfirm = async (clearState: boolean) => {
    console.log('[TradingTask] Restarting task:', {
      taskId,
      taskName: task?.name,
      clearState,
    });
    try {
      setIsTransitioning(true);
      const result = await restartTask.mutate({ id: taskId, clearState });
      console.log('[TradingTask] Restart task response:', result);
      await refetch();
      invalidateTradingExecutions(taskId);
      setRestartDialogOpen(false);
    } catch (error) {
      console.error('[TradingTask] Failed to restart task:', error);
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleRerun = async () => {
    console.log('[TradingTask] Rerunning task:', {
      taskId,
      taskName: task?.name,
    });
    try {
      setIsTransitioning(true); // Optimistic update (Requirement 3.1)
      const result = await rerunTask.mutate(taskId);
      console.log('[TradingTask] Rerun task response:', result);
      // Force immediate refetch after mutation completes
      await refetch();
      invalidateTradingExecutions(taskId); // Refresh executions list
      handleMenuClose();
    } catch (error) {
      console.error('[TradingTask] Failed to rerun task:', error);
      // Error handled by mutation hook
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleCopy = () => {
    setCopyDialogOpen(true);
    handleMenuClose();
  };

  const handleCopyConfirm = async (newName: string) => {
    try {
      const newTask = await copyTask.mutate({
        id: taskId,
        data: { new_name: newName },
      });
      navigate(`/trading-tasks/${newTask.id}`);
    } catch {
      // Error handled by mutation hook
    }
  };

  const handleDelete = () => {
    setDeleteDialogOpen(true);
    handleMenuClose();
  };

  const handleDeleteConfirm = async () => {
    try {
      setIsTransitioning(true);
      await deleteTask.mutate(taskId);
      navigate('/trading-tasks');
    } catch {
      // Error handled by mutation hook
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleStop = () => {
    setStopDialogOpen(true);
    handleMenuClose();
  };

  const handleStopConfirm = async (option: StopOption) => {
    console.log('[TradingTask] Stopping task:', {
      taskId,
      taskName: task?.name,
      stopMode: option,
    });
    try {
      setIsTransitioning(true);
      const result = await stopTask.mutate({ id: taskId, mode: option });
      console.log('[TradingTask] Stop task response:', result);
      await refetch(); // Force immediate refetch to show updated status
      invalidateTradingExecutions(taskId); // Refresh executions list
      setStopDialogOpen(false);
    } catch (error) {
      console.error('[TradingTask] Failed to stop task:', error);
      // Error handled by mutation hook
    } finally {
      setIsTransitioning(false);
    }
  };

  if (isLoading) {
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
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
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <ErrorDisplay
          error={error || new Error('Task not found')}
          title="Failed to load task"
        />
      </Container>
    );
  }

  // Use polled status if available, otherwise fall back to task status
  // This ensures UI reflects real-time status changes (e.g., external stops)
  const currentStatus = (polledStatus?.status as TaskStatus) || task.status;

  const canStop =
    currentStatus === TaskStatus.RUNNING || currentStatus === TaskStatus.PAUSED;
  const canEdit =
    currentStatus !== TaskStatus.RUNNING && currentStatus !== TaskStatus.PAUSED;
  const canDelete =
    currentStatus !== TaskStatus.RUNNING && currentStatus !== TaskStatus.PAUSED;

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
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

      {/* Live Trading Warning */}
      {currentStatus === TaskStatus.RUNNING && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          This task is actively trading with real money. Monitor carefully and
          use the emergency stop button if needed.
        </Alert>
      )}

      {/* Header */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
          <IconButton onClick={handleBack} sx={{ mt: -1 }}>
            <ArrowBackIcon />
          </IconButton>

          <Box sx={{ flex: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
              <Typography variant="h4" component="h1">
                {task.name}
              </Typography>
              <StatusBadge status={currentStatus} />
              {currentStatus === TaskStatus.RUNNING && (
                <Box
                  sx={{
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    bgcolor: 'success.main',
                    animation: 'pulse 2s infinite',
                    '@keyframes pulse': {
                      '0%, 100%': { opacity: 1 },
                      '50%': { opacity: 0.5 },
                    },
                  }}
                  title="Live"
                />
              )}
            </Box>

            <Typography variant="body2" color="text.secondary">
              Account: {task.account_name} • Configuration: {task.config_name} •
              Strategy: {getStrategyDisplayName(strategies, task.strategy_type)}
            </Typography>

            {task.description && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {task.description}
              </Typography>
            )}
          </Box>

          {isMobile ? (
            <IconButton onClick={handleMenuOpen}>
              <MoreVertIcon />
            </IconButton>
          ) : (
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {/* Use TaskActionButtons component (Requirement 4.5) */}
              <TaskActionButtons
                status={currentStatus}
                onStart={
                  currentStatus === TaskStatus.CREATED ? handleStart : undefined
                }
                onResume={handleResume}
                onRestart={handleRestart}
                onStop={handleStop}
                onRerun={handleRerun}
                onDelete={handleDelete}
                loading={isTransitioning}
                canResume={task.can_resume}
                hasOpenPositions={task.has_open_positions}
              />
              <Button
                variant="outlined"
                startIcon={<ContentCopyIcon />}
                onClick={handleCopy}
                size="small"
              >
                Copy
              </Button>
              {canEdit && (
                <Button
                  variant="outlined"
                  startIcon={<EditIcon />}
                  onClick={handleEdit}
                  size="small"
                >
                  Edit
                </Button>
              )}
            </Box>
          )}
        </Box>

        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleMenuClose}
        >
          {currentStatus === TaskStatus.CREATED && (
            <MenuItem onClick={handleStart}>Start</MenuItem>
          )}
          {task.can_resume && (
            <MenuItem onClick={handleResume}>Resume</MenuItem>
          )}
          {(currentStatus === TaskStatus.STOPPED ||
            currentStatus === TaskStatus.PAUSED ||
            currentStatus === TaskStatus.FAILED) && (
            <MenuItem onClick={handleRestart} sx={{ color: 'warning.main' }}>
              Restart
            </MenuItem>
          )}
          {canStop && (
            <MenuItem onClick={handleStop} sx={{ color: 'error.main' }}>
              Stop
            </MenuItem>
          )}
          <MenuItem onClick={handleRerun}>Rerun</MenuItem>
          <MenuItem onClick={handleCopy}>Copy</MenuItem>
          {canEdit && <MenuItem onClick={handleEdit}>Edit</MenuItem>}
          {canDelete && (
            <MenuItem onClick={handleDelete} sx={{ color: 'error.main' }}>
              Delete
            </MenuItem>
          )}
        </Menu>
      </Paper>

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          aria-label="task detail tabs"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label="Live" {...a11yProps(0)} />
          <Tab label="Performance" {...a11yProps(1)} />
          <Tab label="Executions" {...a11yProps(2)} />
          <Tab label="Configuration" {...a11yProps(3)} />
        </Tabs>

        <TabPanel value={tabValue} index={0}>
          <LiveTaskTab task={task} />
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <TaskPerformanceTab task={task} />
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          <TaskExecutionsTab taskId={taskId} taskType={TaskType.TRADING} />
        </TabPanel>

        <TabPanel value={tabValue} index={3}>
          <TradingTaskConfigTab task={task} />
        </TabPanel>
      </Paper>

      {/* Dialogs */}
      <CopyTaskDialog
        open={copyDialogOpen}
        taskName={task.name}
        onCancel={() => setCopyDialogOpen(false)}
        onConfirm={handleCopyConfirm}
        isLoading={copyTask.isLoading}
      />

      <DeleteTaskDialog
        open={deleteDialogOpen}
        taskName={task.name}
        taskStatus={task.status}
        onCancel={() => setDeleteDialogOpen(false)}
        onConfirm={handleDeleteConfirm}
        isLoading={deleteTask.isLoading}
      />

      <StopOptionsDialog
        open={stopDialogOpen}
        taskName={task.name}
        onCancel={() => setStopDialogOpen(false)}
        onConfirm={handleStopConfirm}
        isLoading={stopTask.isLoading}
      />

      <RestartOptionsDialog
        open={restartDialogOpen}
        taskName={task.name}
        hasOpenPositions={task.has_open_positions}
        openPositionsCount={task.open_positions_count}
        hasStrategyState={task.has_strategy_state}
        onCancel={() => setRestartDialogOpen(false)}
        onConfirm={handleRestartConfirm}
        isLoading={restartTask.isLoading}
      />
    </Container>
  );
}
