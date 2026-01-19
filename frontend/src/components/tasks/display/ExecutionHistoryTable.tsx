import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Typography,
  Chip,
  CircularProgress,
  TextField,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  IconButton,
  Tooltip,
  useTheme,
} from '@mui/material';
import {
  Visibility as VisibilityIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useTaskExecutions } from '../../../hooks/useTaskExecutions';
import { StatusBadge } from './StatusBadge';
import { ErrorDisplay } from './ErrorDisplay';
import { TaskStatus, TaskType } from '../../../types/common';
import type { TaskExecution } from '../../../types/execution';

interface ExecutionHistoryTableProps {
  taskId: number;
  taskType: TaskType;
  onExecutionClick?: (executionId: number) => void;
}

export function ExecutionHistoryTable({
  taskId,
  taskType,
  onExecutionClick,
}: ExecutionHistoryTableProps) {
  const navigate = useNavigate();
  const theme = useTheme();

  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(20);
  const [statusFilter, setStatusFilter] = useState<TaskStatus | 'all'>('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const { data, isLoading, error, refetch } = useTaskExecutions(
    taskId,
    taskType,
    {
      page: page + 1, // API uses 1-based pagination
      page_size: rowsPerPage,
      include_metrics: true,
    },
    {
      enablePolling: true,
      pollingInterval: 5000,
    }
  );

  const executions = data?.results || [];
  const totalCount = data?.count || 0;

  // Filter executions by status and date range
  const filteredExecutions = executions.filter((execution) => {
    // Status filter
    if (statusFilter !== 'all' && execution.status !== statusFilter) {
      return false;
    }

    // Date range filter
    if (startDate) {
      const executionDate = new Date(execution.started_at);
      const filterStartDate = new Date(startDate);
      if (executionDate < filterStartDate) {
        return false;
      }
    }

    if (endDate) {
      const executionDate = new Date(execution.started_at);
      const filterEndDate = new Date(endDate);
      filterEndDate.setHours(23, 59, 59, 999); // End of day
      if (executionDate > filterEndDate) {
        return false;
      }
    }

    return true;
  });

  const handleChangePage = (_event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleExecutionClick = (execution: TaskExecution) => {
    if (onExecutionClick) {
      onExecutionClick(execution.id);
    } else {
      // If execution is running or paused, navigate to running task view
      if (
        execution.status === TaskStatus.RUNNING ||
        execution.status === TaskStatus.PAUSED
      ) {
        const taskTypeStr =
          taskType === TaskType.BACKTEST ? 'backtest' : 'trading';
        navigate(`/${taskTypeStr}-tasks/${taskId}/running`);
      } else {
        // Navigate to execution results view for completed/stopped/failed executions
        navigate(`/executions/${execution.id}/results`);
      }
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const formatDuration = (started: string, completed?: string) => {
    if (!completed) {
      return '-';
    }

    const start = new Date(started).getTime();
    const end = new Date(completed).getTime();
    const durationMs = end - start;

    const hours = Math.floor(durationMs / (1000 * 60 * 60));
    const minutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((durationMs % (1000 * 60)) / 1000);

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    } else {
      return `${seconds}s`;
    }
  };

  const formatMetric = (value: string | number | undefined) => {
    if (value === undefined || value === null) {
      return '-';
    }
    const num = typeof value === 'string' ? parseFloat(value) : value;
    return num.toFixed(2);
  };

  if (isLoading && executions.length === 0) {
    return (
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
    );
  }

  if (error) {
    return (
      <ErrorDisplay error={error} title="Failed to load execution history" />
    );
  }

  return (
    <Box>
      {/* Filters */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
        >
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel id="status-filter-label">Status</InputLabel>
            <Select
              labelId="status-filter-label"
              value={statusFilter}
              label="Status"
              onChange={(e) =>
                setStatusFilter(e.target.value as TaskStatus | 'all')
              }
            >
              <MenuItem value="all">All</MenuItem>
              <MenuItem value={TaskStatus.RUNNING}>Running</MenuItem>
              <MenuItem value={TaskStatus.COMPLETED}>Completed</MenuItem>
              <MenuItem value={TaskStatus.FAILED}>Failed</MenuItem>
              <MenuItem value={TaskStatus.STOPPED}>Stopped</MenuItem>
            </Select>
          </FormControl>

          <TextField
            label="Start Date"
            type="date"
            size="small"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ minWidth: 150 }}
          />

          <TextField
            label="End Date"
            type="date"
            size="small"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ minWidth: 150 }}
          />

          <Box sx={{ flex: 1 }} />

          <Tooltip title="Refresh">
            <IconButton onClick={() => refetch()} size="small">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Paper>

      {/* Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Execution #</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Started</TableCell>
              <TableCell>Duration</TableCell>
              <TableCell align="right">Return %</TableCell>
              <TableCell align="right">PnL</TableCell>
              <TableCell align="right">Trades</TableCell>
              <TableCell align="right">Win Rate</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredExecutions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} align="center">
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ py: 4 }}
                  >
                    No executions found
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              filteredExecutions.map((execution) => (
                <TableRow
                  key={execution.id}
                  hover
                  sx={{
                    cursor: 'pointer',
                    '&:hover': {
                      bgcolor: theme.palette.action.hover,
                    },
                  }}
                  onClick={() => handleExecutionClick(execution)}
                >
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      #{execution.execution_number}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={execution.status} size="small" />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {formatDate(execution.started_at)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {formatDuration(
                        execution.started_at,
                        execution.completed_at
                      )}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    {execution.metrics ? (
                      <Chip
                        label={`${formatMetric(execution.metrics.total_return)}%`}
                        size="small"
                        color={
                          parseFloat(execution.metrics.total_return) >= 0
                            ? 'success'
                            : 'error'
                        }
                        sx={{ minWidth: 70 }}
                      />
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        -
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell align="right">
                    {execution.metrics ? (
                      <Typography
                        variant="body2"
                        color={
                          parseFloat(execution.metrics.total_pnl) >= 0
                            ? 'success.main'
                            : 'error.main'
                        }
                      >
                        ${formatMetric(execution.metrics.total_pnl)}
                      </Typography>
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        -
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell align="right">
                    {execution.metrics ? (
                      <Typography variant="body2">
                        {execution.metrics.total_trades}
                      </Typography>
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        -
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell align="right">
                    {execution.metrics ? (
                      <Typography variant="body2">
                        {formatMetric(execution.metrics.win_rate)}%
                      </Typography>
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        -
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip title="View Details">
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleExecutionClick(execution);
                        }}
                      >
                        <VisibilityIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>

        <TablePagination
          rowsPerPageOptions={[10, 20, 50, 100]}
          component="div"
          count={totalCount}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </TableContainer>
    </Box>
  );
}
