/**
 * TradingTaskChart Component
 *
 * Specialized chart for live trading tasks with real-time updates.
 * Displays OHLC candlestick chart with:
 * - Start vertical line marking task start
 * - Stop vertical line (if task is stopped)
 * - Trade markers (buy/sell) at execution points
 * - Strategy layer horizontal lines (if provided)
 * - Granularity controls
 * - Auto-refresh controls
 * - Marker visibility toggles
 *
 * Features:
 * - Auto-refresh enabled by default (60s interval, configurable)
 * - Scrolls to latest data when new candles arrive
 * - Updates markers when new trades occur
 * - Trade click handler for chart-to-table interaction
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
  Typography,
  Switch,
  FormControlLabel,
  type SelectChangeEvent,
} from '@mui/material';
import { FinancialChart } from '../chart/FinancialChart';
import type { OHLCData } from '../chart/FinancialChart';
import type {
  ChartMarker,
  VerticalLine,
  HorizontalLine,
  Trade as ChartTrade,
  StrategyLayer,
} from '../../utils/chartMarkers';
import {
  createTradeMarkers,
  createStartEndMarkers,
  createVerticalLine,
  createHorizontalLine,
} from '../../utils/chartMarkers';
import { transformCandles } from '../../utils/chartDataTransform';
import { calculateGranularity } from '../../utils/granularityCalculator';
import { useSupportedGranularities } from '../../hooks/useMarketConfig';
import type { OandaGranularity } from '../../types/oanda';
import type { Trade } from '../../types/execution';
import { CHART_CONFIG } from '../../config/chartConfig';
import { useAuth } from '../../contexts/AuthContext';

/**
 * TradingTaskChart Props
 */
export interface TradingTaskChartProps {
  instrument: string;
  startDate: string; // ISO 8601
  stopDate?: string; // ISO 8601, optional (null if still running)
  trades: Trade[];
  strategyLayers?: StrategyLayer[];
  granularity?: string;
  height?: number;
  timezone?: string; // IANA timezone from global settings
  autoRefresh?: boolean;
  refreshInterval?: number;
  onGranularityChange?: (granularity: string) => void;
  onTradeClick?: (tradeIndex: number) => void; // Called when user clicks a trade marker
}

/**
 * TradingTaskChart Component
 */
export const TradingTaskChart: React.FC<TradingTaskChartProps> = ({
  instrument,
  startDate,
  stopDate,
  trades,
  strategyLayers = [],
  granularity: propGranularity,
  height = CHART_CONFIG.DEFAULT_HEIGHT,
  timezone = 'UTC',
  autoRefresh: propAutoRefresh = CHART_CONFIG.DEFAULT_AUTO_REFRESH_ENABLED,
  refreshInterval:
    propRefreshInterval = CHART_CONFIG.DEFAULT_AUTO_REFRESH_INTERVAL,
  onGranularityChange,
  onTradeClick,
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
  const refreshTimerRef = useRef<number | null>(null);

  // Calculate initial granularity based on task duration
  const calculatedGranularity = useMemo(() => {
    try {
      const start = new Date(startDate);
      const end = stopDate ? new Date(stopDate) : new Date();
      return calculateGranularity(start, end);
    } catch (err) {
      console.error('Error calculating granularity:', err);
      return 'H1' as OandaGranularity;
    }
  }, [startDate, stopDate]);

  // Use prop granularity if provided, otherwise use calculated
  useEffect(() => {
    if (propGranularity) {
      setCurrentGranularity(propGranularity as OandaGranularity);
    } else {
      setCurrentGranularity(calculatedGranularity);
    }
  }, [propGranularity, calculatedGranularity]);

  // Available granularities for selector (with human-readable labels)
  const { granularities: availableGranularities } = useSupportedGranularities();

  // Parse dates
  const parsedStartDate = useMemo(() => new Date(startDate), [startDate]);
  const parsedStopDate = useMemo(
    () => (stopDate ? new Date(stopDate) : null),
    [stopDate]
  );

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
        // Build API URL - fetch from start time to current time
        const fromTimestamp = Math.floor(parsedStartDate.getTime() / 1000);
        const toTimestamp = Math.floor(Date.now() / 1000);

        const url = `/api/candles?instrument=${instrument}&granularity=${currentGranularity}&from=${fromTimestamp}&to=${toTimestamp}&count=${CHART_CONFIG.DEFAULT_FETCH_COUNT}`;

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
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to fetch candles';

        // Check if error is explicitly marked as non-retryable
        const isNonRetryable =
          err instanceof Error &&
          (err as Error & { retryable?: boolean }).retryable === false;

        // Check if we should retry
        const isRateLimited = errorMessage.includes('Rate limited');
        const isServerError = errorMessage.includes('HTTP 5');
        const shouldRetry =
          !isNonRetryable &&
          (isServerError || isRateLimited) &&
          attempt < CHART_CONFIG.MAX_RETRY_ATTEMPTS;

        if (shouldRetry) {
          const delay = CHART_CONFIG.RETRY_DELAYS[attempt];
          console.warn(
            `Attempt ${attempt + 1} failed, retrying in ${delay}ms...`,
            errorMessage
          );

          await new Promise((resolve) => setTimeout(resolve, delay));
          return attemptFetch(attempt + 1);
        } else {
          // Max retries exceeded or non-retryable error
          setError(errorMessage);
          console.error('Error fetching candles:', err);
        }
      }
    };

    try {
      await attemptFetch(0);
    } finally {
      setLoading(false);
    }
  }, [token, instrument, parsedStartDate, currentGranularity]);

  // Fetch candles on mount and when dependencies change
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

  // Handle granularity change
  const handleGranularityChange = useCallback(
    (event: SelectChangeEvent<OandaGranularity>) => {
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

  // Helper function to find nearest candle date
  const findNearestCandleDate = useCallback(
    (targetDate: Date): Date | null => {
      if (!candles || candles.length === 0) return null;

      let nearest = candles[0].date;
      let minDiff = Math.abs(candles[0].date.getTime() - targetDate.getTime());
      for (let i = 1; i < candles.length; i++) {
        const d = candles[i].date;
        const diff = Math.abs(d.getTime() - targetDate.getTime());
        if (diff < minDiff) {
          minDiff = diff;
          nearest = d;
        }
      }
      return nearest;
    },
    [candles]
  );

  // Convert trades to chart markers with cyan/orange colors, aligning to nearest candle
  const tradeMarkers = useMemo<ChartMarker[]>(() => {
    if (!trades || trades.length === 0 || !candles || candles.length === 0) {
      return [];
    }

    // Convert Trade format to ChartTrade format with aligned dates
    const chartTrades: ChartTrade[] = trades.map((trade) => {
      const tradeDate = new Date(trade.entry_time);
      const alignedDate = findNearestCandleDate(tradeDate) || tradeDate;
      return {
        timestamp: alignedDate.toISOString(),
        action: trade.direction === 'long' ? 'buy' : 'sell',
        price: trade.entry_price,
        units: trade.units,
        pnl: trade.pnl,
      };
    });

    return createTradeMarkers(chartTrades);
  }, [trades, candles, findNearestCandleDate]);

  // Create start/end markers with gray double circles
  const startEndMarkers = useMemo<ChartMarker[]>(() => {
    if (!candles || candles.length === 0) {
      return [];
    }

    // Find candle closest to start date
    const startCandle =
      candles.find((c) => c.date >= parsedStartDate) || candles[0];

    // Find candle closest to stop date (if stopped)
    let stopCandle = null;
    if (parsedStopDate) {
      stopCandle =
        candles.reverse().find((c) => c.date <= parsedStopDate) ||
        candles[candles.length - 1];
    }

    // Use candle-aligned dates for markers
    const alignedStartDate = findNearestCandleDate(parsedStartDate);
    const alignedStopDate = parsedStopDate
      ? findNearestCandleDate(parsedStopDate)
      : null;

    return createStartEndMarkers(
      alignedStartDate || parsedStartDate,
      alignedStopDate,
      startCandle.high,
      stopCandle?.high
    );
  }, [parsedStartDate, parsedStopDate, candles, findNearestCandleDate]);

  // Create vertical lines for start and stop
  const verticalLines = useMemo<VerticalLine[]>(() => {
    const lines: VerticalLine[] = [];

    // Start line
    lines.push(
      createVerticalLine(
        parsedStartDate,
        'START',
        '#757575', // Gray
        2,
        '5,5' // Dashed
      )
    );

    // Stop line (if task is stopped)
    if (parsedStopDate) {
      lines.push(
        createVerticalLine(
          parsedStopDate,
          'STOP',
          '#757575', // Gray
          2,
          '5,5' // Dashed
        )
      );
    }

    return lines;
  }, [parsedStartDate, parsedStopDate]);

  // Create horizontal lines for strategy layers
  const horizontalLines = useMemo<HorizontalLine[]>(() => {
    if (!strategyLayers || strategyLayers.length === 0) {
      return [];
    }

    return strategyLayers.map((layer) =>
      createHorizontalLine(
        layer.price,
        layer.label,
        layer.color || '#9c27b0', // Purple default
        1,
        '5,5' // Dashed
      )
    );
  }, [strategyLayers]);

  // Combine all markers
  const allMarkers = useMemo(() => {
    return [...tradeMarkers, ...startEndMarkers];
  }, [tradeMarkers, startEndMarkers]);

  // Handle marker click - map marker clicks to trade indices
  const handleMarkerClick = useCallback(
    (marker: ChartMarker) => {
      if (!onTradeClick) {
        return;
      }

      // Extract trade index from marker ID
      // Trade markers have IDs like "trade-0", "trade-1", etc.
      if (marker.id && marker.id.startsWith('trade-')) {
        const tradeIndex = parseInt(marker.id.replace('trade-', ''), 10);
        if (!isNaN(tradeIndex)) {
          onTradeClick(tradeIndex);
        }
      }
    },
    [onTradeClick]
  );

  return (
    <Box>
      {/* Controls */}
      <Box
        sx={{
          mb: 2,
          display: 'flex',
          gap: 2,
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        {/* Granularity Selector */}
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Granularity</InputLabel>
          <Select
            value={currentGranularity}
            label="Granularity"
            onChange={handleGranularityChange}
          >
            {availableGranularities.map((gran) => (
              <MenuItem key={gran.value} value={gran.value}>
                {gran.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Auto-refresh Toggle */}
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

        {/* Refresh Interval Selector */}
        {autoRefreshEnabled && (
          <FormControl size="small" sx={{ minWidth: 120 }}>
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

        {/* Task Info */}
        <Typography variant="body2" color="text.secondary">
          Started: {parsedStartDate.toLocaleDateString()}
          {parsedStopDate &&
            ` | Stopped: ${parsedStopDate.toLocaleDateString()}`}
        </Typography>
      </Box>

      {/* Chart */}
      <FinancialChart
        data={candles}
        height={height}
        markers={allMarkers}
        verticalLines={verticalLines}
        horizontalLines={horizontalLines}
        onMarkerClick={handleMarkerClick}
        timezone={timezone}
        showResetButton={true}
        enableMarkerToggle={true}
        showOHLCTooltip={true}
        showGrid={true}
        showCrosshair={true}
        loading={loading}
        error={error}
      />
    </Box>
  );
};

export default TradingTaskChart;
