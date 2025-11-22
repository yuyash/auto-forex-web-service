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
import Grid from '@mui/material/Grid';
import RefreshIcon from '@mui/icons-material/Refresh';
import type { SelectChangeEvent } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { useOandaAccounts } from '../hooks/useOandaAccounts';
import { useChartPreferences } from '../hooks/useChartPreferences';
import { DashboardChart } from '../components/chart/DashboardChart';
import { Breadcrumbs } from '../components/common';
import ChartControls from '../components/chart/ChartControls';
import ActiveTasksWidget from '../components/dashboard/ActiveTasksWidget';
import RecentBacktestsWidget from '../components/dashboard/RecentBacktestsWidget';
import QuickActionsWidget from '../components/dashboard/QuickActionsWidget';
import type { Granularity, Position, StrategyEvent } from '../types/chart';
import { handleAuthErrorStatus } from '../utils/authEvents';

const DashboardPage = () => {
  const { t } = useTranslation('dashboard');
  const { token, user } = useAuth();

  // Chart preferences with localStorage persistence
  const { preferences, updatePreference } = useChartPreferences();
  const { instrument, granularity, autoRefreshEnabled, refreshInterval } =
    preferences;

  // Get timezone from user settings, default to UTC
  const timezone = user?.timezone || 'UTC';

  // Data state
  const [positions, setPositions] = useState<Position[]>([]);
  const [strategyEvents, setStrategyEvents] = useState<StrategyEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Chart refresh trigger - increment to force chart to fetch new data
  const [chartRefreshTrigger, setChartRefreshTrigger] = useState<number>(0);

  // OANDA account state - using shared hook with caching
  const {
    accounts: oandaAccounts,
    hasAccounts: hasOandaAccount,
    isLoading: accountsLoading,
  } = useOandaAccounts();

  // Log account state
  useEffect(() => {
    console.log('[DashboardPage] OANDA accounts state', {
      accountCount: oandaAccounts.length,
      hasOandaAccount,
      isLoading: accountsLoading,
      accounts: oandaAccounts.map((a) => ({
        id: a.id,
        account_id: a.account_id,
        is_default: a.is_default,
      })),
    });
  }, [oandaAccounts, hasOandaAccount, accountsLoading]);

  // Use default account or first account
  const defaultAccount =
    oandaAccounts.find((acc) => acc.is_default) || oandaAccounts[0];
  const oandaAccountId = defaultAccount?.account_id;

  console.log('[DashboardPage] Selected account', {
    hasDefaultAccount: !!defaultAccount,
    accountId: oandaAccountId,
  });

  // Fetch positions
  const fetchPositions = useCallback(async () => {
    if (!token) return;
    try {
      const response = await fetch('/api/positions', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (
        handleAuthErrorStatus(response.status, {
          context: 'dashboard:positions',
        })
      ) {
        return;
      }
      if (response.ok) {
        const data = await response.json();
        setPositions(data.positions || []);
      }
    } catch (err) {
      console.error('Error fetching positions:', err);
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
      if (
        handleAuthErrorStatus(response.status, {
          context: 'dashboard:events',
        })
      ) {
        return;
      }
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
        await Promise.all([fetchPositions(), fetchStrategyEvents()]);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to load dashboard data'
        );
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [fetchPositions, fetchStrategyEvents]);

  // Auto-refresh effect for positions, orders, and events
  // Note: Chart handles its own auto-refresh internally
  useEffect(() => {
    // Clear existing timer
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }

    // Set up new timer if auto-refresh is enabled
    if (autoRefreshEnabled && refreshInterval > 0) {
      refreshTimerRef.current = setInterval(async () => {
        // Fetch sequentially to avoid overwhelming the browser
        try {
          await fetchPositions();
          await fetchStrategyEvents();
        } catch (err) {
          console.error('Auto-refresh error:', err);
        }
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
    fetchStrategyEvents,
  ]);

  // Handle refresh interval change
  const handleRefreshIntervalChange = (event: SelectChangeEvent<number>) => {
    updatePreference('refreshInterval', Number(event.target.value));
  };

  // Handle auto-refresh toggle
  const handleAutoRefreshToggle = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    updatePreference('autoRefreshEnabled', event.target.checked);
  };

  // Handle instrument change
  const handleInstrumentChange = (newInstrument: string) => {
    updatePreference('instrument', newInstrument);
  };

  // Handle granularity change
  const handleGranularityChange = (newGranularity: Granularity) => {
    updatePreference('granularity', newGranularity);
  };

  // Handle manual refresh - reload data without remounting
  const handleManualRefresh = useCallback(() => {
    fetchPositions();
    fetchStrategyEvents();
    // Trigger chart refresh by incrementing key
    setChartRefreshTrigger((prev) => prev + 1);
  }, [fetchPositions, fetchStrategyEvents]);

  // Filter positions for current instrument
  const currentPositions = positions.filter((p) => p.instrument === instrument);

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

      {/* Task Widgets */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 4 }}>
          <ActiveTasksWidget />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <RecentBacktestsWidget />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <QuickActionsWidget />
        </Grid>
      </Grid>

      {/* Chart Section */}
      <Paper elevation={2} sx={{ p: { xs: 2, sm: 3 }, mb: 3 }}>
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', sm: 'row' },
            justifyContent: 'space-between',
            alignItems: { xs: 'flex-start', sm: 'center' },
            gap: 2,
            mb: 2,
          }}
        >
          <Box>
            <Typography variant="h6">Market Chart</Typography>
            <Typography variant="caption" color="text.secondary">
              Settings are automatically saved
            </Typography>
          </Box>

          {/* Auto-refresh controls */}
          <Box
            sx={{
              display: 'flex',
              flexDirection: { xs: 'column', sm: 'row' },
              gap: 2,
              alignItems: { xs: 'stretch', sm: 'center' },
              width: { xs: '100%', sm: 'auto' },
            }}
          >
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

            <FormControl
              size="small"
              sx={{ minWidth: { xs: '100%', sm: 120 } }}
            >
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

        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', sm: 'row' },
            alignItems: { xs: 'stretch', sm: 'center' },
            gap: 2,
          }}
        >
          <Box sx={{ flex: 1 }}>
            <ChartControls
              instrument={instrument}
              granularity={granularity}
              onInstrumentChange={handleInstrumentChange}
              onGranularityChange={handleGranularityChange}
            />
          </Box>

          {/* Manual Refresh Button */}
          <Tooltip title="Refresh chart data">
            <IconButton
              onClick={handleManualRefresh}
              disabled={!hasOandaAccount}
              color="primary"
              size="small"
              sx={{ alignSelf: { xs: 'flex-end', sm: 'center' } }}
            >
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>

        <Box
          sx={{
            height: { xs: 300, sm: 400, md: 500 },
            position: 'relative',
            overflow: 'hidden',
          }}
        >
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
            <DashboardChart
              key={chartRefreshTrigger}
              instrument={instrument}
              granularity={granularity}
              height={500}
              timezone={timezone}
              autoRefresh={autoRefreshEnabled}
              refreshInterval={refreshInterval * 1000}
              onGranularityChange={(g) =>
                handleGranularityChange(g as Granularity)
              }
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
