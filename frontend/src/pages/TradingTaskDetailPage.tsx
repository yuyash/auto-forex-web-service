import { useState, useEffect } from 'react';
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
  PlayArrow,
  Stop as StopIcon,
  Pause as PauseIcon,
  PlayCircleOutline as ResumeIcon,
  Refresh as RefreshIcon,
  ContentCopy as ContentCopyIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  MoreVert as MoreVertIcon,
} from '@mui/icons-material';
import { useTradingTask } from '../hooks/useTradingTasks';
import {
  useStartTradingTask,
  useStopTradingTask,
  usePauseTradingTask,
  useResumeTradingTask,
  useRerunTradingTask,
  useCopyTradingTask,
  useDeleteTradingTask,
} from '../hooks/useTradingTaskMutations';
import { useTaskStatusWebSocket } from '../hooks/useTaskStatusWebSocket';
import { StatusBadge } from '../components/tasks/display/StatusBadge';
import { ErrorDisplay } from '../components/tasks/display/ErrorDisplay';
import { CopyTaskDialog } from '../components/tasks/actions/CopyTaskDialog';
import { DeleteTaskDialog } from '../components/tasks/actions/DeleteTaskDialog';
import { ConfirmDialog } from '../components/tasks/actions/ConfirmDialog';
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

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`task-tabpanel-${index}`}
      aria-labelledby={`task-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
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

  const [tabValue, setTabValue] = useState(0);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [copyDialogOpen, setCopyDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [emergencyStopDialogOpen, setEmergencyStopDialogOpen] = useState(false);

  const { data: task, isLoading, error, refetch } = useTradingTask(taskId);
  const { strategies } = useStrategies();

  // Listen to WebSocket updates for this task
  useTaskStatusWebSocket({
    onStatusUpdate: (update) => {
      // Refetch task data when this specific task's status changes
      if (update.task_id === taskId && update.task_type === 'trading') {
        console.log(
          '[TradingTaskDetail] Status update received, refetching task data'
        );
        refetch();
      }
    },
  });

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
  const pauseTask = usePauseTradingTask();
  const resumeTask = useResumeTradingTask();
  const rerunTask = useRerunTradingTask();
  const copyTask = useCopyTradingTask();
  const deleteTask = useDeleteTradingTask();

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
    try {
      await startTask.mutate(taskId);
      await refetch(); // Force immediate refetch to show updated status
      handleMenuClose();
    } catch {
      // Error handled by mutation hook
    }
  };

  const handlePause = async () => {
    try {
      await pauseTask.mutate(taskId);
      await refetch(); // Force immediate refetch to show updated status
      handleMenuClose();
    } catch {
      // Error handled by mutation hook
    }
  };

  const handleResume = async () => {
    try {
      await resumeTask.mutate(taskId);
      await refetch(); // Force immediate refetch to show updated status
      handleMenuClose();
    } catch {
      // Error handled by mutation hook
    }
  };

  const handleRerun = async () => {
    try {
      await rerunTask.mutate(taskId);
      // Force immediate refetch after mutation completes
      await refetch();
      handleMenuClose();
    } catch {
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
      await deleteTask.mutate(taskId);
      navigate('/trading-tasks');
    } catch {
      // Error handled by mutation hook
    }
  };

  const handleEmergencyStop = () => {
    setEmergencyStopDialogOpen(true);
  };

  const handleEmergencyStopConfirm = async () => {
    try {
      await stopTask.mutate(taskId);
      await refetch(); // Force immediate refetch to show updated status
      setEmergencyStopDialogOpen(false);
    } catch {
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
  const canPause = task.status === TaskStatus.RUNNING;
  const canResume = task.status === TaskStatus.PAUSED;
  const canEdit =
    task.status !== TaskStatus.RUNNING && task.status !== TaskStatus.PAUSED;
  const canDelete =
    task.status !== TaskStatus.RUNNING && task.status !== TaskStatus.PAUSED;

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
      {task.status === TaskStatus.RUNNING && (
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
              <StatusBadge status={task.status} />
              {task.status === TaskStatus.RUNNING && (
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
              {canStart && (
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<PlayArrow />}
                  onClick={handleStart}
                  disabled={startTask.isLoading}
                >
                  Start
                </Button>
              )}
              {canPause && (
                <Button
                  variant="contained"
                  color="warning"
                  startIcon={<PauseIcon />}
                  onClick={handlePause}
                  disabled={pauseTask.isLoading}
                >
                  Pause
                </Button>
              )}
              {canResume && (
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<ResumeIcon />}
                  onClick={handleResume}
                  disabled={resumeTask.isLoading}
                >
                  Resume
                </Button>
              )}
              {canStop && (
                <Button
                  variant="contained"
                  color="error"
                  startIcon={<StopIcon />}
                  onClick={handleEmergencyStop}
                >
                  Emergency Stop
                </Button>
              )}
              <Button
                variant="outlined"
                startIcon={<RefreshIcon />}
                onClick={handleRerun}
                disabled={rerunTask.isLoading}
              >
                Rerun
              </Button>
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
              {canDelete && (
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<DeleteIcon />}
                  onClick={handleDelete}
                >
                  Delete
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
          {canPause && <MenuItem onClick={handlePause}>Pause</MenuItem>}
          {canResume && <MenuItem onClick={handleResume}>Resume</MenuItem>}
          {canStop && (
            <MenuItem onClick={handleEmergencyStop}>Emergency Stop</MenuItem>
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

      <ConfirmDialog
        open={emergencyStopDialogOpen}
        title="Emergency Stop"
        message="Are you sure you want to immediately stop this trading task? All open positions will remain open and must be closed manually."
        confirmText="Emergency Stop"
        confirmColor="error"
        onCancel={() => setEmergencyStopDialogOpen(false)}
        onConfirm={handleEmergencyStopConfirm}
        isLoading={stopTask.isLoading}
      />
    </Container>
  );
}
