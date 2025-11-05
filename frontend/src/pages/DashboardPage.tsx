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
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { OHLCChart } from '../components/chart';
import { Breadcrumbs } from '../components/common';
import ChartControls from '../components/chart/ChartControls';
import type { Granularity, OHLCData, Position, Order } from '../types/chart';
import type { ChartType, Indicator } from '../components/chart/ChartControls';

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
  const [chartType, setChartType] = useState<ChartType>('Candlestick');
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

  // Chart data state for lazy loading
  const [chartData, setChartData] = useState<OHLCData[]>([]);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const oldestTimestampRef = useRef<number | null>(null);
  const [hasOandaAccount, setHasOandaAccount] = useState<boolean>(true);

  // Load historical data for the chart
  const loadHistoricalData = useCallback(
    async (inst: string, gran: string, count = 100): Promise<OHLCData[]> => {
      try {
        const response = await fetch(
          `/api/candles?instrument=${inst}&granularity=${gran}&count=${count}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (!response.ok) {
          const errorData = await response.json();

          // Check if the error is due to missing OANDA account
          if (errorData.error_code === 'NO_OANDA_ACCOUNT') {
            setHasOandaAccount(false);
            return [];
          }

          throw new Error('Failed to load historical data');
        }

        const data = await response.json();
        const candles = data.candles || [];

        // Update oldest timestamp for lazy loading
        if (candles.length > 0) {
          oldestTimestampRef.current = candles[0].time;
        }

        setHasOandaAccount(true);
        return candles;
      } catch (err) {
        console.error('Error loading historical data:', err);
        return [];
      }
    },
    [token]
  );

  // Load older data (for scrolling back in time)
  const loadOlderData = useCallback(
    async (inst: string, gran: string): Promise<OHLCData[]> => {
      if (!oldestTimestampRef.current || isLoadingMore) {
        return [];
      }

      setIsLoadingMore(true);

      try {
        const response = await fetch(
          `/api/candles?instrument=${inst}&granularity=${gran}&count=50&before=${oldestTimestampRef.current}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (!response.ok) {
          throw new Error('Failed to load older data');
        }

        const data = await response.json();
        const olderCandles = data.candles || [];

        if (olderCandles.length > 0) {
          // Update oldest timestamp
          oldestTimestampRef.current = olderCandles[0].time;

          // Prepend older data to existing chart data
          setChartData((prev) => [...olderCandles, ...prev]);
        }

        return olderCandles;
      } catch (err) {
        console.error('Error loading older data:', err);
        return [];
      } finally {
        setIsLoadingMore(false);
      }
    },
    [isLoadingMore, token]
  );

  // Initial chart data load
  useEffect(() => {
    const loadInitialChartData = async () => {
      const data = await loadHistoricalData(instrument, granularity);
      setChartData(data);
    };

    loadInitialChartData();
  }, [instrument, granularity, loadHistoricalData]);

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

  // Initial data load
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);

      try {
        await Promise.all([
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
  }, [fetchPositions, fetchOrders, fetchStrategyEvents]);

  // Auto-refresh effect
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

        <ChartControls
          instrument={instrument}
          granularity={granularity}
          chartType={chartType}
          indicators={indicators}
          onInstrumentChange={setInstrument}
          onGranularityChange={setGranularity}
          onChartTypeChange={setChartType}
          onIndicatorsChange={setIndicators}
        />

        <Box sx={{ height: 500, position: 'relative' }}>
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
            <>
              {isLoadingMore && (
                <Box
                  sx={{
                    position: 'absolute',
                    top: 8,
                    left: 8,
                    zIndex: 10,
                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    borderRadius: 1,
                    px: 2,
                    py: 1,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                  }}
                >
                  <CircularProgress size={16} />
                  <Typography variant="caption">
                    Loading older data...
                  </Typography>
                </Box>
              )}
              <OHLCChart
                instrument={instrument}
                granularity={granularity}
                data={chartData}
                positions={currentPositions}
                orders={currentOrders}
                enableRealTimeUpdates={true}
                onLoadOlderData={loadOlderData}
              />
            </>
          )}
        </Box>

        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mt: 1 }}
        >
          Tip: Scroll left on the chart to load older historical data
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
