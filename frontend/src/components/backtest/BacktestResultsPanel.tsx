import { useEffect, useRef, useState } from 'react';

import {
  Box,
  Card,
  CardContent,
  Typography,
  Paper,
  Alert,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { useTranslation } from 'react-i18next';
import { createChart, type IChartApi, type Time } from 'lightweight-charts';
import type { BacktestResult } from '../../types/backtest';
import TradeLogTable from './TradeLogTable';

interface BacktestResultsPanelProps {
  result: BacktestResult | null;
}

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  color?: 'success' | 'error' | 'info' | 'warning';
}

const MetricCard = ({ title, value, subtitle, color }: MetricCardProps) => {
  const getColor = () => {
    switch (color) {
      case 'success':
        return 'success.main';
      case 'error':
        return 'error.main';
      case 'warning':
        return 'warning.main';
      case 'info':
      default:
        return 'primary.main';
    }
  };

  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {title}
        </Typography>
        <Typography
          variant="h4"
          component="div"
          sx={{ color: getColor(), fontWeight: 'bold' }}
        >
          {value}
        </Typography>
        {subtitle && (
          <Typography variant="caption" color="text.secondary">
            {subtitle}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
};

const BacktestResultsPanel = ({ result }: BacktestResultsPanelProps) => {
  const { t } = useTranslation(['backtest', 'common']);
  const equityChartRef = useRef<HTMLDivElement>(null);
  const drawdownChartRef = useRef<HTMLDivElement>(null);
  const tradeDistChartRef = useRef<HTMLDivElement>(null);
  const monthlyReturnsRef = useRef<HTMLDivElement>(null);

  const [equityChart, setEquityChart] = useState<IChartApi | null>(null);
  const [drawdownChart, setDrawdownChart] = useState<IChartApi | null>(null);
  const [tradeDistChart, setTradeDistChart] = useState<IChartApi | null>(null);

  // Initialize charts
  useEffect(() => {
    if (!result) return;

    // Equity Curve Chart
    if (equityChartRef.current && !equityChart) {
      const chart = createChart(equityChartRef.current, {
        width: equityChartRef.current.clientWidth,
        height: 300,
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
      setEquityChart(chart);
    }

    // Drawdown Chart
    if (drawdownChartRef.current && !drawdownChart) {
      const chart = createChart(drawdownChartRef.current, {
        width: drawdownChartRef.current.clientWidth,
        height: 300,
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
      setDrawdownChart(chart);
    }

    // Trade Distribution Chart
    if (tradeDistChartRef.current && !tradeDistChart) {
      const chart = createChart(tradeDistChartRef.current, {
        width: tradeDistChartRef.current.clientWidth,
        height: 300,
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
      setTradeDistChart(chart);
    }

    // Cleanup
    return () => {
      equityChart?.remove();
      drawdownChart?.remove();
      tradeDistChart?.remove();
    };
  }, [result, equityChart, drawdownChart, tradeDistChart]);

  // Update equity curve
  useEffect(() => {
    if (!equityChart || !result?.equity_curve) return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const lineSeries = (equityChart as any).addLineSeries({
      color: '#2962FF',
      lineWidth: 2,
    });

    const data = result.equity_curve.map((point) => ({
      time: (new Date(point.timestamp).getTime() / 1000) as Time,
      value: point.balance,
    }));

    lineSeries.setData(data);
    equityChart.timeScale().fitContent();
  }, [equityChart, result]);

  // Update drawdown chart
  useEffect(() => {
    if (!drawdownChart || !result?.equity_curve) return;

    // Calculate drawdown from equity curve
    let peak = result.equity_curve[0]?.balance || 0;
    const drawdownData = result.equity_curve.map((point) => {
      if (point.balance > peak) {
        peak = point.balance;
      }
      const drawdown = ((point.balance - peak) / peak) * 100;
      return {
        time: (new Date(point.timestamp).getTime() / 1000) as Time,
        value: drawdown,
      };
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const lineSeries = (drawdownChart as any).addLineSeries({
      color: '#ef5350',
      lineWidth: 2,
    });

    lineSeries.setData(drawdownData);
    drawdownChart.timeScale().fitContent();
  }, [drawdownChart, result]);

  // Update trade distribution chart
  useEffect(() => {
    if (!tradeDistChart || !result?.trade_log) return;

    // Create histogram of P&L distribution
    const pnlValues = result.trade_log.map((trade) => trade.pnl);
    const min = Math.min(...pnlValues);
    const max = Math.max(...pnlValues);
    const binCount = 20;
    const binSize = (max - min) / binCount;

    const bins: { [key: number]: number } = {};
    for (let i = 0; i < binCount; i++) {
      bins[i] = 0;
    }

    pnlValues.forEach((pnl) => {
      const binIndex = Math.min(
        Math.floor((pnl - min) / binSize),
        binCount - 1
      );
      bins[binIndex]++;
    });

    const histogramData = Object.entries(bins).map(([index, count], i) => ({
      time: i as Time,
      value: count,
      color: parseFloat(index) * binSize + min >= 0 ? '#26a69a' : '#ef5350',
    }));

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const histogramSeries = (tradeDistChart as any).addHistogramSeries({
      priceFormat: {
        type: 'volume',
      },
    });

    histogramSeries.setData(histogramData);
    tradeDistChart.timeScale().fitContent();
  }, [tradeDistChart, result]);

  // Calculate monthly returns for heatmap
  const calculateMonthlyReturns = () => {
    if (!result?.trade_log) return [];

    const monthlyData: {
      [key: string]: { pnl: number; trades: number };
    } = {};

    result.trade_log.forEach((trade) => {
      const date = new Date(trade.timestamp);
      const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;

      if (!monthlyData[monthKey]) {
        monthlyData[monthKey] = { pnl: 0, trades: 0 };
      }

      monthlyData[monthKey].pnl += trade.pnl;
      monthlyData[monthKey].trades += 1;
    });

    return Object.entries(monthlyData)
      .map(([month, data]) => ({
        month,
        pnl: data.pnl,
        trades: data.trades,
        return: (data.pnl / result.backtest) * 100,
      }))
      .sort((a, b) => a.month.localeCompare(b.month));
  };

  const monthlyReturns = calculateMonthlyReturns();

  // Render monthly returns heatmap
  const renderMonthlyHeatmap = () => {
    if (monthlyReturns.length === 0) {
      return (
        <Typography variant="body2" color="text.secondary" align="center">
          {t('backtest:results.noData', 'No data available')}
        </Typography>
      );
    }

    return (
      <Box sx={{ overflowX: 'auto' }}>
        <Box sx={{ display: 'flex', gap: 1, minWidth: 'fit-content', p: 2 }}>
          {monthlyReturns.map((data) => {
            const intensity = Math.min(Math.abs(data.return) / 10, 1);
            const bgColor =
              data.return >= 0
                ? `rgba(38, 166, 154, ${intensity})`
                : `rgba(239, 83, 80, ${intensity})`;

            return (
              <Box
                key={data.month}
                sx={{
                  minWidth: 80,
                  p: 1.5,
                  backgroundColor: bgColor,
                  borderRadius: 1,
                  textAlign: 'center',
                }}
              >
                <Typography variant="caption" display="block" fontWeight="bold">
                  {data.month}
                </Typography>
                <Typography variant="body2" fontWeight="bold">
                  {data.return.toFixed(2)}%
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {data.trades} trades
                </Typography>
              </Box>
            );
          })}
        </Box>
      </Box>
    );
  };

  if (!result) {
    return (
      <Alert severity="info">
        {t(
          'backtest:results.noResults',
          'No results available. Run a backtest to see results.'
        )}
      </Alert>
    );
  }

  const getReturnColor = (value: number) => {
    if (value > 0) return 'success';
    if (value < 0) return 'error';
    return 'info';
  };

  return (
    <Box>
      {/* Performance Metrics Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            title={t('backtest:results.totalReturn', 'Total Return')}
            value={`${result.total_return.toFixed(2)}%`}
            color={getReturnColor(result.total_return)}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            title={t('backtest:results.maxDrawdown', 'Max Drawdown')}
            value={`${result.max_drawdown.toFixed(2)}%`}
            color="error"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            title={t('backtest:results.sharpeRatio', 'Sharpe Ratio')}
            value={result.sharpe_ratio.toFixed(2)}
            color={result.sharpe_ratio > 1 ? 'success' : 'warning'}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            title={t('backtest:results.winRate', 'Win Rate')}
            value={`${result.win_rate.toFixed(1)}%`}
            subtitle={`${result.winning_trades}/${result.total_trades} trades`}
            color={result.win_rate >= 50 ? 'success' : 'warning'}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            title={t('backtest:results.profitFactor', 'Profit Factor')}
            value={result.profit_factor.toFixed(2)}
            color={result.profit_factor > 1 ? 'success' : 'error'}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            title={t('backtest:results.totalTrades', 'Total Trades')}
            value={result.total_trades}
            subtitle={`${result.winning_trades}W / ${result.losing_trades}L`}
            color="info"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            title={t('backtest:results.avgWin', 'Avg Win')}
            value={`$${result.average_win.toFixed(2)}`}
            color="success"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            title={t('backtest:results.avgLoss', 'Avg Loss')}
            value={`$${Math.abs(result.average_loss).toFixed(2)}`}
            color="error"
          />
        </Grid>
      </Grid>

      {/* Charts */}
      <Grid container spacing={3}>
        {/* Equity Curve Chart */}
        <Grid size={{ xs: 12, lg: 6 }}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              {t('backtest:results.equityCurve', 'Equity Curve')}
            </Typography>
            <Box ref={equityChartRef} sx={{ width: '100%', height: 300 }} />
          </Paper>
        </Grid>

        {/* Drawdown Chart */}
        <Grid size={{ xs: 12, lg: 6 }}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              {t('backtest:results.drawdown', 'Drawdown')}
            </Typography>
            <Box ref={drawdownChartRef} sx={{ width: '100%', height: 300 }} />
          </Paper>
        </Grid>

        {/* Trade Distribution Chart */}
        <Grid size={{ xs: 12, lg: 6 }}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              {t('backtest:results.tradeDistribution', 'Trade Distribution')}
            </Typography>
            <Box ref={tradeDistChartRef} sx={{ width: '100%', height: 300 }} />
          </Paper>
        </Grid>

        {/* Monthly Returns Heatmap */}
        <Grid size={{ xs: 12, lg: 6 }}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              {t('backtest:results.monthlyReturns', 'Monthly Returns')}
            </Typography>
            <Box ref={monthlyReturnsRef} sx={{ height: 300, overflow: 'auto' }}>
              {renderMonthlyHeatmap()}
            </Box>
          </Paper>
        </Grid>

        {/* Trade Log Table */}
        <Grid size={{ xs: 12 }}>
          <TradeLogTable trades={result.trade_log || []} />
        </Grid>
      </Grid>
    </Box>
  );
};

export default BacktestResultsPanel;
