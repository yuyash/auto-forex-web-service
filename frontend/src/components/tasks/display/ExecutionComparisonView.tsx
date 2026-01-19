import { useState, useMemo } from 'react';
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Button,
  Checkbox,
  Alert,
  Grid,
  Card,
  CardContent,
} from '@mui/material';
import {
  Compare as CompareIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import { StatusBadge } from './StatusBadge';
import type { TaskExecution } from '../../../types/execution';

interface ExecutionComparisonViewProps {
  executions: TaskExecution[];
  selectedExecutionIds: number[];
  onSelectionChange: (executionIds: number[]) => void;
  onClose?: () => void;
}

export function ExecutionComparisonView({
  executions,
  selectedExecutionIds,
  onSelectionChange,
  onClose,
}: ExecutionComparisonViewProps) {
  const [showOnlyDifferences, setShowOnlyDifferences] = useState(false);

  // Get selected executions with metrics
  const selectedExecutions = useMemo(() => {
    return executions
      .filter((exec) => selectedExecutionIds.includes(exec.id))
      .filter((exec) => exec.metrics); // Only include executions with metrics
  }, [executions, selectedExecutionIds]);

  const handleToggleExecution = (executionId: number) => {
    if (selectedExecutionIds.includes(executionId)) {
      onSelectionChange(
        selectedExecutionIds.filter((id) => id !== executionId)
      );
    } else {
      if (selectedExecutionIds.length < 5) {
        // Limit to 5 executions
        onSelectionChange([...selectedExecutionIds, executionId]);
      }
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const formatMetric = (value: string | number | undefined) => {
    if (value === undefined || value === null) {
      return '-';
    }
    const num = typeof value === 'string' ? parseFloat(value) : value;
    return num.toFixed(2);
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

  // Check if all values in a row are the same
  const areValuesSame = (values: (string | number | undefined)[]) => {
    const definedValues = values.filter((v) => v !== undefined && v !== null);
    if (definedValues.length === 0) return true;
    const first = String(definedValues[0]);
    return definedValues.every((v) => String(v) === first);
  };

  // Metric rows configuration
  const metricRows = [
    {
      label: 'Total Return',
      getValue: (exec: TaskExecution) => exec.metrics?.total_return,
      format: (v: string | number | undefined) => `${formatMetric(v)}%`,
      isPositive: (v: string | number | undefined) =>
        v !== undefined && parseFloat(String(v)) >= 0,
    },
    {
      label: 'Total PnL',
      getValue: (exec: TaskExecution) => exec.metrics?.total_pnl,
      format: (v: string | number | undefined) => `$${formatMetric(v)}`,
      isPositive: (v: string | number | undefined) =>
        v !== undefined && parseFloat(String(v)) >= 0,
    },
    {
      label: 'Realized PnL',
      getValue: (exec: TaskExecution) => exec.metrics?.realized_pnl,
      format: (v: string | number | undefined) => `$${formatMetric(v)}`,
      isPositive: (v: string | number | undefined) =>
        v !== undefined && parseFloat(String(v)) >= 0,
    },
    {
      label: 'Unrealized PnL',
      getValue: (exec: TaskExecution) => exec.metrics?.unrealized_pnl,
      format: (v: string | number | undefined) => `$${formatMetric(v)}`,
      isPositive: (v: string | number | undefined) =>
        v !== undefined && parseFloat(String(v)) >= 0,
    },
    {
      label: 'Total Trades',
      getValue: (exec: TaskExecution) => exec.metrics?.total_trades,
      format: (v: string | number | undefined) => String(v || '-'),
    },
    {
      label: 'Winning Trades',
      getValue: (exec: TaskExecution) => exec.metrics?.winning_trades,
      format: (v: string | number | undefined) => String(v || '-'),
    },
    {
      label: 'Losing Trades',
      getValue: (exec: TaskExecution) => exec.metrics?.losing_trades,
      format: (v: string | number | undefined) => String(v || '-'),
    },
    {
      label: 'Win Rate',
      getValue: (exec: TaskExecution) => exec.metrics?.win_rate,
      format: (v: string | number | undefined) => `${formatMetric(v)}%`,
    },
    {
      label: 'Max Drawdown',
      getValue: (exec: TaskExecution) => exec.metrics?.max_drawdown,
      format: (v: string | number | undefined) => `${formatMetric(v)}%`,
    },
    {
      label: 'Sharpe Ratio',
      getValue: (exec: TaskExecution) => exec.metrics?.sharpe_ratio,
      format: (v: string | number | undefined) => formatMetric(v),
    },
    {
      label: 'Profit Factor',
      getValue: (exec: TaskExecution) => exec.metrics?.profit_factor,
      format: (v: string | number | undefined) => formatMetric(v),
    },
    {
      label: 'Average Win',
      getValue: (exec: TaskExecution) => exec.metrics?.average_win,
      format: (v: string | number | undefined) => `$${formatMetric(v)}`,
    },
    {
      label: 'Average Loss',
      getValue: (exec: TaskExecution) => exec.metrics?.average_loss,
      format: (v: string | number | undefined) => `$${formatMetric(v)}`,
    },
  ];

  // Filter rows if showing only differences
  const displayedRows = showOnlyDifferences
    ? metricRows.filter((row) => {
        const values = selectedExecutions.map((exec) => row.getValue(exec));
        return !areValuesSame(values);
      })
    : metricRows;

  if (selectedExecutions.length === 0) {
    return (
      <Paper sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h6">Compare Executions</Typography>
          {onClose && (
            <Button startIcon={<CloseIcon />} onClick={onClose}>
              Close
            </Button>
          )}
        </Box>
        <Alert severity="info">
          Select 2-5 executions to compare their performance metrics
          side-by-side.
        </Alert>
      </Paper>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 2,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <CompareIcon />
            <Typography variant="h6">
              Comparing {selectedExecutions.length} Execution
              {selectedExecutions.length !== 1 ? 's' : ''}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              size="small"
              variant="outlined"
              onClick={() => setShowOnlyDifferences(!showOnlyDifferences)}
            >
              {showOnlyDifferences ? 'Show All' : 'Show Differences Only'}
            </Button>
            {onClose && (
              <Button
                size="small"
                variant="outlined"
                startIcon={<CloseIcon />}
                onClick={onClose}
              >
                Close
              </Button>
            )}
          </Box>
        </Box>

        {selectedExecutionIds.length >= 5 && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            Maximum of 5 executions can be compared at once.
          </Alert>
        )}
      </Paper>

      {/* Summary Cards */}
      <Grid container spacing={2} sx={{ mb: 2 }}>
        {selectedExecutions.map((execution) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={execution.id}>
            <Card>
              <CardContent>
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    mb: 1,
                  }}
                >
                  <Typography variant="h6">
                    Execution #{execution.execution_number}
                  </Typography>
                  <Checkbox
                    checked={selectedExecutionIds.includes(execution.id)}
                    onChange={() => handleToggleExecution(execution.id)}
                    size="small"
                  />
                </Box>
                <StatusBadge status={execution.status} size="small" />
                <Typography
                  variant="caption"
                  color="text.secondary"
                  display="block"
                  sx={{ mt: 1 }}
                >
                  {formatDate(execution.started_at)}
                </Typography>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  display="block"
                >
                  Duration:{' '}
                  {formatDuration(execution.started_at, execution.completed_at)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Comparison Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 'bold', minWidth: 150 }}>
                Metric
              </TableCell>
              {selectedExecutions.map((execution) => (
                <TableCell
                  key={execution.id}
                  align="center"
                  sx={{ fontWeight: 'bold' }}
                >
                  Execution #{execution.execution_number}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {/* Basic Info Section */}
            <TableRow>
              <TableCell
                colSpan={selectedExecutions.length + 1}
                sx={{ bgcolor: 'grey.100' }}
              >
                <Typography variant="subtitle2" fontWeight="bold">
                  Basic Information
                </Typography>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Status</TableCell>
              {selectedExecutions.map((execution) => (
                <TableCell key={execution.id} align="center">
                  <StatusBadge status={execution.status} size="small" />
                </TableCell>
              ))}
            </TableRow>
            <TableRow>
              <TableCell>Started</TableCell>
              {selectedExecutions.map((execution) => (
                <TableCell key={execution.id} align="center">
                  <Typography variant="body2">
                    {formatDate(execution.started_at)}
                  </Typography>
                </TableCell>
              ))}
            </TableRow>
            <TableRow>
              <TableCell>Duration</TableCell>
              {selectedExecutions.map((execution) => (
                <TableCell key={execution.id} align="center">
                  <Typography variant="body2">
                    {formatDuration(
                      execution.started_at,
                      execution.completed_at
                    )}
                  </Typography>
                </TableCell>
              ))}
            </TableRow>

            {/* Performance Metrics Section */}
            <TableRow>
              <TableCell
                colSpan={selectedExecutions.length + 1}
                sx={{ bgcolor: 'grey.100' }}
              >
                <Typography variant="subtitle2" fontWeight="bold">
                  Performance Metrics
                </Typography>
              </TableCell>
            </TableRow>
            {displayedRows.map((row, index) => {
              const values = selectedExecutions.map((exec) =>
                row.getValue(exec)
              );
              const allSame = areValuesSame(values);

              return (
                <TableRow
                  key={index}
                  sx={{
                    bgcolor:
                      allSame && showOnlyDifferences ? 'grey.50' : 'inherit',
                  }}
                >
                  <TableCell>{row.label}</TableCell>
                  {selectedExecutions.map((execution) => {
                    const value = row.getValue(execution);
                    const isPositive = row.isPositive
                      ? row.isPositive(value)
                      : undefined;

                    return (
                      <TableCell key={execution.id} align="center">
                        {isPositive !== undefined ? (
                          <Chip
                            label={row.format(value)}
                            size="small"
                            color={isPositive ? 'success' : 'error'}
                          />
                        ) : (
                          <Typography variant="body2">
                            {row.format(value)}
                          </Typography>
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      {showOnlyDifferences && displayedRows.length === 0 && (
        <Paper sx={{ p: 3, mt: 2 }}>
          <Alert severity="info">
            All metrics are identical across selected executions.
          </Alert>
        </Paper>
      )}
    </Box>
  );
}
