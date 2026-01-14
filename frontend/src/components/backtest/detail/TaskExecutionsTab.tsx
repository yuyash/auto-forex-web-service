import { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';

import {
  Box,
  Paper,
  Typography,
  Alert,
  List,
  ListItemButton,
  CircularProgress,
  Pagination,
  Button,
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
  Tabs,
  Tab,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { Refresh as RefreshIcon } from '@mui/icons-material';
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  PlayArrow as PlayArrowIcon,
} from '@mui/icons-material';
import { useTaskExecutions } from '../../../hooks/useTaskExecutions';
import { useTaskLogs } from '../../../hooks/useTaskLogs';
import { StatusBadge } from '../../tasks/display/StatusBadge';
import { ErrorDisplay } from '../../tasks/display/ErrorDisplay';
import { ExecutionHistoryTable } from '../../tasks/display/ExecutionHistoryTable';
import { ExecutionComparisonView } from '../../tasks/display/ExecutionComparisonView';
import { TaskStatus, TaskType } from '../../../types/common';
import type { TaskExecution, ExecutionLog } from '../../../types/execution';

interface TaskExecutionsTabProps {
  taskId: number;
  taskType?: TaskType;
  taskStatus?: TaskStatus;
  task?: {
    start_time: string;
    end_time: string;
  };
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
  taskType,
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

            {/* Show progress bar for running backtest executions only */}
            {execution.status === TaskStatus.RUNNING &&
              taskType === TaskType.BACKTEST && (
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
  task,
}: TaskExecutionsTabProps) {
  const navigate = useNavigate();
  const [tabValue, setTabValue] = useState(0); // 0 = History, 1 = Logs, 2 = Compare
  const [selectedExecution, setSelectedExecution] =
    useState<TaskExecution | null>(null);
  const [executionsPage, setExecutionsPage] = useState(1);
  const executionsPageSize = 20;
  const [selectedComparisonIds, setSelectedComparisonIds] = useState<number[]>([]);

  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const logsContainerRef = useRef<HTMLDivElement>(null);
  const isUserScrollingRef = useRef(false);

  const [logsPage, setLogsPage] = useState(1);
  const logsPageSize = 100;

  const {
    data: executionsData,
    isLoading,
    error,
    refetch: refetchExecutions,
  } = useTaskExecutions(
    taskId,
    taskType,
    { page: executionsPage, page_size: executionsPageSize },
    {
      enablePolling: true,
      pollingInterval: 3000, // Poll every 3 seconds for running executions
    }
  );

  const executions = useMemo(
    () => executionsData?.results || [],
    [executionsData?.results]
  );

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

  // Note: WebSocket log streaming has been removed.
  // Logs are now fetched via HTTP API and stored in the database.

  const logInitialParams = useMemo(
    () => ({
      page: logsPage,
      page_size: logsPageSize,
      execution_id: selectedExecution?.id,
    }),
    [selectedExecution?.id, logsPage, logsPageSize]
  );

  const {
    logs: allLogs,
    totalCount: totalLogsCount,
    isLoading: isLogsLoading,
    error: logsError,
    refresh: refreshLogs,
  } = useTaskLogs(taskId, taskType as unknown as 'backtest' | 'trading', {
    enabled: Boolean(selectedExecution?.id),
    autoRefresh: selectedExecution?.status === TaskStatus.RUNNING,
    refreshInterval: 3000,
    initialParams: logInitialParams,
  });

  // Reset logs pagination when changing execution
  useEffect(() => {
    setLogsPage(1);
  }, [selectedExecution?.id]);

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

  // Keep the selected execution details up to date (status/progress/etc)
  useEffect(() => {
    const currentExecutionId = selectedExecution?.id;
    if (currentExecutionId && executions.length > 0) {
      const updatedExecution = executions.find(
        (exec) => exec.id === currentExecutionId
      );
      if (updatedExecution) {
        setSelectedExecution(updatedExecution);
      }
    }
  }, [executions, selectedExecution?.id]);

  const handleExecutionClick = (executionId: number) => {
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

  const totalExecutionPages = executionsData
    ? Math.ceil(executionsData.count / executionsPageSize)
    : 0;

  const totalLogPages = totalLogsCount
    ? Math.ceil(totalLogsCount / logsPageSize)
    : 0;

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

      {/* Tabs for History, Logs, and Compare */}
      <Paper sx={{ mb: 2 }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          aria-label="execution tabs"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label="History" />
          <Tab label="Logs" />
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

      {/* Logs Tab */}
      {tabValue === 1 && (
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

            {totalExecutionPages > 1 && (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
                <Pagination
                  count={totalExecutionPages}
                  page={executionsPage}
                  onChange={(_e, value) => {
                    setExecutionsPage(value);
                    setSelectedExecution(null);
                  }}
                  size="small"
                />
              </Box>
            )}
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
                      </Typography>
                      <Box
                        sx={{
                          mt: 0.5,
                          display: 'flex',
                          gap: 1,
                          alignItems: 'center',
                          flexWrap: 'wrap',
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

                        <Typography variant="caption" color="text.secondary">
                          Execution ID: {selectedExecution.id}
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
                          onClick={() => {
                            refetchExecutions();
                            refreshLogs();
                          }}
                          aria-label="Refresh logs"
                        >
                          <RefreshIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Typography variant="caption" color="text.secondary">
                        {totalLogsCount}{' '}
                        {totalLogsCount === 1 ? 'entry' : 'entries'}
                      </Typography>
                    </Box>
                  </Box>

                  {totalLogPages > 1 && (
                    <Box
                      sx={{
                        mt: 1,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 1,
                        flexWrap: 'wrap',
                      }}
                    >
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Button
                          size="small"
                          variant="outlined"
                          disabled={logsPage <= 1 || isLogsLoading}
                          onClick={() => setLogsPage((p) => Math.max(1, p - 1))}
                        >
                          Newer
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          disabled={logsPage >= totalLogPages || isLogsLoading}
                          onClick={() =>
                            setLogsPage((p) => Math.min(totalLogPages, p + 1))
                          }
                        >
                          Older
                        </Button>
                      </Box>

                      <Pagination
                        count={totalLogPages}
                        page={logsPage}
                        onChange={(_e, value) => setLogsPage(value)}
                        size="small"
                      />
                    </Box>
                  )}
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
                  {logsError ? (
                    <Box sx={{ p: 2 }}>
                      <ErrorDisplay
                        error={logsError}
                        title="Failed to load logs"
                      />
                    </Box>
                  ) : allLogs.length > 0 ? (
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
                        {isLogsLoading
                          ? 'Loading logs...'
                          : selectedExecution.status === TaskStatus.RUNNING
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
      )}

      {/* Compare Tab */}
      {tabValue === 2 && (
        <ExecutionComparisonView
          executions={executions}
          selectedExecutionIds={selectedComparisonIds}
          onSelectionChange={setSelectedComparisonIds}
        />
      )}
    </Box>
  );
}
