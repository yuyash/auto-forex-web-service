import { useState, useEffect, useRef } from 'react';

import {
  Box,
  Paper,
  Typography,
  Alert,
  List,
  ListItemButton,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Checkbox,
  FormControlLabel,
  Tooltip,
  IconButton,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { Refresh as RefreshIcon } from '@mui/icons-material';
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  PlayArrow as PlayArrowIcon,
} from '@mui/icons-material';
import { useTaskExecutions } from '../../../hooks/useTaskExecutions';
import { useTaskLogsWebSocket } from '../../../hooks/useTaskLogsWebSocket';
import { StatusBadge } from '../../tasks/display/StatusBadge';
import { ErrorDisplay } from '../../tasks/display/ErrorDisplay';
import { TaskStatus, TaskType } from '../../../types/common';
import type { TaskExecution, ExecutionLog } from '../../../types/execution';

interface TaskExecutionsTabProps {
  taskId: number;
  taskType?: TaskType;
  taskStatus?: TaskStatus;
}

interface ExecutionItemProps {
  execution: TaskExecution;
  taskId: number;
  taskType: TaskType;
  isSelected: boolean;
  onSelect: () => void;
}

function ExecutionItem({
  execution,
  isSelected,
  onSelect,
}: ExecutionItemProps) {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const getStatusIcon = (status: TaskStatus) => {
    switch (status) {
      case TaskStatus.COMPLETED:
        return <CheckCircleIcon color="success" fontSize="small" />;
      case TaskStatus.FAILED:
        return <ErrorIcon color="error" fontSize="small" />;
      case TaskStatus.RUNNING:
        return <PlayArrowIcon color="primary" fontSize="small" />;
      default:
        return null;
    }
  };

  return (
    <Paper
      variant="outlined"
      sx={{
        mb: 1,
        bgcolor: isSelected ? 'action.selected' : 'background.paper',
        cursor: 'pointer',
        '&:hover': {
          bgcolor: isSelected ? 'action.selected' : 'action.hover',
        },
      }}
    >
      <ListItemButton onClick={onSelect} selected={isSelected}>
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

            <Typography variant="caption" color="text.secondary">
              {formatDate(execution.started_at)}
            </Typography>

            {/* Show progress bar for running executions */}
            {execution.status === TaskStatus.RUNNING && (
              <Box
                sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1 }}
              >
                <Box sx={{ flex: 1, position: 'relative' }}>
                  <Box
                    sx={{
                      height: 4,
                      bgcolor: 'grey.200',
                      borderRadius: 1,
                      overflow: 'hidden',
                    }}
                  >
                    <Box
                      sx={{
                        height: '100%',
                        bgcolor: 'primary.main',
                        width: `${execution.progress || 0}%`,
                        transition: 'width 0.3s ease',
                      }}
                    />
                  </Box>
                </Box>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ minWidth: 40 }}
                >
                  {execution.progress || 0}%
                </Typography>
              </Box>
            )}
          </Box>
        </Box>
      </ListItemButton>
    </Paper>
  );
}

export function TaskExecutionsTab({
  taskId,
  taskType = TaskType.BACKTEST,
  taskStatus,
}: TaskExecutionsTabProps) {
  const [selectedExecution, setSelectedExecution] =
    useState<TaskExecution | null>(null);
  const [liveLogs, setLiveLogs] = useState<ExecutionLog[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const logsContainerRef = useRef<HTMLDivElement>(null);
  const isUserScrollingRef = useRef(false);

  const {
    data: executionsData,
    isLoading,
    error,
    refetch: refetchExecutions,
  } = useTaskExecutions(taskId, taskType);

  const executions = executionsData?.results || [];

  // Debug logging
  console.log('[TaskExecutionsTab] Task ID:', taskId);
  console.log('[TaskExecutionsTab] Task Type:', taskType);
  console.log('[TaskExecutionsTab] Executions Data:', executionsData);
  console.log('[TaskExecutionsTab] Executions:', executions);
  console.log('[TaskExecutionsTab] Loading:', isLoading);
  console.log('[TaskExecutionsTab] Error:', error);

  // Auto-select the most recent execution (only when executions first load)
  useEffect(() => {
    if (executions.length > 0 && !selectedExecution) {
      setSelectedExecution(executions[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [executions.length]);

  // Refetch executions when task status changes (e.g., after rerun)
  useEffect(() => {
    if (taskStatus) {
      refetchExecutions();
    }
  }, [taskStatus, refetchExecutions]);

  // Connect to WebSocket for live logs when an execution is selected and running
  // Only connect if we have a valid execution ID and the execution is actually running
  const shouldConnectToLogs =
    selectedExecution?.status === TaskStatus.RUNNING &&
    selectedExecution?.id !== undefined &&
    selectedExecution.id > 0;

  // Debug logging
  console.log('[TaskExecutionsTab] WebSocket connection status:', {
    selectedExecutionId: selectedExecution?.id,
    selectedExecutionStatus: selectedExecution?.status,
    shouldConnect: shouldConnectToLogs,
  });

  useTaskLogsWebSocket({
    taskType: taskType === TaskType.BACKTEST ? 'backtest' : 'trading',
    taskId,
    enabled: shouldConnectToLogs,
    onLog: (update) => {
      // Only add logs for the selected execution
      if (selectedExecution && update.execution_id === selectedExecution.id) {
        setLiveLogs((prev) => [...prev, update.log]);
      }
    },
  });

  // Track the last known log count to avoid infinite loops
  const lastLogCountRef = useRef<number>(0);

  // Combine stored logs with live logs
  const allLogs = selectedExecution
    ? selectedExecution.status === TaskStatus.RUNNING
      ? [...(selectedExecution.logs || []), ...liveLogs]
      : selectedExecution.logs || []
    : [];

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && !isUserScrollingRef.current && logsContainerRef.current) {
      logsContainerRef.current.scrollTop =
        logsContainerRef.current.scrollHeight;
    }
  }, [allLogs.length, autoScroll]);

  // Detect user scrolling to temporarily disable auto-scroll
  const handleScroll = () => {
    if (!logsContainerRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = logsContainerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;

    // If user scrolls away from bottom, mark as user scrolling
    if (!isAtBottom && autoScroll) {
      isUserScrollingRef.current = true;
    } else if (isAtBottom) {
      isUserScrollingRef.current = false;
    }
  };

  // Reset live logs when selection changes (using execution ID as key)
  const executionId = selectedExecution?.id;
  useEffect(() => {
    setLiveLogs([]);
    lastLogCountRef.current = selectedExecution?.logs?.length || 0;
  }, [executionId, selectedExecution?.logs?.length]);

  // Update selectedExecution when executions data changes (to get latest logs from API)
  useEffect(() => {
    const currentExecutionId = selectedExecution?.id;
    if (currentExecutionId && executions.length > 0) {
      const updatedExecution = executions.find(
        (exec) => exec.id === currentExecutionId
      );
      if (updatedExecution) {
        // Check if logs have been updated from the API
        const apiLogCount = updatedExecution.logs?.length || 0;

        if (apiLogCount > lastLogCountRef.current) {
          // API has new logs, update selectedExecution and clear liveLogs to avoid duplicates
          lastLogCountRef.current = apiLogCount;
          setSelectedExecution(updatedExecution);
          setLiveLogs([]);
        }
      }
    }
  }, [executions, selectedExecution?.id]);

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

  return (
    <Box sx={{ px: 3 }}>
      <Grid container spacing={3}>
        {/* Execution List */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Box sx={{ mb: 2 }}>
            <Typography variant="h6" sx={{ mb: 1 }}>
              Execution History
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {executions.length} execution{executions.length !== 1 ? 's' : ''}
            </Typography>
          </Box>

          <List sx={{ p: 0 }}>
            {executions.map((execution) => (
              <ExecutionItem
                key={execution.id}
                execution={execution}
                taskId={taskId}
                taskType={taskType}
                isSelected={selectedExecution?.id === execution.id}
                onSelect={() => setSelectedExecution(execution)}
              />
            ))}
          </List>
        </Grid>

        {/* Logs Panel */}
        <Grid size={{ xs: 12, md: 8 }}>
          {selectedExecution ? (
            <Paper
              variant="outlined"
              sx={{
                height: '100%',
                minHeight: '500px',
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <Box>
                    <Typography variant="h6">
                      Execution #{selectedExecution.execution_number} Logs
                      {selectedExecution.status === TaskStatus.RUNNING &&
                        liveLogs.length > 0 && (
                          <Typography
                            component="span"
                            variant="caption"
                            sx={{ ml: 1, color: 'success.main' }}
                          >
                            • Live
                          </Typography>
                        )}
                    </Typography>
                    <Box
                      sx={{
                        mt: 0.5,
                        display: 'flex',
                        gap: 1,
                        alignItems: 'center',
                      }}
                    >
                      <StatusBadge
                        status={selectedExecution.status}
                        size="small"
                      />
                      <Typography variant="caption" color="text.secondary">
                        Started:{' '}
                        {new Date(
                          selectedExecution.started_at
                        ).toLocaleString()}
                      </Typography>
                    </Box>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={autoScroll}
                          onChange={(e) => {
                            setAutoScroll(e.target.checked);
                            isUserScrollingRef.current = false;
                          }}
                          size="small"
                        />
                      }
                      label="Auto-scroll"
                      sx={{ mr: 0 }}
                    />
                    <Tooltip title="Refresh logs">
                      <IconButton
                        size="small"
                        onClick={() => refetchExecutions()}
                        aria-label="Refresh logs"
                      >
                        <RefreshIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Typography variant="caption" color="text.secondary">
                      {allLogs.length}{' '}
                      {allLogs.length === 1 ? 'entry' : 'entries'}
                    </Typography>
                  </Box>
                </Box>
              </Box>

              <Box
                ref={logsContainerRef}
                onScroll={handleScroll}
                sx={{
                  flex: 1,
                  overflow: 'auto',
                  '&::-webkit-scrollbar': {
                    width: '8px',
                  },
                  '&::-webkit-scrollbar-track': {
                    bgcolor: 'background.paper',
                  },
                  '&::-webkit-scrollbar-thumb': {
                    bgcolor: 'action.disabled',
                    borderRadius: '4px',
                    '&:hover': {
                      bgcolor: 'action.active',
                    },
                  },
                }}
              >
                {allLogs.length > 0 ? (
                  <TableContainer>
                    <Table size="small" stickyHeader>
                      <TableHead>
                        <TableRow>
                          <TableCell
                            sx={{
                              fontWeight: 'bold',
                              bgcolor: 'background.paper',
                              width: '140px',
                            }}
                          >
                            Timestamp
                          </TableCell>
                          <TableCell
                            sx={{
                              fontWeight: 'bold',
                              bgcolor: 'background.paper',
                              width: '100px',
                            }}
                          >
                            Level
                          </TableCell>
                          <TableCell
                            sx={{
                              fontWeight: 'bold',
                              bgcolor: 'background.paper',
                            }}
                          >
                            Message
                          </TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {allLogs.map((log: ExecutionLog, index: number) => (
                          <TableRow
                            key={index}
                            sx={{
                              '&:nth-of-type(odd)': {
                                bgcolor: 'grey.50',
                              },
                              '&:hover': {
                                bgcolor: 'action.hover',
                              },
                            }}
                          >
                            <TableCell
                              sx={{
                                fontFamily: 'monospace',
                                fontSize: '0.75rem',
                                color: 'text.secondary',
                              }}
                            >
                              {new Date(log.timestamp).toLocaleTimeString()}
                            </TableCell>
                            <TableCell
                              sx={{
                                fontFamily: 'monospace',
                                fontWeight: 'bold',
                                fontSize: '0.75rem',
                                color:
                                  log.level === 'ERROR'
                                    ? 'error.main'
                                    : log.level === 'WARNING'
                                      ? 'warning.main'
                                      : 'info.main',
                              }}
                            >
                              {log.level}
                            </TableCell>
                            <TableCell
                              sx={{
                                fontFamily: 'monospace',
                                fontSize: '0.875rem',
                                wordBreak: 'break-word',
                              }}
                            >
                              {log.message}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    <div ref={logsEndRef} />
                  </TableContainer>
                ) : (
                  <Box
                    sx={{
                      display: 'flex',
                      justifyContent: 'center',
                      alignItems: 'center',
                      height: '100%',
                      textAlign: 'center',
                      p: 2,
                    }}
                  >
                    <Typography variant="body2" color="text.secondary">
                      {selectedExecution.status === TaskStatus.RUNNING
                        ? 'Waiting for logs...'
                        : 'No logs available for this execution'}
                    </Typography>
                  </Box>
                )}
              </Box>
            </Paper>
          ) : (
            <Paper
              variant="outlined"
              sx={{
                height: '100%',
                minHeight: '500px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Typography variant="body2" color="text.secondary">
                Select an execution to view logs
              </Typography>
            </Paper>
          )}
        </Grid>
      </Grid>
    </Box>
  );
}
