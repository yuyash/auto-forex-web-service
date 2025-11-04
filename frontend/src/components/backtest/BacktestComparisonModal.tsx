import { useState, useEffect, useRef, useMemo } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Checkbox,
  FormControlLabel,
  Alert,
  Chip,
  Stack,
  Divider,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { createChart, type IChartApi, type Time } from 'lightweight-charts';
import type { Backtest, BacktestResult } from '../../types/backtest';

interface BacktestComparisonModalProps {
  open: boolean;
  onClose: () => void;
  backtests: Backtest[];
  onFetchResult: (backtestId: number) => Promise<BacktestResult>;
}

interface ComparisonData {
  backtest: Backtest;
  result: BacktestResult | null;
  selected: boolean;
  loading: boolean;
}

const BacktestComparisonModal = ({
  open,
  onClose,
  backtests,
  onFetchResult,
}: BacktestComparisonModalProps) => {
  const { t } = useTranslation(['backtest', 'common']);
  const chartRef = useRef<HTMLDivElement>(null);
  const [chart, setChart] = useState<IChartApi | null>(null);
  const [comparisonData, setComparisonData] = useState<ComparisonData[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Initialize comparison data from backtests
  const initialComparisonData = useMemo(() => {
    if (!open || backtests.length === 0) return [];
    return backtests
      .filter((bt) => bt.status === 'completed')
      .map((bt) => ({
        backtest: bt,
        result: null,
        selected: false,
        loading: false,
      }));
  }, [open, backtests]);

  // Reset comparison data when modal opens or backtests change
  useEffect(() => {
    if (open && initialComparisonData.length > 0) {
      setComparisonData(initialComparisonData);
      setError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Initialize chart
  useEffect(() => {
    if (!open || !chartRef.current) return;

    if (!chart) {
      const newChart = createChart(chartRef.current, {
        width: chartRef.current.clientWidth,
        height: 400,
        layout: {
          background: { color: '#ffffff' },
          textColor: '#333',
        },
        grid: {
          vertLines: { color: '#e1e1e1' },
          horzLines: { color: '#e1e1e1' },
        },
        timeScale: {
          borderColor: '#cccccc',
        },
        rightPriceScale: {
          borderColor: '#cccccc',
        },
      });
      setChart(newChart);
    }

    return () => {
      if (chart) {
        chart.remove();
        setChart(null);
      }
    };
  }, [open, chart]);

  // Handle backtest selection
  const handleToggleSelection = async (index: number) => {
    const selectedCount = comparisonData.filter((d) => d.selected).length;
    const isCurrentlySelected = comparisonData[index].selected;

    // Check if we're trying to select more than 4
    if (!isCurrentlySelected && selectedCount >= 4) {
      setError(
        t(
          'backtest:comparison.maxSelectionError',
          'You can only compare up to 4 backtests at a time'
        )
      );
      return;
    }

    setError(null);

    // Toggle selection
    const newData = comparisonData.map((item, i) =>
      i === index ? { ...item, selected: !item.selected } : item
    );

    // Fetch result if selecting and not already loaded
    if (newData[index].selected && !newData[index].result) {
      const loadingData = newData.map((item, i) =>
        i === index ? { ...item, loading: true } : item
      );
      setComparisonData(loadingData);

      try {
        const result = await onFetchResult(newData[index].backtest.id);
        const updatedData = loadingData.map((item, i) =>
          i === index ? { ...item, result, loading: false } : item
        );
        setComparisonData(updatedData);
      } catch {
        const errorData = loadingData.map((item, i) =>
          i === index ? { ...item, selected: false, loading: false } : item
        );
        setComparisonData(errorData);
        setError(
          t(
            'backtest:comparison.fetchError',
            'Failed to fetch backtest results'
          )
        );
      }
    } else {
      setComparisonData(newData);
    }
  };

  // Update chart with selected backtests
  useEffect(() => {
    if (!chart) return;

    // Clear existing series
    // Note: lightweight-charts doesn't have a direct way to remove all series
    // We'll recreate the chart if needed
    const selectedData = comparisonData.filter((d) => d.selected && d.result);

    if (selectedData.length === 0) return;

    const colors = ['#2962FF', '#FF6D00', '#00C853', '#AA00FF'];

    selectedData.forEach((data, index) => {
      if (!data.result?.equity_curve) return;

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const lineSeries = (chart as any).addLineSeries({
        color: colors[index % colors.length],
        lineWidth: 2,
        title: `${data.backtest.strategy_type} (${new Date(data.backtest.created_at).toLocaleDateString()})`,
      });

      const chartData = data.result.equity_curve.map((point) => ({
        time: (new Date(point.timestamp).getTime() / 1000) as Time,
        value: point.balance,
      }));

      lineSeries.setData(chartData);
    });

    chart.timeScale().fitContent();
  }, [chart, comparisonData]);

  // Calculate statistical significance (simplified t-test)
  const calculateStatisticalSignificance = () => {
    const selectedData = comparisonData.filter((d) => d.selected && d.result);

    if (selectedData.length < 2) return null;

    // For simplicity, we'll compare the first two selected backtests
    const data1 = selectedData[0].result!;
    const data2 = selectedData[1].result!;

    // Calculate mean returns
    const mean1 = data1.total_return;
    const mean2 = data2.total_return;

    // Calculate standard deviations (simplified using trade P&L)
    const trades1 = data1.trade_log.map((t) => t.pnl);
    const trades2 = data2.trade_log.map((t) => t.pnl);

    const std1 = calculateStdDev(trades1);
    const std2 = calculateStdDev(trades2);

    // Calculate t-statistic
    const n1 = trades1.length;
    const n2 = trades2.length;

    if (n1 === 0 || n2 === 0) return null;

    const pooledStd = Math.sqrt(
      ((n1 - 1) * std1 * std1 + (n2 - 1) * std2 * std2) / (n1 + n2 - 2)
    );
    const tStat = (mean1 - mean2) / (pooledStd * Math.sqrt(1 / n1 + 1 / n2));

    // Degrees of freedom
    const df = n1 + n2 - 2;

    // Critical value for 95% confidence (approximate)
    const criticalValue = 1.96; // For large df

    const isSignificant = Math.abs(tStat) > criticalValue;

    return {
      tStatistic: tStat,
      degreesOfFreedom: df,
      isSignificant,
      pValue: isSignificant ? '< 0.05' : '> 0.05',
    };
  };

  // Helper function to calculate standard deviation
  const calculateStdDev = (values: number[]) => {
    if (values.length === 0) return 0;
    const mean = values.reduce((sum, val) => sum + val, 0) / values.length;
    const squaredDiffs = values.map((val) => Math.pow(val - mean, 2));
    const variance =
      squaredDiffs.reduce((sum, val) => sum + val, 0) / values.length;
    return Math.sqrt(variance);
  };

  const selectedData = comparisonData.filter((d) => d.selected && d.result);
  const statisticalTest = calculateStatisticalSignificance();

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="xl"
      fullWidth
      PaperProps={{
        sx: { height: '90vh' },
      }}
    >
      <DialogTitle>
        {t('backtest:comparison.title', 'Compare Backtests')}
      </DialogTitle>
      <DialogContent dividers>
        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            {t(
              'backtest:comparison.instructions',
              'Select up to 4 backtests to compare. Only completed backtests can be compared.'
            )}
          </Typography>
          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}
        </Box>

        {/* Backtest Selection */}
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            {t('backtest:comparison.selectBacktests', 'Select Backtests')}
          </Typography>
          <Stack spacing={1}>
            {comparisonData.map((data, index) => (
              <FormControlLabel
                key={data.backtest.id}
                control={
                  <Checkbox
                    checked={data.selected}
                    onChange={() => handleToggleSelection(index)}
                    disabled={data.loading}
                  />
                }
                label={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2">
                      {data.backtest.strategy_type} -{' '}
                      {new Date(data.backtest.created_at).toLocaleDateString()}
                    </Typography>
                    <Chip
                      label={data.backtest.instruments.join(', ')}
                      size="small"
                      variant="outlined"
                    />
                    {data.loading && (
                      <Typography variant="caption" color="text.secondary">
                        {t('common:loading', 'Loading...')}
                      </Typography>
                    )}
                  </Box>
                }
              />
            ))}
          </Stack>
        </Paper>

        {selectedData.length > 0 && (
          <>
            {/* Equity Curve Overlay */}
            <Paper sx={{ p: 2, mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                {t('backtest:comparison.equityCurves', 'Equity Curves')}
              </Typography>
              <Box ref={chartRef} sx={{ width: '100%', height: 400 }} />
              <Box sx={{ mt: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                {selectedData.map((data, index) => {
                  const colors = ['#2962FF', '#FF6D00', '#00C853', '#AA00FF'];
                  return (
                    <Box
                      key={data.backtest.id}
                      sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                    >
                      <Box
                        sx={{
                          width: 16,
                          height: 16,
                          backgroundColor: colors[index % colors.length],
                          borderRadius: 1,
                        }}
                      />
                      <Typography variant="caption">
                        {data.backtest.strategy_type} (
                        {new Date(
                          data.backtest.created_at
                        ).toLocaleDateString()}
                        )
                      </Typography>
                    </Box>
                  );
                })}
              </Box>
            </Paper>

            {/* Comparison Table */}
            <Paper sx={{ p: 2, mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                {t(
                  'backtest:comparison.metricsComparison',
                  'Metrics Comparison'
                )}
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>
                        {t('backtest:comparison.metric', 'Metric')}
                      </TableCell>
                      {selectedData.map((data) => (
                        <TableCell key={data.backtest.id} align="right">
                          <Typography variant="caption" display="block">
                            {data.backtest.strategy_type}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {new Date(
                              data.backtest.created_at
                            ).toLocaleDateString()}
                          </Typography>
                        </TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    <TableRow>
                      <TableCell>
                        {t('backtest:results.totalReturn', 'Total Return')}
                      </TableCell>
                      {selectedData.map((data) => (
                        <TableCell
                          key={data.backtest.id}
                          align="right"
                          sx={{
                            color:
                              data.result!.total_return > 0
                                ? 'success.main'
                                : 'error.main',
                            fontWeight: 'bold',
                          }}
                        >
                          {data.result!.total_return.toFixed(2)}%
                        </TableCell>
                      ))}
                    </TableRow>
                    <TableRow>
                      <TableCell>
                        {t('backtest:results.maxDrawdown', 'Max Drawdown')}
                      </TableCell>
                      {selectedData.map((data) => (
                        <TableCell
                          key={data.backtest.id}
                          align="right"
                          sx={{ color: 'error.main' }}
                        >
                          {data.result!.max_drawdown.toFixed(2)}%
                        </TableCell>
                      ))}
                    </TableRow>
                    <TableRow>
                      <TableCell>
                        {t('backtest:results.sharpeRatio', 'Sharpe Ratio')}
                      </TableCell>
                      {selectedData.map((data) => (
                        <TableCell key={data.backtest.id} align="right">
                          {data.result!.sharpe_ratio.toFixed(2)}
                        </TableCell>
                      ))}
                    </TableRow>
                    <TableRow>
                      <TableCell>
                        {t('backtest:results.winRate', 'Win Rate')}
                      </TableCell>
                      {selectedData.map((data) => (
                        <TableCell key={data.backtest.id} align="right">
                          {data.result!.win_rate.toFixed(1)}%
                        </TableCell>
                      ))}
                    </TableRow>
                    <TableRow>
                      <TableCell>
                        {t('backtest:results.profitFactor', 'Profit Factor')}
                      </TableCell>
                      {selectedData.map((data) => (
                        <TableCell
                          key={data.backtest.id}
                          align="right"
                          sx={{
                            color:
                              data.result!.profit_factor > 1
                                ? 'success.main'
                                : 'error.main',
                          }}
                        >
                          {data.result!.profit_factor.toFixed(2)}
                        </TableCell>
                      ))}
                    </TableRow>
                    <TableRow>
                      <TableCell>
                        {t('backtest:results.totalTrades', 'Total Trades')}
                      </TableCell>
                      {selectedData.map((data) => (
                        <TableCell key={data.backtest.id} align="right">
                          {data.result!.total_trades}
                        </TableCell>
                      ))}
                    </TableRow>
                    <TableRow>
                      <TableCell>
                        {t('backtest:results.avgWin', 'Avg Win')}
                      </TableCell>
                      {selectedData.map((data) => (
                        <TableCell
                          key={data.backtest.id}
                          align="right"
                          sx={{ color: 'success.main' }}
                        >
                          {data.result!.average_win.toFixed(2)}
                        </TableCell>
                      ))}
                    </TableRow>
                    <TableRow>
                      <TableCell>
                        {t('backtest:results.avgLoss', 'Avg Loss')}
                      </TableCell>
                      {selectedData.map((data) => (
                        <TableCell
                          key={data.backtest.id}
                          align="right"
                          sx={{ color: 'error.main' }}
                        >
                          {Math.abs(data.result!.average_loss).toFixed(2)}
                        </TableCell>
                      ))}
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>

            {/* Statistical Significance */}
            {statisticalTest && selectedData.length >= 2 && (
              <Paper sx={{ p: 2 }}>
                <Typography variant="h6" gutterBottom>
                  {t(
                    'backtest:comparison.statisticalSignificance',
                    'Statistical Significance'
                  )}
                </Typography>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {t(
                    'backtest:comparison.statisticalNote',
                    'Comparing the first two selected backtests using a two-sample t-test'
                  )}
                </Typography>
                <Divider sx={{ my: 2 }} />
                <Stack spacing={1}>
                  <Box
                    sx={{ display: 'flex', justifyContent: 'space-between' }}
                  >
                    <Typography variant="body2">
                      {t('backtest:comparison.tStatistic', 't-Statistic')}:
                    </Typography>
                    <Typography variant="body2" fontWeight="bold">
                      {statisticalTest.tStatistic.toFixed(4)}
                    </Typography>
                  </Box>
                  <Box
                    sx={{ display: 'flex', justifyContent: 'space-between' }}
                  >
                    <Typography variant="body2">
                      {t(
                        'backtest:comparison.degreesOfFreedom',
                        'Degrees of Freedom'
                      )}
                      :
                    </Typography>
                    <Typography variant="body2" fontWeight="bold">
                      {statisticalTest.degreesOfFreedom}
                    </Typography>
                  </Box>
                  <Box
                    sx={{ display: 'flex', justifyContent: 'space-between' }}
                  >
                    <Typography variant="body2">
                      {t('backtest:comparison.pValue', 'p-Value')}:
                    </Typography>
                    <Typography variant="body2" fontWeight="bold">
                      {statisticalTest.pValue}
                    </Typography>
                  </Box>
                  <Box
                    sx={{ display: 'flex', justifyContent: 'space-between' }}
                  >
                    <Typography variant="body2">
                      {t('backtest:comparison.result', 'Result')}:
                    </Typography>
                    <Chip
                      label={
                        statisticalTest.isSignificant
                          ? t(
                              'backtest:comparison.significant',
                              'Statistically Significant'
                            )
                          : t(
                              'backtest:comparison.notSignificant',
                              'Not Statistically Significant'
                            )
                      }
                      color={
                        statisticalTest.isSignificant ? 'success' : 'default'
                      }
                      size="small"
                    />
                  </Box>
                </Stack>
                <Alert severity="info" sx={{ mt: 2 }}>
                  <Typography variant="caption">
                    {t(
                      'backtest:comparison.significanceExplanation',
                      'A statistically significant result (p < 0.05) suggests that the difference in performance between the two strategies is unlikely to be due to chance alone.'
                    )}
                  </Typography>
                </Alert>
              </Paper>
            )}
          </>
        )}

        {selectedData.length === 0 && (
          <Alert severity="info">
            {t(
              'backtest:comparison.noSelection',
              'Select backtests above to compare their performance'
            )}
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('common:close', 'Close')}</Button>
      </DialogActions>
    </Dialog>
  );
};

export default BacktestComparisonModal;
