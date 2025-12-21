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
  Menu,
  MenuItem,
  Alert,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  ContentCopy as ContentCopyIcon,
  Edit as EditIcon,
  MoreVert as MoreVertIcon,
} from '@mui/icons-material';
import {
  useBacktestTask,
  invalidateBacktestTasksCache,
} from '../hooks/useBacktestTasks';
import {
  useStartBacktestTask,
  useStopBacktestTask,
  useCopyBacktestTask,
  useDeleteBacktestTask,
  useRerunBacktestTask,
} from '../hooks/useBacktestTaskMutations';
import { useTaskPolling } from '../hooks/useTaskPolling';
import { useInvalidateExecutions } from '../hooks/useTaskExecutions';
import { useBacktestResults } from '../hooks/useTaskResults';
import { StatusBadge } from '../components/tasks/display/StatusBadge';
import { ErrorDisplay } from '../components/tasks/display/ErrorDisplay';
import { TaskActionButtons } from '../components/tasks/actions/TaskActionButtons';
import { TaskOverviewTab } from '../components/backtest/detail/TaskOverviewTab';
import { TaskResultsTab } from '../components/backtest/detail/TaskResultsTab';
import { TaskExecutionsTab } from '../components/backtest/detail/TaskExecutionsTab';
import { TaskConfigTab } from '../components/backtest/detail/TaskConfigTab';
import { CopyTaskDialog } from '../components/tasks/actions/CopyTaskDialog';
import { DeleteTaskDialog } from '../components/tasks/actions/DeleteTaskDialog';
import { TaskStatus } from '../types/common';
import { useStrategies, getStrategyDisplayName } from '../hooks/useStrategies';

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

export default function BacktestTaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const taskId = parseInt(id || '0', 10);

  const [tabValue, setTabValue] = useState(0); // Default to Overview tab (index 0)
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [copyDialogOpen, setCopyDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [progress, setProgress] = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: task, isLoading, error, refetch } = useBacktestTask(taskId);
  const { strategies } = useStrategies();

  // Use HTTP polling for task status updates (Requirements 1.2, 1.3, 4.3, 4.4)
  const { status: polledStatus, refetch: refetchPolledStatus } = useTaskPolling(
    taskId,
    'backtest',
    {
      enabled: !!taskId,
      pollStatus: true,
      interval: 3000, // Poll every 3 seconds for active tasks
    }
  );

  // Merge status sources (detail endpoint vs /status/ polling).
  // Prefer the polled status when it disagrees so the UI updates immediately
  // on stop/complete/fail transitions.
  const currentStatus =
    task && polledStatus && polledStatus.status !== task.status
      ? polledStatus.status
      : task?.status;

  // Poll for live results when task is running
  const { results } = useBacktestResults(taskId, currentStatus, {
    interval: 5000, // Poll every 5 seconds for live results
  });

  // Refetch when status changes
  const prevStatusRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (polledStatus) {
      console.log('[BacktestTaskDetail] Polled status update:', polledStatus);

      if (
        task &&
        prevStatusRef.current &&
        polledStatus.status !== prevStatusRef.current
      ) {
        console.log(
          '[BacktestTaskDetail] Status changed from',
          prevStatusRef.current,
          'to',
          polledStatus.status,
          '- refetching task data'
        );
        refetch().then(() => {
          setIsTransitioning(false);
        });
      }
      prevStatusRef.current = polledStatus.status;
    }
  }, [polledStatus, task, refetch]);

  // Also refetch when task transitions to RUNNING (new execution started)
  useEffect(() => {
    if (task && task.status === TaskStatus.RUNNING && progress === 100) {
      console.log(
        '[BacktestTaskDetail] Task is RUNNING but progress is 100%, refetching'
      );
      refetch();
    }
  }, [task, progress, refetch]);

  // Refetch task data after mutations complete
  useEffect(() => {
    const handleMutationSuccess = () => {
      refetch();
    };

    // Listen for custom events from mutations
    window.addEventListener('backtest-task-mutated', handleMutationSuccess);
    return () => {
      window.removeEventListener(
        'backtest-task-mutated',
        handleMutationSuccess
      );
    };
  }, [refetch]);

  const startTask = useStartBacktestTask();
  const stopTask = useStopBacktestTask();
  const rerunTask = useRerunBacktestTask();
  const copyTask = useCopyBacktestTask();
  const deleteTask = useDeleteBacktestTask();
  const { invalidateBacktestExecutions } = useInvalidateExecutions();

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
    navigate('/backtest-tasks');
  };

  const handleEdit = () => {
    navigate(`/backtest-tasks/${taskId}/edit`);
    handleMenuClose();
  };

  const handleStart = async () => {
    console.log('[BacktestTask] Starting task:', {
      taskId,
      taskName: task?.name,
    });
    try {
      setActionError(null);
      setIsTransitioning(true); // Optimistic update (Requirement 3.1)
      setProgress(0); // Reset progress when starting
      const result = await startTask.mutate(taskId);
      console.log('[BacktestTask] Start task response:', result);
      await refetch(); // Force immediate refetch to show updated status
      refetchPolledStatus(); // Ensure /status/ polling reflects the new run
      invalidateBacktestExecutions(taskId); // Refresh executions list
      handleMenuClose();
    } catch (error) {
      console.error('[BacktestTask] Failed to start task:', error);
      setActionError((error as Error).message);
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleStop = async () => {
    console.log('[BacktestTask] Stopping task:', {
      taskId,
      taskName: task?.name,
    });
    try {
      setActionError(null);
      setIsTransitioning(true); // Optimistic update (Requirement 3.1)
      const result = await stopTask.mutate(taskId);
      console.log('[BacktestTask] Stop task response:', result);
      await refetch(); // Force immediate refetch to show updated status
      refetchPolledStatus();
      invalidateBacktestExecutions(taskId); // Refresh executions list
      handleMenuClose();
    } catch (error) {
      console.error('[BacktestTask] Failed to stop task:', error);
      setActionError((error as Error).message);
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleRerun = async () => {
    console.log('[BacktestTask] Rerunning task:', {
      taskId,
      taskName: task?.name,
    });
    try {
      setActionError(null);
      setIsTransitioning(true); // Optimistic update (Requirement 3.1)
      setProgress(0); // Reset progress when rerunning
      const result = await rerunTask.mutate(taskId);
      console.log('[BacktestTask] Rerun task response:', result);
      // Force immediate refetch after mutation completes
      await refetch();
      refetchPolledStatus();
      invalidateBacktestExecutions(taskId); // Refresh executions list
      handleMenuClose();
    } catch (error) {
      console.error('[BacktestTask] Failed to rerun task:', error);
      setActionError((error as Error).message);
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
      invalidateBacktestTasksCache(); // Refresh task list
      navigate(`/backtest-tasks/${newTask.id}`);
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
      invalidateBacktestTasksCache(); // Refresh task list
      navigate('/backtest-tasks');
    } catch {
      // Error handled by mutation hook
    } finally {
      setIsTransitioning(false);
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
        <ErrorDisplay
          error={error || new Error('Task not found')}
          title="Failed to load task"
        />
      </Container>
    );
  }

  const statusForActions = currentStatus ?? task.status;
  const taskForTabs = { ...task, status: statusForActions };
  const canStart =
    statusForActions === TaskStatus.CREATED ||
    statusForActions === TaskStatus.STOPPED;
  const canStop = statusForActions === TaskStatus.RUNNING;
  const canRerun =
    statusForActions === TaskStatus.COMPLETED ||
    statusForActions === TaskStatus.FAILED;
  const canEdit = statusForActions !== TaskStatus.RUNNING;
  const canDelete = statusForActions !== TaskStatus.RUNNING;

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
          <IconButton onClick={handleBack} sx={{ mt: -1 }}>
            <ArrowBackIcon />
          </IconButton>

          <Box sx={{ flex: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
              <Typography variant="h4" component="h1">
                {task.name}
              </Typography>
              <StatusBadge status={statusForActions} />
            </Box>

            <Typography variant="body2" color="text.secondary">
              Configuration: {task.config_name} • Strategy:{' '}
              {getStrategyDisplayName(strategies, task.strategy_type)}
            </Typography>

            {task.description && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {task.description}
              </Typography>
            )}

            {actionError && (
              <Box sx={{ mt: 2 }}>
                <Alert
                  severity="error"
                  onClose={() => setActionError(null)}
                  aria-label="Task action error"
                >
                  {actionError}
                </Alert>
              </Box>
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
                status={statusForActions}
                onStart={handleStart}
                onStop={handleStop}
                onRerun={handleRerun}
                onDelete={handleDelete}
                loading={isTransitioning}
              />
              <Button
                variant="outlined"
                startIcon={<ContentCopyIcon />}
                onClick={handleCopy}
              >
                Copy
              </Button>
              {canEdit && (
                <Button
                  variant="outlined"
                  startIcon={<EditIcon />}
                  onClick={handleEdit}
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
          {canStart && (
            <MenuItem onClick={handleStart} disabled={isTransitioning}>
              Start
            </MenuItem>
          )}
          {canStop && (
            <MenuItem onClick={handleStop} disabled={isTransitioning}>
              Stop
            </MenuItem>
          )}
          {canRerun && (
            <MenuItem onClick={handleRerun} disabled={isTransitioning}>
              Rerun
            </MenuItem>
          )}
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
          <Tab label="Overview" {...a11yProps(0)} />
          <Tab label="Results" {...a11yProps(1)} />
          <Tab label="Executions" {...a11yProps(2)} />
          <Tab label="Configuration" {...a11yProps(3)} />
        </Tabs>

        <TabPanel value={tabValue} index={0}>
          <TaskOverviewTab task={taskForTabs} results={results} />
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <TaskResultsTab task={taskForTabs} results={results} />
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          <TaskExecutionsTab
            taskId={taskId}
            taskStatus={statusForActions}
            task={{
              start_time: task.start_time,
              end_time: task.end_time,
            }}
          />
        </TabPanel>

        <TabPanel value={tabValue} index={3}>
          <TaskConfigTab task={taskForTabs} />
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
    </Container>
  );
}
