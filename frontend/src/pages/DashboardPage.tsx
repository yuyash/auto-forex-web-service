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
import { CacheManager } from '../utils/CacheManager';
import type { IChartApi } from 'lightweight-charts';

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

  // Manual refresh state
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Chart data state for lazy loading with caching
  const [chartData, setChartData] = useState<OHLCData[]>([]);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasOandaAccount, setHasOandaAccount] = useState<boolean>(true);
  const [oandaAccountId, setOandaAccountId] = useState<string | undefined>(
    undefined
  );

  // Error handling state
  const [chartError, setChartError] = useState<string | null>(null);
  const [isRateLimited, setIsRateLimited] = useState(false);
  const [rateLimitRetryTime, setRateLimitRetryTime] = useState<number | null>(
    null
  );

  // Cache manager for storing all fetched candles
  const cacheManagerRef = useRef<CacheManager>(new CacheManager());

  // Rate limit countdown timer effect
  useEffect(() => {
    if (!isRateLimited || !rateLimitRetryTime) {
      return;
    }

    const countdownInterval = setInterval(() => {
      if (rateLimitRetryTime <= Date.now()) {
        setIsRateLimited(false);
        setRateLimitRetryTime(null);
        clearInterval(countdownInterval);
      } else {
        // Force re-render to update countdown display
        setRateLimitRetryTime((prev) => prev);
      }
    }, 1000);

    return () => {
      clearInterval(countdownInterval);
    };
  }, [isRateLimited, rateLimitRetryTime]);

  // Load a large batch of historical data (up to 5000 candles) and cache it
  const loadAndCacheHistoricalData = useCallback(
    async (
      inst: string,
      gran: string,
      count = 5000,
      before?: number
    ): Promise<OHLCData[]> => {
      try {
        let url = `/api/candles?instrument=${inst}&granularity=${gran}&count=${count}`;
        if (before) {
          url += `&before=${before}`;
        }

        const response = await fetch(url, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        // Check for rate limiting
        const isRateLimitedResponse =
          response.status === 429 ||
          response.headers.get('X-Rate-Limited') === 'true';

        if (isRateLimitedResponse) {
          console.warn('Rate limited by API, using cached data');
          setIsRateLimited(true);
          setRateLimitRetryTime(Date.now() + 60000); // 60 seconds from now
          setChartError(null); // Clear any previous errors

          // Return empty array to use cached data
          return [];
        }

        if (!response.ok) {
          const errorData = await response.json();
          if (errorData.error_code === 'NO_OANDA_ACCOUNT') {
            setHasOandaAccount(false);
            setChartError(null); // Clear error as this is expected state
            return [];
          }

          // Log error and display message without clearing chart data
          const errorMessage = `Failed to load data: ${response.status} ${response.statusText}`;
          console.error(errorMessage, errorData);
          setChartError(errorMessage);
          return [];
        }

        const data = await response.json();
        const candles = data.candles || [];

        if (candles.length > 0) {
          // Use CacheManager to merge new data with existing cache
          cacheManagerRef.current.merge(inst, gran, candles);

          const timeRange = cacheManagerRef.current.getTimeRange(inst, gran);
          if (timeRange) {
            console.log(
              `Cached data for ${inst}_${gran}: ${timeRange.oldest} to ${timeRange.newest}`
            );
          }
        }

        // Clear errors on successful fetch
        setChartError(null);
        setIsRateLimited(false);
        setRateLimitRetryTime(null);
        setHasOandaAccount(true);
        return candles;
      } catch (err) {
        // Log error to console for debugging
        console.error('Error loading historical data:', err);

        // Display error message without clearing chart data
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to load historical data';
        setChartError(errorMessage);

        return [];
      }
    },
    [token]
  );

  // Load initial visible data from cache or API
  const loadHistoricalData = useCallback(
    async (inst: string, gran: string, count = 1000): Promise<OHLCData[]> => {
      // Check cache first using CacheManager
      const cachedData = cacheManagerRef.current.get(inst, gran);

      // If we have cached data, return the most recent 'count' candles
      if (cachedData && cachedData.length > 0) {
        console.log(`Using ${cachedData.length} cached candles`);
        return cachedData.slice(-count);
      }

      // Otherwise, fetch a large batch and cache it
      console.log('No cache found, fetching initial batch of 5000 candles');
      const candles = await loadAndCacheHistoricalData(inst, gran, 5000);

      // Return the most recent 'count' candles for display
      return candles.slice(-count);
    },
    [loadAndCacheHistoricalData]
  );

  // Load older data (for scrolling left/back in time)
  const loadOlderData = useCallback(
    async (inst: string, gran: string): Promise<OHLCData[]> => {
      if (isLoadingMore) {
        console.log('Already loading, skipping...');
        return [];
      }

      setIsLoadingMore(true);

      try {
        const cachedData = cacheManagerRef.current.get(inst, gran) || [];

        // Use a ref to get the current chart data to avoid stale closure
        const currentOldest = chartData.length > 0 ? chartData[0].time : null;

        if (!currentOldest) {
          console.log('No current data, cannot load older');
          return [];
        }

        // Check if we have older data in cache
        const olderCachedData = cachedData.filter(
          (c) => c.time < currentOldest
        );

        if (olderCachedData.length > 0) {
          // Return up to 200 older candles from cache
          const candlesToAdd = olderCachedData.slice(-200);
          console.log(
            `Loading ${candlesToAdd.length} older candles from cache (oldest: ${candlesToAdd[0].time})`
          );
          setChartData((prev) => {
            // Double-check to avoid duplicates
            const newData = [...candlesToAdd, ...prev];
            const uniqueData = Array.from(
              new Map(newData.map((c) => [c.time, c])).values()
            ).sort((a, b) => a.time - b.time);
            return uniqueData;
          });
          return candlesToAdd;
        }

        // If no older cached data, fetch more from API
        const timeRange = cacheManagerRef.current.getTimeRange(inst, gran);
        if (timeRange) {
          console.log('Fetching older data from API (5000 candles)');
          const olderCandles = await loadAndCacheHistoricalData(
            inst,
            gran,
            5000,
            timeRange.oldest
          );

          if (olderCandles.length > 0) {
            // Add the newest 200 of the fetched candles to chart
            const candlesToAdd = olderCandles.slice(-200);
            console.log(
              `Adding ${candlesToAdd.length} newly fetched older candles`
            );
            setChartData((prev) => {
              const newData = [...candlesToAdd, ...prev];
              const uniqueData = Array.from(
                new Map(newData.map((c) => [c.time, c])).values()
              ).sort((a, b) => a.time - b.time);
              return uniqueData;
            });
            return candlesToAdd;
          }
        }

        console.log('No older data available');
        return [];
      } catch (err) {
        console.error('Error loading older data:', err);
        return [];
      } finally {
        setIsLoadingMore(false);
      }
    },
    [isLoadingMore, chartData, loadAndCacheHistoricalData]
  );

  // Load newer data (for scrolling right/forward in time)
  const loadNewerData = useCallback(
    async (inst: string, gran: string): Promise<OHLCData[]> => {
      if (isLoadingMore) {
        console.log('Already loading, skipping...');
        return [];
      }

      setIsLoadingMore(true);

      try {
        const cachedData = cacheManagerRef.current.get(inst, gran) || [];
        const currentNewest =
          chartData.length > 0 ? chartData[chartData.length - 1].time : null;

        console.log('=== LOAD NEWER DATA ===');
        console.log('Current chart data length:', chartData.length);
        console.log('Current newest time:', currentNewest);
        console.log('Cached data length:', cachedData.length);

        if (!currentNewest) {
          console.log('No current data, cannot load newer');
          return [];
        }

        // Check if we have newer data in cache
        const newerCachedData = cachedData.filter(
          (c) => c.time > currentNewest
        );
        console.log('Newer cached data available:', newerCachedData.length);

        if (newerCachedData.length > 0) {
          // Return up to 200 newer candles from cache
          const candlesToAdd = newerCachedData.slice(0, 200);
          console.log(
            `Loading ${candlesToAdd.length} newer candles from cache (newest: ${candlesToAdd[candlesToAdd.length - 1].time})`
          );
          setChartData((prev) => {
            console.log('Before adding newer data, prev length:', prev.length);
            // Double-check to avoid duplicates
            const newData = [...prev, ...candlesToAdd];
            const uniqueData = Array.from(
              new Map(newData.map((c) => [c.time, c])).values()
            ).sort((a, b) => a.time - b.time);
            console.log(
              'After adding newer data, new length:',
              uniqueData.length
            );
            return uniqueData;
          });
          return candlesToAdd;
        }

        // If we're at the newest cached data, fetch latest from API
        console.log('Fetching latest data from API (5000 candles)');
        const latestCandles = await loadAndCacheHistoricalData(
          inst,
          gran,
          5000
        );

        if (latestCandles.length > 0) {
          // Find candles newer than current newest
          const newCandles = latestCandles.filter(
            (c) => c.time > currentNewest
          );
          console.log('New candles from API:', newCandles.length);

          if (newCandles.length > 0) {
            const candlesToAdd = newCandles.slice(0, 200);
            console.log(
              `Adding ${candlesToAdd.length} newly fetched newer candles`
            );
            setChartData((prev) => {
              console.log('Before adding API data, prev length:', prev.length);
              const newData = [...prev, ...candlesToAdd];
              const uniqueData = Array.from(
                new Map(newData.map((c) => [c.time, c])).values()
              ).sort((a, b) => a.time - b.time);
              console.log(
                'After adding API data, new length:',
                uniqueData.length
              );
              return uniqueData;
            });
            return candlesToAdd;
          } else {
            console.log(
              'No newer data available (already at latest) - API returned same data'
            );
            // Return empty array to signal no new data was added
            // This will prevent the chart from trying to restore a range beyond the data
            return [];
          }
        }

        console.log('No newer data available (already at latest)');
        return [];
      } catch (err) {
        console.error('Error loading newer data:', err);
        return [];
      } finally {
        setIsLoadingMore(false);
      }
    },
    [isLoadingMore, chartData, loadAndCacheHistoricalData]
  );

  // Initial chart data load
  useEffect(() => {
    const loadInitialChartData = async () => {
      // Clear cache when instrument or granularity changes
      const cachedData = cacheManagerRef.current.get(instrument, granularity);
      if (!cachedData) {
        // Clear entire cache when switching to a new instrument/granularity combination
        cacheManagerRef.current.clear();
      }

      // Add a small delay to prevent rapid-fire requests on mount
      await new Promise((resolve) => setTimeout(resolve, 100));
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

  // Ref to track if user is viewing latest candles
  const isViewingLatestRef = useRef(true);

  // Ref to store the chart API for checking scroll position
  const chartApiRef = useRef<IChartApi | null>(null);

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

  // Auto-refresh effect for chart data
  const chartRefreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(
    null
  );

  useEffect(() => {
    // Clear existing chart refresh timer
    if (chartRefreshTimerRef.current) {
      clearInterval(chartRefreshTimerRef.current);
      chartRefreshTimerRef.current = null;
    }

    // Set up chart data auto-refresh if enabled
    if (autoRefreshEnabled && refreshInterval > 0 && hasOandaAccount) {
      chartRefreshTimerRef.current = setInterval(async () => {
        console.log('Auto-refresh: Fetching latest chart data');

        try {
          // Fetch latest data only for current instrument/granularity
          const latestCandles = await loadAndCacheHistoricalData(
            instrument,
            granularity,
            5000
          );

          if (latestCandles.length > 0) {
            console.log(
              `Auto-refresh: Fetched ${latestCandles.length} candles`
            );

            // Get the current newest time in chart data
            const currentNewest =
              chartData.length > 0 ? chartData[chartData.length - 1].time : 0;

            // Find only new candles that don't exist in current chart data
            const newCandles = latestCandles.filter(
              (c) => c.time > currentNewest
            );

            if (newCandles.length > 0) {
              console.log(
                `Auto-refresh: Adding ${newCandles.length} new candles`
              );

              // Check if user is viewing the latest candles
              // User is viewing latest if they're within 50 bars of the end
              const isViewingLatest = isViewingLatestRef.current;

              // Merge new candles into chart data
              setChartData((prev) => {
                const merged = [...prev, ...newCandles];
                // Remove duplicates and sort
                const uniqueData = Array.from(
                  new Map(merged.map((c) => [c.time, c])).values()
                ).sort((a, b) => a.time - b.time);
                return uniqueData;
              });

              // Auto-scroll to end if viewing latest candles
              if (isViewingLatest) {
                console.log(
                  'Auto-refresh: User is viewing latest, will auto-scroll'
                );
                // Trigger scroll to end after data is updated
                setTimeout(() => {
                  if (chartApiRef.current) {
                    try {
                      chartApiRef.current.timeScale().scrollToRealTime();
                    } catch (err) {
                      console.error('Error scrolling to real time:', err);
                    }
                  }
                }, 100);
              } else {
                console.log(
                  'Auto-refresh: User is viewing historical data, preserving scroll position'
                );
              }
            } else {
              console.log(
                'Auto-refresh: No new candles to add (already up to date)'
              );
            }
          }
        } catch (err) {
          console.error('Auto-refresh error:', err);
          // Error is already handled by loadAndCacheHistoricalData
        }
      }, refreshInterval * 1000);
    }

    return () => {
      if (chartRefreshTimerRef.current) {
        clearInterval(chartRefreshTimerRef.current);
        chartRefreshTimerRef.current = null;
      }
    };
  }, [
    autoRefreshEnabled,
    refreshInterval,
    hasOandaAccount,
    instrument,
    granularity,
    chartData,
    loadAndCacheHistoricalData,
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

  // Handle manual refresh
  const handleManualRefresh = useCallback(async () => {
    if (isRefreshing) {
      console.log('Refresh already in progress, skipping...');
      return;
    }

    setIsRefreshing(true);
    console.log('Manual refresh triggered');

    try {
      // Fetch latest 5000 candles
      const latestCandles = await loadAndCacheHistoricalData(
        instrument,
        granularity,
        5000
      );

      if (latestCandles.length > 0) {
        console.log(`Fetched ${latestCandles.length} candles during refresh`);

        // Get the current newest time in chart data
        const currentNewest =
          chartData.length > 0 ? chartData[chartData.length - 1].time : 0;

        // Find only new candles that don't exist in current chart data
        const newCandles = latestCandles.filter((c) => c.time > currentNewest);

        if (newCandles.length > 0) {
          console.log(`Adding ${newCandles.length} new candles to chart`);
          // Merge new candles into chart data
          setChartData((prev) => {
            const merged = [...prev, ...newCandles];
            // Remove duplicates and sort
            const uniqueData = Array.from(
              new Map(merged.map((c) => [c.time, c])).values()
            ).sort((a, b) => a.time - b.time);
            return uniqueData;
          });
        } else {
          console.log('No new candles to add (already up to date)');
        }
      }
    } catch (err) {
      console.error('Error during manual refresh:', err);
      // Error is already handled by loadAndCacheHistoricalData
    } finally {
      setIsRefreshing(false);
    }
  }, [
    isRefreshing,
    instrument,
    granularity,
    chartData,
    loadAndCacheHistoricalData,
  ]);

  // Callback to track when user is viewing latest candles
  const handleViewingLatestChange = useCallback((isViewingLatest: boolean) => {
    isViewingLatestRef.current = isViewingLatest;
  }, []);

  // Callback when chart is ready
  const handleChartReady = useCallback((chartApi: IChartApi) => {
    chartApiRef.current = chartApi;
  }, []);

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

      {/* Rate Limit Warning Banner */}
      {isRateLimited && rateLimitRetryTime && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 0.5 }}>
            Rate Limited - Using Cached Data
          </Typography>
          <Typography variant="body2">
            API rate limit reached. Displaying cached data. You can retry in{' '}
            {Math.ceil((rateLimitRetryTime - Date.now()) / 1000)} seconds.
          </Typography>
        </Alert>
      )}

      {/* Chart Error Message */}
      {chartError && !isRateLimited && (
        <Alert
          severity="error"
          sx={{ mb: 3 }}
          onClose={() => setChartError(null)}
        >
          <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 0.5 }}>
            Chart Data Error
          </Typography>
          <Typography variant="body2">
            {chartError}. Displaying cached data if available.
          </Typography>
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
              disabled={isRefreshing || !hasOandaAccount}
              color="primary"
              size="small"
              sx={{ ml: 'auto' }}
            >
              {isRefreshing ? <CircularProgress size={20} /> : <RefreshIcon />}
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
              data={chartData}
              positions={currentPositions}
              orders={currentOrders}
              enableRealTimeUpdates={hasOandaAccount && !!oandaAccountId}
              accountId={oandaAccountId}
              onLoadOlderData={loadOlderData}
              onLoadNewerData={loadNewerData}
              onViewingLatestChange={handleViewingLatestChange}
              onChartReady={handleChartReady}
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
