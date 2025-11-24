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
import { StatusBadge } from '../components/tasks/display/StatusBadge';
import { ErrorDisplay } from '../components/tasks/display/ErrorDisplay';
import { TaskActionButtons } from '../components/tasks/actions/TaskActionButtons';
import { TaskProgress } from '../components/tasks/TaskProgress';
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

  console.log(
    `[TabPanel] index=${index}, value=${value}, shouldRender=${value === index}`
  );

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

  const [tabValue, setTabValue] = useState(2); // Default to Executions tab (index 2)
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [copyDialogOpen, setCopyDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [progress, setProgress] = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(false);

  const { data: task, isLoading, error, refetch } = useBacktestTask(taskId);
  const { strategies } = useStrategies();

  // Use HTTP polling for task status updates (Requirements 1.2, 1.3, 4.3, 4.4)
  const { status: polledStatus } = useTaskPolling(taskId, 'backtest', {
    enabled: !!taskId,
    pollStatus: true,
    interval: 3000, // Poll every 3 seconds for active tasks
  });

  // Use polled progress directly (no local state needed)
  const currentProgress = polledStatus?.progress || progress;

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
          '[BacktestTaskDetail] Status changed, refetching task data'
        );
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
    try {
      setIsTransitioning(true); // Optimistic update (Requirement 3.1)
      setProgress(0); // Reset progress when starting
      await startTask.mutate(taskId);
      await refetch(); // Force immediate refetch to show updated status
      handleMenuClose();
    } catch {
      setIsTransitioning(false);
      // Error handled by mutation hook
    }
  };

  const handleStop = async () => {
    try {
      setIsTransitioning(true); // Optimistic update (Requirement 3.1)
      await stopTask.mutate(taskId);
      await refetch(); // Force immediate refetch to show updated status
      handleMenuClose();
    } catch {
      setIsTransitioning(false);
      // Error handled by mutation hook
    }
  };

  const handleRerun = async () => {
    try {
      setIsTransitioning(true); // Optimistic update (Requirement 3.1)
      setProgress(0); // Reset progress when rerunning
      await rerunTask.mutate(taskId);
      // Force immediate refetch after mutation completes
      await refetch();
      handleMenuClose();
    } catch {
      setIsTransitioning(false);
      // Error handled by mutation hook
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
      setIsTransitioning(false);
      // Error handled by mutation hook
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

  const canStart =
    task.status === TaskStatus.CREATED || task.status === TaskStatus.STOPPED;
  const canStop = task.status === TaskStatus.RUNNING;
  const canEdit = task.status !== TaskStatus.RUNNING;
  const canDelete = task.status !== TaskStatus.RUNNING;

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
              <StatusBadge status={task.status} />
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
          </Box>

          {isMobile ? (
            <IconButton onClick={handleMenuOpen}>
              <MoreVertIcon />
            </IconButton>
          ) : (
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {/* Use TaskActionButtons component (Requirement 4.5) */}
              <TaskActionButtons
                status={task.status}
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
          {canStart && <MenuItem onClick={handleStart}>Start</MenuItem>}
          {canStop && <MenuItem onClick={handleStop}>Stop</MenuItem>}
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

      {/* Progress Bar in full-width mode for detail page (Requirement 3.3) */}
      {task.status === TaskStatus.RUNNING && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <TaskProgress
            status={task.status}
            progress={currentProgress}
            compact={false}
            showPercentage={true}
          />
        </Paper>
      )}

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
          <TaskOverviewTab task={task} />
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <TaskResultsTab task={task} />
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          <TaskExecutionsTab
            taskId={taskId}
            taskStatus={task.status}
            task={{
              start_time: task.start_time,
              end_time: task.end_time,
            }}
          />
        </TabPanel>

        <TabPanel value={tabValue} index={3}>
          <TaskConfigTab task={task} />
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
