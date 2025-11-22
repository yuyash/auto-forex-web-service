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

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Box } from '@mui/material';
import { FinancialChart } from './FinancialChart';
import type { OHLCData } from './FinancialChart';
import { transformCandles } from '../../utils/chartDataTransform';
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
  onResetView?: () => void;
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
  onResetView,
}) => {
  // Auth context for API token
  const { token } = useAuth();

  // State
  const [candles, setCandles] = useState<OHLCData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const currentGranularity = (propGranularity as OandaGranularity) || 'H1';
  const autoRefreshEnabled = propAutoRefresh;
  const refreshInterval = propRefreshInterval;

  // Ref for auto-refresh timer
  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
    <Box sx={{ width: '100%', maxWidth: '100%', boxSizing: 'border-box' }}>
      {/* Chart */}
      <FinancialChart
        data={candles}
        height={height}
        timezone={timezone}
        loading={loading}
        error={error}
        onLoadMore={handleLoadMore}
        showResetButton={false} // Reset button now in ChartControls
        enableMarkerToggle={false} // No markers for dashboard chart
        showGrid={true}
        showCrosshair={true}
        showOHLCTooltip={true}
        onResetView={onResetView}
      />
    </Box>
  );
};

export default DashboardChart;
