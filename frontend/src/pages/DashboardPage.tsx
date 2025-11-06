import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Container,
  Typography,
  Box,
  Paper,
  Card,
  CardContent,
  Chip,
  Alert,
  CircularProgress,
  Stack,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  IconButton,
  Tooltip,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import type { SelectChangeEvent } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { OHLCChart } from '../components/chart';
import { Breadcrumbs } from '../components/common';
import ChartControls from '../components/chart/ChartControls';
import type { Granularity, OHLCData, Position, Order } from '../types/chart';
import type { Indicator } from '../components/chart/ChartControls';

interface StrategyEvent {
  id: string;
  strategy_name: string;
  event_type: string;
  message: string;
  timestamp: string;
  instrument?: string;
}

const DashboardPage = () => {
  const { t } = useTranslation('dashboard');
  const { token } = useAuth();

  // Chart state
  const [instrument, setInstrument] = useState<string>('USD_JPY');
  const [granularity, setGranularity] = useState<Granularity>('H1');
  const [indicators, setIndicators] = useState<Indicator[]>([]);

  // Data state
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [strategyEvents, setStrategyEvents] = useState<StrategyEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Auto-refresh settings
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState<number>(30); // seconds
  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // OANDA account state
  const [hasOandaAccount, setHasOandaAccount] = useState<boolean>(true);
  const [oandaAccountId, setOandaAccountId] = useState<string | undefined>(
    undefined
  );

  // Chart API reference for programmatic control
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const chartApiRef = useRef<any>(null);

  /**
   * Simple fetchCandles function that makes API calls
   * Returns OHLCData[] or empty array on error
   *
   * @param before - Unix timestamp to fetch older data (candles ending before this time)
   * @param after - Unix timestamp to fetch newer data (candles starting after this time)
   */
  const fetchCandles = useCallback(
    async (
      inst: string,
      gran: string,
      count: number,
      before?: number,
      after?: number
    ): Promise<OHLCData[]> => {
      try {
        let url = `/api/candles?instrument=${inst}&granularity=${gran}&count=${count}`;
        if (before) {
          url += `&before=${before}`;
        }
        if (after) {
          url += `&after=${after}`;
        }

        console.log('📡 Fetching candles:', {
          inst,
          gran,
          count,
          before,
          after,
        });

        const response = await fetch(url, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        // Check for rate limiting
        if (
          response.status === 429 ||
          response.headers.get('X-Rate-Limited') === 'true'
        ) {
          console.warn('⚠️ Rate limited by API');
          return [];
        }

        if (!response.ok) {
          const errorData = await response.json();
          if (errorData.error_code === 'NO_OANDA_ACCOUNT') {
            setHasOandaAccount(false);
            return [];
          }

          console.error('❌ API error:', response.status, errorData);
          return [];
        }

        const data = await response.json();
        const candles = data.candles || [];

        console.log('✅ Fetched', candles.length, 'candles');
        setHasOandaAccount(true);
        return candles;
      } catch (err) {
        console.error('❌ Error fetching candles:', err);
        return [];
      }
    },
    [token]
  );

  // Fetch positions
  const fetchPositions = useCallback(async () => {
    if (!token) return;
    try {
      const response = await fetch('/api/positions', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setPositions(data.positions || []);
      }
    } catch (err) {
      console.error('Error fetching positions:', err);
    }
  }, [token]);

  // Fetch orders
  const fetchOrders = useCallback(async () => {
    if (!token) return;
    try {
      const response = await fetch('/api/orders', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setOrders(data.orders || []);
      }
    } catch (err) {
      console.error('Error fetching orders:', err);
    }
  }, [token]);

  // Fetch strategy events
  const fetchStrategyEvents = useCallback(async () => {
    if (!token) return;
    try {
      const response = await fetch('/api/events?limit=10', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setStrategyEvents(data.events || []);
      } else if (response.status === 403) {
        // User doesn't have permission to view events (not an admin)
        // This is expected for non-admin users, so just set empty array
        setStrategyEvents([]);
      }
    } catch (err) {
      console.error('Error fetching strategy events:', err);
    }
  }, [token]);

  // Fetch OANDA accounts
  const fetchOandaAccounts = useCallback(async () => {
    if (!token) return;
    try {
      const response = await fetch('/api/accounts/', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (response.ok) {
        const accounts = await response.json();
        // Backend returns the accounts array directly, not wrapped in an object
        if (Array.isArray(accounts) && accounts.length > 0) {
          // Use the first account's account_id
          setOandaAccountId(accounts[0].account_id);
          setHasOandaAccount(true);
        } else {
          setHasOandaAccount(false);
        }
      }
    } catch (err) {
      console.error('Error fetching OANDA accounts:', err);
      setHasOandaAccount(false);
    }
  }, [token]);

  // Initial data load
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);

      try {
        await Promise.all([
          fetchOandaAccounts(),
          fetchPositions(),
          fetchOrders(),
          fetchStrategyEvents(),
        ]);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to load dashboard data'
        );
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [fetchOandaAccounts, fetchPositions, fetchOrders, fetchStrategyEvents]);

  // Auto-refresh effect for positions, orders, and events
  useEffect(() => {
    // Clear existing timer
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }

    // Set up new timer if auto-refresh is enabled
    if (autoRefreshEnabled && refreshInterval > 0) {
      refreshTimerRef.current = setInterval(() => {
        fetchPositions();
        fetchOrders();
        fetchStrategyEvents();
      }, refreshInterval * 1000);
    }

    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [
    autoRefreshEnabled,
    refreshInterval,
    fetchPositions,
    fetchOrders,
    fetchStrategyEvents,
  ]);

  // Handle refresh interval change
  const handleRefreshIntervalChange = (event: SelectChangeEvent<number>) => {
    setRefreshInterval(Number(event.target.value));
  };

  // Handle auto-refresh toggle
  const handleAutoRefreshToggle = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setAutoRefreshEnabled(event.target.checked);
  };

  // Handle manual refresh - reload data without remounting
  const handleManualRefresh = useCallback(() => {
    console.log('🔄 Manual refresh: Reloading chart data');
    // Force re-fetch by changing instrument temporarily
    const currentInstrument = instrument;
    setInstrument('');
    setTimeout(() => setInstrument(currentInstrument), 0);
  }, [instrument]);

  // Filter positions and orders for current instrument
  const currentPositions = positions.filter((p) => p.instrument === instrument);
  const currentOrders = orders.filter((o) => o.instrument === instrument);

  return (
    <Container maxWidth={false} sx={{ mt: 4, mb: 4, px: 3 }}>
      <Breadcrumbs />
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          {t('title')}
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {t('welcome')}
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Chart Section */}
      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 2,
          }}
        >
          <Typography variant="h6">Market Chart</Typography>

          {/* Auto-refresh controls */}
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <FormControlLabel
              control={
                <Switch
                  checked={autoRefreshEnabled}
                  onChange={handleAutoRefreshToggle}
                  size="small"
                />
              }
              label="Auto-refresh"
            />

            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel id="refresh-interval-label">Interval</InputLabel>
              <Select
                labelId="refresh-interval-label"
                id="refresh-interval-select"
                value={refreshInterval}
                label="Interval"
                onChange={handleRefreshIntervalChange}
                disabled={!autoRefreshEnabled}
              >
                <MenuItem value={10}>10 seconds</MenuItem>
                <MenuItem value={30}>30 seconds</MenuItem>
                <MenuItem value={60}>1 minute</MenuItem>
                <MenuItem value={120}>2 minutes</MenuItem>
                <MenuItem value={300}>5 minutes</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <ChartControls
            instrument={instrument}
            granularity={granularity}
            indicators={indicators}
            onInstrumentChange={setInstrument}
            onGranularityChange={setGranularity}
            onIndicatorsChange={setIndicators}
          />

          {/* Manual Refresh Button */}
          <Tooltip title="Refresh chart data">
            <IconButton
              onClick={handleManualRefresh}
              disabled={!hasOandaAccount}
              color="primary"
              size="small"
              sx={{ ml: 'auto' }}
            >
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>

        <Box sx={{ height: 500, position: 'relative', overflow: 'hidden' }}>
          {!hasOandaAccount ? (
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                height: '100%',
                border: '1px solid #e1e1e1',
                borderRadius: 1,
                backgroundColor: '#f5f5f5',
              }}
            >
              <Typography variant="body1" color="text.secondary">
                {t('chart.noOandaAccount')}
              </Typography>
            </Box>
          ) : (
            <OHLCChart
              instrument={instrument}
              granularity={granularity}
              fetchCandles={fetchCandles}
              positions={currentPositions}
              orders={currentOrders}
              enableRealTimeUpdates={hasOandaAccount && !!oandaAccountId}
              accountId={oandaAccountId}
              onChartReady={(chartApi) => {
                chartApiRef.current = chartApi;
              }}
            />
          )}
        </Box>

        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mt: 1 }}
        >
          Tip: Scroll left/right on the chart to load more historical data. Data
          is cached for faster navigation.
        </Typography>
      </Paper>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
          gap: 3,
        }}
      >
        {/* Open Positions */}
        <Paper elevation={2} sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Open Positions ({currentPositions.length})
          </Typography>

          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
              <CircularProgress size={32} />
            </Box>
          ) : currentPositions.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
              No open positions for {instrument.replace('_', '/')}
            </Typography>
          ) : (
            <Stack spacing={2}>
              {currentPositions.map((position) => (
                <Card key={position.position_id} variant="outlined">
                  <CardContent>
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        mb: 1,
                      }}
                    >
                      <Typography variant="subtitle2">
                        {position.instrument.replace('_', '/')}
                      </Typography>
                      <Chip
                        label={position.direction.toUpperCase()}
                        color={
                          position.direction === 'long' ? 'success' : 'error'
                        }
                        size="small"
                      />
                    </Box>
                    <Box
                      sx={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: 1,
                      }}
                    >
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Entry Price
                        </Typography>
                        <Typography variant="body2">
                          {position.entry_price.toFixed(5)}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Current Price
                        </Typography>
                        <Typography variant="body2">
                          {position.current_price.toFixed(5)}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Units
                        </Typography>
                        <Typography variant="body2">
                          {position.units}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          P&L
                        </Typography>
                        <Typography
                          variant="body2"
                          color={
                            position.unrealized_pnl >= 0
                              ? 'success.main'
                              : 'error.main'
                          }
                        >
                          {position.unrealized_pnl >= 0 ? '+' : ''}
                          {position.unrealized_pnl.toFixed(2)}
                        </Typography>
                      </Box>
                    </Box>
                  </CardContent>
                </Card>
              ))}
            </Stack>
          )}
        </Paper>

        {/* Strategy Events */}
        <Paper elevation={2} sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Recent Strategy Events
          </Typography>

          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
              <CircularProgress size={32} />
            </Box>
          ) : strategyEvents.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
              No recent strategy events
            </Typography>
          ) : (
            <Stack spacing={2}>
              {strategyEvents.map((event) => (
                <Card key={event.id} variant="outlined">
                  <CardContent>
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        mb: 1,
                      }}
                    >
                      <Typography variant="subtitle2">
                        {event.strategy_name}
                      </Typography>
                      <Chip
                        label={event.event_type}
                        size="small"
                        color={
                          event.event_type === 'SIGNAL'
                            ? 'primary'
                            : event.event_type === 'ERROR'
                              ? 'error'
                              : 'default'
                        }
                      />
                    </Box>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ mb: 1 }}
                    >
                      {event.message}
                    </Typography>
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                      }}
                    >
                      {event.instrument && (
                        <Typography variant="caption" color="text.secondary">
                          {event.instrument.replace('_', '/')}
                        </Typography>
                      )}
                      <Typography variant="caption" color="text.secondary">
                        {new Date(event.timestamp).toLocaleString()}
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              ))}
            </Stack>
          )}
        </Paper>
      </Box>
    </Container>
  );
};

export default DashboardPage;
