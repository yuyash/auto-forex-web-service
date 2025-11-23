/**
 * DashboardChart Component
 *
 * Simple chart for market monitoring.
 * - Loads 5000 candles initially
 * - Shows most recent 100 candles by default
 * - Update button reloads all data
 * - Auto-refresh updates data without changing viewport
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Box } from '@mui/material';
import { FinancialChart } from './FinancialChart';
import type { OHLCData } from './FinancialChart';
import { transformCandles } from '../../utils/chartDataTransform';
import type { OandaGranularity } from '../../types/oanda';
import { useAuth } from '../../contexts/AuthContext';

/**
 * DashboardChart Props
 */
export interface DashboardChartProps {
  instrument: string;
  granularity: string;
  height?: number;
  timezone?: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
  onResetView?: () => void;
  onUpdateView?: () => void;
}

/**
 * DashboardChart Component
 */
export const DashboardChart: React.FC<DashboardChartProps> = ({
  instrument,
  granularity: propGranularity,
  height = 500,
  timezone = 'UTC',
  autoRefresh = false,
  refreshInterval = 60000,
  onResetView,
  onUpdateView,
}) => {
  const { token } = useAuth();

  // State
  const [candles, setCandles] = useState<OHLCData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [latestPrice, setLatestPrice] = useState<number | null>(null);
  const [initialVisibleRange, setInitialVisibleRange] = useState<{
    from: Date;
    to: Date;
  } | null>(null);

  const currentGranularity = (propGranularity as OandaGranularity) || 'H1';

  // Refs
  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch 5000 candles
  const fetchAllCandles = useCallback(async () => {
    if (!token) {
      setError('Authentication token not available');
      setLoading(false);
      return;
    }

    console.log('[DashboardChart] Fetching 5000 candles');
    setLoading(true);
    setError(null);

    try {
      const url = `/api/candles?instrument=${instrument}&granularity=${currentGranularity}&count=5000`;

      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      const transformedCandles = transformCandles(data.candles || []);

      console.log('[DashboardChart] Loaded candles', {
        count: transformedCandles.length,
        firstDate: transformedCandles[0]?.date.toISOString(),
        lastDate:
          transformedCandles[transformedCandles.length - 1]?.date.toISOString(),
      });

      setCandles(transformedCandles);

      // Set latest price from the most recent candle
      if (transformedCandles.length > 0) {
        const latest = transformedCandles[transformedCandles.length - 1];
        setLatestPrice((latest.high + latest.low) / 2);

        // Set initial visible range to show last 100 candles
        const startIndex = Math.max(0, transformedCandles.length - 100);
        setInitialVisibleRange({
          from: transformedCandles[startIndex].date,
          to: latest.date,
        });
      }

      setLoading(false);
    } catch (err) {
      console.error('[DashboardChart] Error fetching candles:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch candles');
      setLoading(false);
    }
  }, [token, instrument, currentGranularity]);

  // Handle reset view
  const handleResetView = useCallback(() => {
    console.log('[DashboardChart] Reset view');
    fetchAllCandles();
    onResetView?.();
  }, [fetchAllCandles, onResetView]);

  // Handle update view
  const handleUpdateView = useCallback(() => {
    console.log('[DashboardChart] Update view');
    fetchAllCandles();
    onUpdateView?.();
  }, [fetchAllCandles, onUpdateView]);

  // Initial data fetch
  useEffect(() => {
    fetchAllCandles();
  }, [instrument, currentGranularity, fetchAllCandles]); // Reload when instrument or granularity changes

  // Set up auto-refresh timer
  useEffect(() => {
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }

    if (autoRefresh && refreshInterval > 0) {
      console.log('[DashboardChart] Setting up auto-refresh', {
        refreshInterval,
      });
      refreshTimerRef.current = setInterval(() => {
        console.log('[DashboardChart] Auto-refresh triggered');
        fetchAllCandles();
      }, refreshInterval);
    }

    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [autoRefresh, refreshInterval, fetchAllCandles]);

  return (
    <Box sx={{ width: '100%', maxWidth: '100%', boxSizing: 'border-box' }}>
      <FinancialChart
        data={candles}
        height={height}
        timezone={timezone}
        loading={loading}
        error={error}
        initialVisibleRange={initialVisibleRange || undefined}
        showResetButton={false}
        enableMarkerToggle={false}
        showGrid={true}
        showCrosshair={true}
        showOHLCTooltip={true}
        latestPrice={latestPrice}
        onResetView={handleResetView}
        onUpdateView={handleUpdateView}
      />
    </Box>
  );
};

export default DashboardChart;
