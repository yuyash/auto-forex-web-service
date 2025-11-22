/**
 * DashboardChart Component
 *
 * Simple chart for market monitoring without trade markers.
 * Displays OHLC candlestick chart with:
 * - Granularity controls
 * - Auto-refresh controls
 * - Scroll-based data loading
 * - No markers or overlays (simple market monitoring)
 *
 * Features:
 * - Auto-refresh enabled by default (60s interval, configurable)
 * - Loads more data on scroll
 * - Scrolls to latest data when new candles arrive
 */

import React, {
  useState,
  useEffect,
  useMemo,
  useCallback,
  useRef,
} from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  type SelectChangeEvent,
} from '@mui/material';
import { FinancialChart } from './FinancialChart';
import type { OHLCData } from './FinancialChart';
import { transformCandles } from '../../utils/chartDataTransform';
import { getAvailableGranularities } from '../../config/chartConfig';
import type { OandaGranularity } from '../../types/oanda';
import { CHART_CONFIG } from '../../config/chartConfig';
import { useAuth } from '../../contexts/AuthContext';

/**
 * DashboardChart Props
 */
export interface DashboardChartProps {
  instrument: string;
  granularity: string;
  height?: number;
  timezone?: string; // IANA timezone from global settings
  autoRefresh?: boolean;
  refreshInterval?: number;
  onGranularityChange?: (granularity: string) => void;
}

/**
 * DashboardChart Component
 */
export const DashboardChart: React.FC<DashboardChartProps> = ({
  instrument,
  granularity: propGranularity,
  height = CHART_CONFIG.DEFAULT_HEIGHT,
  timezone = 'UTC',
  autoRefresh: propAutoRefresh = CHART_CONFIG.DEFAULT_AUTO_REFRESH_ENABLED,
  refreshInterval:
    propRefreshInterval = CHART_CONFIG.DEFAULT_AUTO_REFRESH_INTERVAL,
  onGranularityChange,
}) => {
  // Auth context for API token
  const { token } = useAuth();

  // State
  const [candles, setCandles] = useState<OHLCData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentGranularity, setCurrentGranularity] =
    useState<OandaGranularity>((propGranularity as OandaGranularity) || 'H1');
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(propAutoRefresh);
  const [refreshInterval, setRefreshInterval] = useState(propRefreshInterval);

  // Ref for auto-refresh timer
  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Available granularities for selector
  const availableGranularities = useMemo(() => getAvailableGranularities(), []);

  // Fetch candles with exponential backoff retry logic
  const fetchCandles = useCallback(async () => {
    if (!token) {
      setError('Authentication token not available');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    const attemptFetch = async (attempt: number): Promise<void> => {
      try {
        // Build API URL - fetch recent candles using DEFAULT_FETCH_COUNT
        const url = `/api/candles?instrument=${instrument}&granularity=${currentGranularity}&count=${CHART_CONFIG.DEFAULT_FETCH_COUNT}`;

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
          throw new Error('Rate limited by API. Please wait before retrying.');
        }

        // Check for other errors
        if (!response.ok) {
          const error = new Error(
            `HTTP ${response.status}: ${response.statusText}`
          );
          // Mark client errors as non-retryable
          if (response.status >= 400 && response.status < 500) {
            (error as Error & { retryable?: boolean }).retryable = false;
          }
          throw error;
        }

        const data = await response.json();
        const apiCandles = data.candles || [];

        // Transform API candles to chart format
        const transformedCandles = transformCandles(apiCandles);
        setCandles(transformedCandles);
        setLoading(false);
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to fetch candles';

        // Check if error is retryable
        const isRetryable =
          !(err as Error & { retryable?: boolean }).retryable === false;

        // If this is the last attempt or error is not retryable, set error state
        if (attempt >= CHART_CONFIG.MAX_RETRY_ATTEMPTS - 1 || !isRetryable) {
          setError(errorMessage);
          setLoading(false);
          return;
        }

        // Wait before retrying with exponential backoff
        const delay = CHART_CONFIG.RETRY_DELAYS[attempt];
        console.warn(
          `Attempt ${attempt + 1} failed, retrying in ${delay}ms...`,
          err
        );
        await new Promise((resolve) => setTimeout(resolve, delay));

        // Retry
        await attemptFetch(attempt + 1);
      }
    };

    await attemptFetch(0);
  }, [token, instrument, currentGranularity]);

  // Initial data fetch
  useEffect(() => {
    fetchCandles();
  }, [fetchCandles]);

  // Handle granularity change
  const handleGranularityChange = useCallback(
    (event: SelectChangeEvent<string>) => {
      const newGranularity = event.target.value as OandaGranularity;
      setCurrentGranularity(newGranularity);

      // Notify parent component
      if (onGranularityChange) {
        onGranularityChange(newGranularity);
      }
    },
    [onGranularityChange]
  );

  // Handle auto-refresh toggle
  const handleAutoRefreshToggle = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setAutoRefreshEnabled(event.target.checked);
    },
    []
  );

  // Handle refresh interval change
  const handleRefreshIntervalChange = useCallback(
    (event: SelectChangeEvent<number>) => {
      setRefreshInterval(event.target.value as number);
    },
    []
  );

  // Set up auto-refresh timer
  useEffect(() => {
    // Clear existing timer
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }

    // Set up new timer if auto-refresh is enabled
    if (autoRefreshEnabled) {
      refreshTimerRef.current = setInterval(() => {
        fetchCandles();
      }, refreshInterval);
    }

    // Cleanup on unmount
    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [autoRefreshEnabled, refreshInterval, fetchCandles]);

  // Handle scroll-based data loading
  const handleLoadMore = useCallback(
    async (direction: 'older' | 'newer') => {
      if (!token || candles.length === 0) return;

      try {
        let url: string;

        if (direction === 'older') {
          // Load older data - use the timestamp of the first candle
          const firstCandle = candles[0];
          const beforeTimestamp = Math.floor(firstCandle.date.getTime() / 1000);
          url = `/api/candles?instrument=${instrument}&granularity=${currentGranularity}&count=${CHART_CONFIG.SCROLL_LOAD_COUNT}&before=${beforeTimestamp}`;
        } else {
          // Load newer data - fetch latest candles
          url = `/api/candles?instrument=${instrument}&granularity=${currentGranularity}&count=${CHART_CONFIG.SCROLL_LOAD_COUNT}`;
        }

        const response = await fetch(url, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          console.error('Failed to load more data:', response.statusText);
          return;
        }

        const data = await response.json();
        const apiCandles = data.candles || [];
        const transformedCandles = transformCandles(apiCandles);

        if (transformedCandles.length === 0) {
          return;
        }

        // Merge new candles with existing ones
        setCandles((prevCandles) => {
          if (direction === 'older') {
            // Add older candles to the beginning
            return [...transformedCandles, ...prevCandles];
          } else {
            // Add newer candles to the end, avoiding duplicates
            const lastTimestamp =
              prevCandles[prevCandles.length - 1].date.getTime();
            const newCandles = transformedCandles.filter(
              (c) => c.date.getTime() > lastTimestamp
            );
            return [...prevCandles, ...newCandles];
          }
        });
      } catch (err) {
        console.error('Error loading more data:', err);
      }
    },
    [token, instrument, currentGranularity, candles]
  );

  return (
    <Box>
      {/* Controls */}
      <Box
        sx={{
          mb: 2,
          display: 'flex',
          gap: 2,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
      >
        {/* Granularity selector */}
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Granularity</InputLabel>
          <Select
            value={currentGranularity}
            label="Granularity"
            onChange={handleGranularityChange}
          >
            {availableGranularities.map((gran) => (
              <MenuItem key={gran} value={gran}>
                {gran}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Auto-refresh toggle */}
        <FormControlLabel
          control={
            <Switch
              checked={autoRefreshEnabled}
              onChange={handleAutoRefreshToggle}
            />
          }
          label="Auto-refresh"
        />

        {/* Refresh interval selector */}
        {autoRefreshEnabled && (
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Interval</InputLabel>
            <Select
              value={refreshInterval}
              label="Interval"
              onChange={handleRefreshIntervalChange}
            >
              {CHART_CONFIG.AUTO_REFRESH_INTERVALS.map((interval) => (
                <MenuItem key={interval.value} value={interval.value}>
                  {interval.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
      </Box>

      {/* Chart */}
      <FinancialChart
        data={candles}
        height={height}
        timezone={timezone}
        loading={loading}
        error={error}
        onLoadMore={handleLoadMore}
        showResetButton={true}
        enableMarkerToggle={false} // No markers for dashboard chart
        showGrid={true}
        showCrosshair={true}
        showOHLCTooltip={true}
      />
    </Box>
  );
};

export default DashboardChart;
