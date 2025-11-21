/**
 * BacktestChart Component
 *
 * Specialized chart for backtest results with start/end markers and trade visualization.
 * Displays OHLC candlestick chart with:
 * - Start and end vertical lines marking backtest boundaries
 * - Trade markers (buy/sell) at execution points
 * - Strategy layer horizontal lines (if provided)
 * - Initial position marker (if provided)
 * - Granularity controls
 * - Marker visibility toggles
 *
 * Features:
 * - Automatic granularity calculation based on backtest duration
 * - Buffered range (2-3 candles before/after backtest period)
 * - No auto-refresh (backtest data is historical and immutable)
 * - Trade click handler for chart-to-table interaction
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
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
import {
  transformCandles,
  calculateBufferedRange,
} from '../../utils/chartDataTransform';
import {
  calculateGranularity,
  getAvailableGranularities,
} from '../../utils/granularityCalculator';
import type { OandaGranularity } from '../../types/oanda';
import type { Trade } from '../../types/execution';
import { CHART_CONFIG } from '../../config/chartConfig';
import { useAuth } from '../../contexts/AuthContext';

/**
 * Initial Position interface
 */
export interface InitialPosition {
  capital: number;
  timestamp: string;
}

/**
 * BacktestChart Props
 */
export interface BacktestChartProps {
  instrument: string;
  startDate: string; // ISO 8601
  endDate: string; // ISO 8601
  trades: Trade[];
  initialPosition?: InitialPosition;
  strategyLayers?: StrategyLayer[];
  granularity?: string;
  height?: number;
  timezone?: string; // IANA timezone from global settings
  onGranularityChange?: (granularity: string) => void;
  onTradeClick?: (tradeIndex: number) => void; // Called when user clicks a trade marker
}

/**
 * BacktestChart Component
 */
export const BacktestChartNew: React.FC<BacktestChartProps> = ({
  instrument,
  startDate,
  endDate,
  trades,
  initialPosition,
  strategyLayers = [],
  granularity: propGranularity,
  height = CHART_CONFIG.DEFAULT_HEIGHT,
  timezone = 'UTC',
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

  // Calculate initial granularity based on backtest duration
  const calculatedGranularity = useMemo(() => {
    try {
      const start = new Date(startDate);
      const end = new Date(endDate);
      return calculateGranularity(start, end);
    } catch (err) {
      console.error('Error calculating granularity:', err);
      return 'H1' as OandaGranularity;
    }
  }, [startDate, endDate]);

  // Use prop granularity if provided, otherwise use calculated
  useEffect(() => {
    if (propGranularity) {
      setCurrentGranularity(propGranularity as OandaGranularity);
    } else {
      setCurrentGranularity(calculatedGranularity);
    }
  }, [propGranularity, calculatedGranularity]);

  // Available granularities for selector
  const availableGranularities = useMemo(() => getAvailableGranularities(), []);

  // Parse dates
  const parsedStartDate = useMemo(() => new Date(startDate), [startDate]);
  const parsedEndDate = useMemo(() => new Date(endDate), [endDate]);

  // Calculate buffered range
  const bufferedRange = useMemo(() => {
    try {
      return calculateBufferedRange(
        parsedStartDate,
        parsedEndDate,
        currentGranularity
      );
    } catch (err) {
      console.error('Error calculating buffered range:', err);
      return { from: parsedStartDate, to: parsedEndDate };
    }
  }, [parsedStartDate, parsedEndDate, currentGranularity]);

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
        // Build API URL with buffered range
        const fromTimestamp = Math.floor(bufferedRange.from.getTime() / 1000);
        const toTimestamp = Math.floor(bufferedRange.to.getTime() / 1000);

        const url = `/api/candles?instrument=${instrument}&granularity=${currentGranularity}&from=${fromTimestamp}&to=${toTimestamp}`;

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
          // Don't retry on client errors (400, 401, 403, 404)
          if (response.status >= 400 && response.status < 500) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
          }
          // Retry on server errors (500+)
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        const apiCandles = data.candles || [];

        // Transform API candles to chart format
        const transformedCandles = transformCandles(apiCandles);
        setCandles(transformedCandles);
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to fetch candles';

        // Check if we should retry
        const isRateLimited = errorMessage.includes('Rate limited');
        const isServerError = errorMessage.includes('HTTP 5');
        const shouldRetry =
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
  }, [token, instrument, bufferedRange, currentGranularity]);

  // Fetch candles on mount and when dependencies change
  useEffect(() => {
    fetchCandles();
  }, [fetchCandles]);

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

  // Convert trades to chart markers with cyan/orange colors
  const tradeMarkers = useMemo<ChartMarker[]>(() => {
    if (!trades || trades.length === 0) {
      return [];
    }

    // Convert Trade format to ChartTrade format
    const chartTrades: ChartTrade[] = trades.map((trade) => ({
      timestamp: trade.entry_time, // Use entry_time as the marker timestamp
      action: trade.direction === 'long' ? 'buy' : 'sell',
      price: trade.entry_price,
      units: trade.units,
      pnl: trade.pnl,
    }));

    return createTradeMarkers(chartTrades);
  }, [trades]);

  // Create start/end markers with gray double circles
  const startEndMarkers = useMemo<ChartMarker[]>(() => {
    if (!candles || candles.length === 0) {
      return [];
    }

    // Find candles closest to start and end dates
    const startCandle =
      candles.find((c) => c.date >= parsedStartDate) || candles[0];
    const endCandle =
      candles.reverse().find((c) => c.date <= parsedEndDate) ||
      candles[candles.length - 1];

    return createStartEndMarkers(
      parsedStartDate,
      parsedEndDate,
      startCandle.high,
      endCandle.high
    );
  }, [parsedStartDate, parsedEndDate, candles]);

  // Create vertical lines for start and end
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

    // End line
    lines.push(
      createVerticalLine(
        parsedEndDate,
        'END',
        '#757575', // Gray
        2,
        '5,5' // Dashed
      )
    );

    return lines;
  }, [parsedStartDate, parsedEndDate]);

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

  // Create initial position marker if provided
  const initialPositionMarker = useMemo<ChartMarker | null>(() => {
    if (!initialPosition || !candles || candles.length === 0) {
      return null;
    }

    const positionDate = new Date(initialPosition.timestamp);
    const nearestCandle =
      candles.find((c) => c.date >= positionDate) || candles[0];

    return {
      id: 'initial-position',
      date: positionDate,
      price: nearestCandle.high,
      type: 'initial_entry',
      color: '#2196f3', // Blue
      shape: 'doubleCircle',
      label: 'INITIAL',
      tooltip: `Initial Capital: $${initialPosition.capital.toFixed(2)}`,
    };
  }, [initialPosition, candles]);

  // Combine all markers
  const allMarkers = useMemo(() => {
    const markers = [...tradeMarkers, ...startEndMarkers];
    if (initialPositionMarker) {
      markers.push(initialPositionMarker);
    }
    return markers;
  }, [tradeMarkers, startEndMarkers, initialPositionMarker]);

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
      {/* Granularity Selector */}
      <Box sx={{ mb: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
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
        <Typography variant="body2" color="text.secondary">
          Backtest: {parsedStartDate.toLocaleDateString()} -{' '}
          {parsedEndDate.toLocaleDateString()}
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
        initialVisibleRange={bufferedRange}
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

export default BacktestChartNew;
