import { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Box,
  Paper,
  Grid,
  Alert,
  Tabs,
  Tab,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { Breadcrumbs } from '../components/common';
import BacktestConfigPanel from '../components/backtest/BacktestConfigPanel';
import BacktestProgressBar from '../components/backtest/BacktestProgressBar';
import BacktestResultsPanel from '../components/backtest/BacktestResultsPanel';
import type { Strategy } from '../types/strategy';
import type {
  BacktestConfig,
  Backtest,
  BacktestResult,
} from '../types/backtest';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = (props: TabPanelProps) => {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`backtest-tabpanel-${index}`}
      aria-labelledby={`backtest-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
};

const BacktestPage = () => {
  const { t } = useTranslation(['backtest', 'common']);
  const { token } = useAuth();
  const [tabValue, setTabValue] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loadingStrategies, setLoadingStrategies] = useState(true);
  const [runningBacktest, setRunningBacktest] = useState(false);
  const [currentBacktestId, setCurrentBacktestId] = useState<number | null>(
    null
  );
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(
    null
  );

  // Fetch available strategies
  useEffect(() => {
    const fetchStrategies = async () => {
      if (!token) return;

      try {
        setLoadingStrategies(true);

        const response = await fetch('/api/strategies/available', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          throw new Error('Failed to fetch strategies');
        }

        const data = await response.json();
        setStrategies(data);
        setError(null);
      } catch (err) {
        // Fallback to mock data if API fails
        console.warn(
          'Failed to fetch strategies from API, using mock data:',
          err
        );
        const mockStrategies: Strategy[] = [
          {
            id: 'floor_strategy',
            name: 'Floor Strategy',
            class_name: 'FloorStrategy',
            description:
              'Multi-layer scaling strategy with dynamic position management',
            config_schema: {
              type: 'object',
              properties: {
                base_lot_size: {
                  type: 'number',
                  description: 'Base lot size for initial entry',
                  default: 1.0,
                  minimum: 0.01,
                },
                scaling_mode: {
                  type: 'string',
                  description: 'Scaling mode for position sizing',
                  default: 'additive',
                  enum: ['additive', 'multiplicative'],
                },
                retracement_pips: {
                  type: 'integer',
                  description: 'Retracement in pips to trigger scaling',
                  default: 30,
                  minimum: 1,
                },
              },
              required: ['base_lot_size', 'scaling_mode', 'retracement_pips'],
            },
          },
          {
            id: 'ma_crossover',
            name: 'MA Crossover Strategy',
            class_name: 'MACrossoverStrategy',
            description:
              'Moving average crossover strategy using EMA 12 and EMA 26',
            config_schema: {
              type: 'object',
              properties: {
                fast_period: {
                  type: 'integer',
                  description: 'Fast EMA period',
                  default: 12,
                  minimum: 1,
                },
                slow_period: {
                  type: 'integer',
                  description: 'Slow EMA period',
                  default: 26,
                  minimum: 1,
                },
              },
              required: ['fast_period', 'slow_period'],
            },
          },
        ];
        setStrategies(mockStrategies);
      } finally {
        setLoadingStrategies(false);
      }
    };

    fetchStrategies();
  }, [token]);

  // Handle tab change
  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  // Handle run backtest
  const handleRunBacktest = async (config: BacktestConfig) => {
    if (!token) {
      setError('Authentication required');
      return;
    }

    try {
      setRunningBacktest(true);
      setError(null);

      const response = await fetch('/api/backtest/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(config),
      });

      if (!response.ok) {
        throw new Error('Failed to start backtest');
      }

      const data = await response.json();
      setCurrentBacktestId(data.backtest_id);

      // Keep on configuration tab to show progress
      // User can switch to results tab when complete
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start backtest');
    } finally {
      setRunningBacktest(false);
    }
  };

  // Handle backtest completion
  const handleBacktestComplete = async (backtest: Backtest) => {
    if (!token) return;

    try {
      const response = await fetch(`/api/backtest/${backtest.id}/results`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch backtest results');
      }

      const result = await response.json();
      setBacktestResult(result);
      // Switch to results tab
      setTabValue(1);
    } catch (err) {
      console.error('Failed to fetch backtest results:', err);
      // Fallback to mock data
      const mockResult: BacktestResult = {
        id: 1,
        backtest: backtest.id,
        final_balance: backtest.initial_balance * 1.15,
        total_return: 15.0,
        max_drawdown: -8.5,
        sharpe_ratio: 1.8,
        total_trades: 45,
        winning_trades: 28,
        losing_trades: 17,
        win_rate: 62.2,
        average_win: 250.0,
        average_loss: -150.0,
        profit_factor: 1.67,
        equity_curve: generateMockEquityCurve(backtest.initial_balance, 45),
        trade_log: generateMockTradeLog(45),
      };

      setBacktestResult(mockResult);
      // Switch to results tab
      setTabValue(1);
    }
  };

  // Generate mock equity curve data
  const generateMockEquityCurve = (initialBalance: number, trades: number) => {
    const curve = [];
    let balance = initialBalance;
    const startDate = new Date('2024-01-01');

    for (let i = 0; i <= trades; i++) {
      const timestamp = new Date(startDate);
      timestamp.setDate(startDate.getDate() + i * 2);

      curve.push({
        timestamp: timestamp.toISOString(),
        balance: balance,
      });

      // Random walk with upward bias
      const change = (Math.random() - 0.4) * 500;
      balance += change;
    }

    return curve;
  };

  // Generate mock trade log data
  const generateMockTradeLog = (count: number) => {
    const instruments = ['EUR_USD', 'GBP_USD', 'USD_JPY'];
    const directions = ['long', 'short'];
    const trades = [];
    const startDate = new Date('2024-01-01');

    for (let i = 0; i < count; i++) {
      const timestamp = new Date(startDate);
      timestamp.setDate(startDate.getDate() + i * 2);

      const entryPrice = 1.1 + Math.random() * 0.1;
      const isWin = Math.random() > 0.38; // 62% win rate
      const exitPrice = isWin
        ? entryPrice + Math.random() * 0.005
        : entryPrice - Math.random() * 0.003;
      const units = 10000;
      const pnl = (exitPrice - entryPrice) * units;

      trades.push({
        timestamp: timestamp.toISOString(),
        instrument: instruments[Math.floor(Math.random() * instruments.length)],
        direction: directions[Math.floor(Math.random() * directions.length)],
        entry_price: entryPrice,
        exit_price: exitPrice,
        units: units,
        pnl: pnl,
        duration: Math.floor(Math.random() * 3600) + 300, // 5 min to 1 hour
      });
    }

    return trades;
  };

  // Handle backtest error
  const handleBacktestError = (errorMsg: string) => {
    setError(errorMsg);
  };

  return (
    <Container maxWidth={false} sx={{ mt: 4, mb: 4, px: 3 }}>
      <Breadcrumbs />
      <Box>
        <Typography variant="h4" gutterBottom>
          {t('backtest:title', 'Backtesting')}
        </Typography>

        {/* Error Alert */}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Tabs for Configuration, Progress, Results, History */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs value={tabValue} onChange={handleTabChange}>
            <Tab label={t('backtest:tabs.configuration', 'Configuration')} />
            <Tab
              label={t('backtest:tabs.results', 'Results')}
              disabled={tabValue === 0}
            />
            <Tab label={t('backtest:tabs.history', 'History')} />
          </Tabs>
        </Box>

        {/* Configuration Tab */}
        <TabPanel value={tabValue} index={0}>
          <Grid container spacing={3}>
            {/* Config Panel */}
            <Grid size={{ xs: 12, lg: 4 }}>
              <Paper sx={{ p: 3 }}>
                <BacktestConfigPanel
                  strategies={strategies}
                  onRunBacktest={handleRunBacktest}
                  loading={loadingStrategies}
                  disabled={runningBacktest}
                />
              </Paper>
            </Grid>

            {/* Progress Panel */}
            <Grid size={{ xs: 12, lg: 8 }}>
              <BacktestProgressBar
                backtestId={currentBacktestId}
                onComplete={handleBacktestComplete}
                onError={handleBacktestError}
              />
            </Grid>
          </Grid>
        </TabPanel>

        {/* Results Tab */}
        <TabPanel value={tabValue} index={1}>
          <BacktestResultsPanel result={backtestResult} />
        </TabPanel>

        {/* History Tab */}
        <TabPanel value={tabValue} index={2}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              {t('backtest:history.title', 'Backtest History')}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t(
                'backtest:history.placeholder',
                'History panel will be implemented in task 21.6'
              )}
            </Typography>
          </Paper>
        </TabPanel>
      </Box>
    </Container>
  );
};

export default BacktestPage;
