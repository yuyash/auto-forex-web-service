// MetricsComparisonPanel component - compares metrics across multiple executions
import React, { useMemo } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Remove as NeutralIcon,
} from '@mui/icons-material';
import { formatCurrency, formatPercentage } from '../../../utils/formatters';
import type { TaskExecution } from '../../../types';

interface MetricsComparisonPanelProps {
  executions: TaskExecution[];
  title?: string;
}

interface MetricRow {
  label: string;
  key: string;
  format: (value: string | number | null | undefined) => string;
  higherIsBetter: boolean;
}

const metricRows: MetricRow[] = [
  {
    label: 'Total Return',
    key: 'total_return',
    format: (v) => formatPercentage(parseFloat(String(v || '0'))),
    higherIsBetter: true,
  },
  {
    label: 'Total P&L',
    key: 'total_pnl',
    format: (v) => formatCurrency(parseFloat(String(v || '0'))),
    higherIsBetter: true,
  },
  {
    label: 'Realized P&L',
    key: 'realized_pnl',
    format: (v) => formatCurrency(parseFloat(String(v || '0'))),
    higherIsBetter: true,
  },
  {
    label: 'Win Rate',
    key: 'win_rate',
    format: (v) => formatPercentage(parseFloat(String(v || '0'))),
    higherIsBetter: true,
  },
  {
    label: 'Total Trades',
    key: 'total_trades',
    format: (v) => String(v || '0'),
    higherIsBetter: false,
  },
  {
    label: 'Winning Trades',
    key: 'winning_trades',
    format: (v) => String(v || '0'),
    higherIsBetter: true,
  },
  {
    label: 'Losing Trades',
    key: 'losing_trades',
    format: (v) => String(v || '0'),
    higherIsBetter: false,
  },
  {
    label: 'Max Drawdown',
    key: 'max_drawdown',
    format: (v) => formatPercentage(Math.abs(parseFloat(String(v || '0')))),
    higherIsBetter: false,
  },
  {
    label: 'Sharpe Ratio',
    key: 'sharpe_ratio',
    format: (v) => (v ? parseFloat(String(v)).toFixed(2) : 'N/A'),
    higherIsBetter: true,
  },
  {
    label: 'Profit Factor',
    key: 'profit_factor',
    format: (v) => (v ? parseFloat(String(v)).toFixed(2) : 'N/A'),
    higherIsBetter: true,
  },
  {
    label: 'Average Win',
    key: 'average_win',
    format: (v) => (v ? formatCurrency(parseFloat(String(v))) : 'N/A'),
    higherIsBetter: true,
  },
  {
    label: 'Average Loss',
    key: 'average_loss',
    format: (v) => (v ? formatCurrency(parseFloat(String(v))) : 'N/A'),
    higherIsBetter: false,
  },
];

export const MetricsComparisonPanel: React.FC<MetricsComparisonPanelProps> = ({
  executions,
  title = 'Execution Comparison',
}) => {
  // Calculate best/worst for each metric
  const metricComparison = useMemo(() => {
    const comparison: Record<
      string,
      { best: number; worst: number; values: number[] }
    > = {};

    metricRows.forEach((row) => {
      const values = executions
        .map((exec) => {
          const value = exec.metrics?.[row.key as keyof typeof exec.metrics];
          return value ? parseFloat(String(value)) : null;
        })
        .filter((v): v is number => v !== null);

      if (values.length > 0) {
        comparison[row.key] = {
          best: row.higherIsBetter ? Math.max(...values) : Math.min(...values),
          worst: row.higherIsBetter ? Math.min(...values) : Math.max(...values),
          values,
        };
      }
    });

    return comparison;
  }, [executions]);

  const getBadgeColor = (
    value: number | null,
    metricKey: string
  ): 'success' | 'error' | 'default' => {
    if (value === null || !metricComparison[metricKey]) return 'default';

    const { best, worst } = metricComparison[metricKey];

    if (value === best) return 'success';
    if (value === worst) return 'error';
    return 'default';
  };

  const getTrendIcon = (
    value: number | null,
    metricKey: string,
    higherIsBetter: boolean
  ) => {
    if (value === null || !metricComparison[metricKey])
      return <NeutralIcon fontSize="small" />;

    const { best, worst } = metricComparison[metricKey];

    if (value === best) {
      return higherIsBetter ? (
        <TrendingUpIcon fontSize="small" color="success" />
      ) : (
        <TrendingDownIcon fontSize="small" color="success" />
      );
    }
    if (value === worst) {
      return higherIsBetter ? (
        <TrendingDownIcon fontSize="small" color="error" />
      ) : (
        <TrendingUpIcon fontSize="small" color="error" />
      );
    }
    return <NeutralIcon fontSize="small" color="disabled" />;
  };

  if (executions.length === 0) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {title}
          </Typography>
          <Typography color="text.secondary">
            No executions available for comparison
          </Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>

        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Comparing {executions.length} execution
            {executions.length !== 1 ? 's' : ''}
          </Typography>
        </Box>

        <TableContainer component={Paper} variant="outlined">
          <Table size="small" sx={{ minWidth: 650 }}>
            <TableHead>
              <TableRow sx={{ bgcolor: 'background.default' }}>
                <TableCell sx={{ fontWeight: 'bold' }}>Metric</TableCell>
                {executions.map((exec) => (
                  <TableCell
                    key={exec.id}
                    align="center"
                    sx={{ fontWeight: 'bold' }}
                  >
                    <Box>
                      <Typography variant="body2" fontWeight="bold">
                        Execution #{exec.execution_number}
                      </Typography>
                      <Chip
                        label={exec.status}
                        size="small"
                        color={
                          exec.status === 'completed'
                            ? 'success'
                            : exec.status === 'failed'
                              ? 'error'
                              : 'default'
                        }
                        sx={{ mt: 0.5 }}
                      />
                    </Box>
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {metricRows.map((row) => (
                <TableRow
                  key={row.key}
                  sx={{
                    '&:nth-of-type(odd)': {
                      bgcolor: 'background.default',
                    },
                  }}
                >
                  <TableCell
                    component="th"
                    scope="row"
                    sx={{ fontWeight: 'medium' }}
                  >
                    {row.label}
                  </TableCell>
                  {executions.map((exec) => {
                    const value =
                      exec.metrics?.[row.key as keyof typeof exec.metrics];
                    // Skip if value is an array (equity_points, trades, events)
                    if (Array.isArray(value)) {
                      return (
                        <TableCell key={exec.id} align="center">
                          <Typography variant="body2" color="text.secondary">
                            N/A
                          </Typography>
                        </TableCell>
                      );
                    }
                    const numValue = value ? parseFloat(String(value)) : null;
                    const badgeColor = getBadgeColor(numValue, row.key);
                    const trendIcon = getTrendIcon(
                      numValue,
                      row.key,
                      row.higherIsBetter
                    );

                    return (
                      <TableCell key={exec.id} align="center">
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: 1,
                          }}
                        >
                          {trendIcon}
                          <Typography
                            variant="body2"
                            fontWeight={
                              badgeColor !== 'default' ? 'bold' : 'normal'
                            }
                            color={
                              badgeColor === 'success'
                                ? 'success.main'
                                : badgeColor === 'error'
                                  ? 'error.main'
                                  : 'text.primary'
                            }
                          >
                            {row.format(
                              value as string | number | null | undefined
                            )}
                          </Typography>
                        </Box>
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}

              {/* Execution Details */}
              <TableRow sx={{ bgcolor: 'background.default' }}>
                <TableCell
                  component="th"
                  scope="row"
                  sx={{ fontWeight: 'medium' }}
                >
                  Started
                </TableCell>
                {executions.map((exec) => (
                  <TableCell key={exec.id} align="center">
                    <Typography variant="body2">
                      {new Date(exec.started_at).toLocaleDateString()}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {new Date(exec.started_at).toLocaleTimeString()}
                    </Typography>
                  </TableCell>
                ))}
              </TableRow>

              <TableRow>
                <TableCell
                  component="th"
                  scope="row"
                  sx={{ fontWeight: 'medium' }}
                >
                  Completed
                </TableCell>
                {executions.map((exec) => (
                  <TableCell key={exec.id} align="center">
                    {exec.completed_at ? (
                      <>
                        <Typography variant="body2">
                          {new Date(exec.completed_at).toLocaleDateString()}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {new Date(exec.completed_at).toLocaleTimeString()}
                        </Typography>
                      </>
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        N/A
                      </Typography>
                    )}
                  </TableCell>
                ))}
              </TableRow>
            </TableBody>
          </Table>
        </TableContainer>

        {/* Legend */}
        <Box sx={{ mt: 2, display: 'flex', gap: 2, justifyContent: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <TrendingUpIcon fontSize="small" color="success" />
            <Typography variant="caption" color="text.secondary">
              Best Performance
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <TrendingDownIcon fontSize="small" color="error" />
            <Typography variant="caption" color="text.secondary">
              Worst Performance
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <NeutralIcon fontSize="small" color="disabled" />
            <Typography variant="caption" color="text.secondary">
              Average Performance
            </Typography>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};
