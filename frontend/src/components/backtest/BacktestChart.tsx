/**
 * BacktestChart Component
 *
 * Chart for backtest results - uses the same implementation as DashboardChart
 * with trade markers overlaid.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  CircularProgress,
  Typography,
  type SelectChangeEvent,
} from '@mui/material';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import { FinancialChart } from '../chart/FinancialChart';
import type { OHLCData } from '../chart/FinancialChart';
import type { ChartMarker } from '../../utils/chartMarkers';
import { createFloorStrategyMarkers } from '../../utils/floorStrategyMarkers';
import { transformCandles } from '../../utils/chartDataTransform';
import type { OandaGranularity } from '../../types/oanda';
import type { BacktestStrategyEvent } from '../../types/execution';
import { useAuth } from '../../contexts/AuthContext';
import { useSupportedGranularities } from '../../hooks/useMarketConfig';

/**
 * BacktestChart Props
 */
export interface BacktestChartProps {
  instrument: string;
  startDate: string; // ISO 8601 - backtest period start
  endDate: string; // ISO 8601 - backtest period end
  strategyEvents?: BacktestStrategyEvent[];
  height?: number;
  timezone?: string;
  onTradeClick?: (marker: ChartMarker) => void;
}

/**
 * BacktestChart Component
 */
export const BacktestChart: React.FC<BacktestChartProps> = ({
  instrument: propInstrument,
  startDate,
  endDate,
  strategyEvents,
  height = 500,
  timezone = 'UTC',
  onTradeClick,
}) => {
  const { token } = useAuth();

  // Fetch supported granularities
  const { granularities, isLoading: granularitiesLoading } =
    useSupportedGranularities();

  // State - use prop instrument (from strategy config), allow granularity changes
  const instrument = propInstrument;
  // Default to H1 for backtest charts to avoid exceeding OANDA's 5000 candle limit
  const [granularity, setGranularity] = useState<OandaGranularity>('H1');
  const [candles, setCandles] = useState<OHLCData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [latestPrice, setLatestPrice] = useState<number | null>(null);
  const [initialVisibleRange, setInitialVisibleRange] = useState<{
    from: Date;
    to: Date;
  } | null>(null);

  // Fetch candles within backtest period
  const fetchAllCandles = useCallback(async () => {
    if (!token) {
      setError('Authentication token not available');
      setLoading(false);
      return;
    }

    if (import.meta.env.DEV) {
      console.log('[BacktestChart] Fetching candles for backtest period');
    }
    setLoading(true);
    setError(null);

    try {
      // Convert to RFC3339 format for OANDA API
      const fromTime = new Date(startDate).toISOString();
      const toTime = new Date(endDate).toISOString();

      if (import.meta.env.DEV) {
        console.log('[BacktestChart] Request params', {
          startDate,
          endDate,
          fromTime,
          toTime,
        });
      }

      const url = `/api/candles?instrument=${instrument}&granularity=${granularity}&from_time=${encodeURIComponent(fromTime)}&to_time=${encodeURIComponent(toTime)}`;

      if (import.meta.env.DEV) {
        console.log('[BacktestChart] Fetching URL:', url);
      }

      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      const transformedCandles = transformCandles(data.candles || []);

      if (import.meta.env.DEV) {
        console.log('[BacktestChart] Loaded candles', {
          count: transformedCandles.length,
          firstDate: transformedCandles[0]?.date.toISOString(),
          lastDate:
            transformedCandles[
              transformedCandles.length - 1
            ]?.date.toISOString(),
          backtestPeriod: `${startDate} to ${endDate}`,
        });
      }

      setCandles(transformedCandles);

      // Set latest price from the most recent candle
      if (transformedCandles.length > 0) {
        const latest = transformedCandles[transformedCandles.length - 1];
        setLatestPrice((latest.high + latest.low) / 2);
      }

      // Set initial visible range to the REQUESTED backtest period
      // This allows gap detection to work by comparing requested vs actual data
      setInitialVisibleRange({
        from: new Date(startDate),
        to: new Date(endDate),
      });

      setLoading(false);
    } catch (err) {
      console.error('[BacktestChart] Error fetching candles:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch candles');
      setLoading(false);
    }
  }, [token, instrument, granularity, startDate, endDate]);

  // Handle reset view
  const handleResetView = useCallback(() => {
    if (import.meta.env.DEV) {
      console.log('[BacktestChart] Reset view');
    }
    fetchAllCandles();
  }, [fetchAllCandles]);

  // Initial data fetch
  useEffect(() => {
    fetchAllCandles();
  }, [instrument, granularity, fetchAllCandles]);

  // Handle granularity change
  const handleGranularityChange = (event: SelectChangeEvent<string>) => {
    setGranularity(event.target.value as OandaGranularity);
  };

  // Convert trades and events to chart markers
  const tradeMarkers = useMemo<ChartMarker[]>(() => {
    const markers: ChartMarker[] = [];

    console.log('[BacktestChart] Candles:', candles);

    // Add strategy event markers only (no trade markers to avoid overlap)
    if (strategyEvents && strategyEvents.length > 0) {
      const eventMarkers = createFloorStrategyMarkers(strategyEvents);
      markers.push(...eventMarkers);
    }

    console.log('[BacktestChart] Filtered markers:', markers);

    return markers;
  }, [strategyEvents, candles]);

  // Handle marker click
  const handleMarkerClick = useCallback(
    (marker: ChartMarker) => {
      if (!onTradeClick) {
        return;
      }

      onTradeClick(marker);
    },
    [onTradeClick]
  );

  return (
    <Box sx={{ width: '100%', maxWidth: '100%', boxSizing: 'border-box' }}>
      {/* Controls - Timeframe and Reset only */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          gap: 2,
          flexWrap: 'wrap',
          mb: 2,
        }}
      >
        {/* Granularity Selector */}
        <FormControl sx={{ minWidth: 120, height: 32 }} size="small">
          <InputLabel id="granularity-label" sx={{ fontSize: '0.85rem' }}>
            Timeframe
          </InputLabel>
          <Select
            labelId="granularity-label"
            value={granularity}
            label="Timeframe"
            onChange={handleGranularityChange}
            disabled={granularitiesLoading}
            sx={{ height: 32, fontSize: '0.85rem' }}
            startAdornment={
              granularitiesLoading ? (
                <CircularProgress size={16} sx={{ ml: 1 }} />
              ) : null
            }
          >
            {granularities.map((gran) => (
              <MenuItem
                key={gran.value}
                value={gran.value}
                sx={{ fontSize: '0.85rem' }}
              >
                {gran.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Reset View Button */}
        <Button
          variant="outlined"
          size="small"
          onClick={handleResetView}
          startIcon={<RestartAltIcon sx={{ fontSize: '1rem' }} />}
          sx={{ height: 32, fontSize: '0.85rem', px: 1.5 }}
        >
          Reset
        </Button>
      </Box>

      {/* Chart Legend */}
      <Box
        sx={{
          display: 'flex',
          gap: 3,
          mb: 2,
          p: 1.5,
          bgcolor: 'grey.50',
          borderRadius: 1,
          border: '1px solid',
          borderColor: 'grey.300',
          flexWrap: 'wrap',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              bgcolor: '#2196f3',
            }}
          />
          <Typography variant="caption" sx={{ fontWeight: 500 }}>
            Initial Entry
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 0,
              height: 0,
              borderLeft: '6px solid transparent',
              borderRight: '6px solid transparent',
              borderBottom: '10px solid #00bcd4',
            }}
          />
          <Typography variant="caption" sx={{ fontWeight: 500 }}>
            Retracement
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 0,
              height: 0,
              borderLeft: '5px solid transparent',
              borderRight: '5px solid transparent',
              borderTop: '8px solid #757575',
            }}
          />
          <Typography variant="caption" sx={{ fontWeight: 500 }}>
            Close
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 0,
              height: 0,
              borderLeft: '5px solid transparent',
              borderRight: '5px solid transparent',
              borderTop: '8px solid #4caf50',
            }}
          />
          <Typography variant="caption" sx={{ fontWeight: 500 }}>
            Take Profit
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              bgcolor: '#9c27b0',
            }}
          />
          <Typography variant="caption" sx={{ fontWeight: 500 }}>
            New Layer
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              bgcolor: '#ff5722',
            }}
          />
          <Typography variant="caption" sx={{ fontWeight: 500 }}>
            Volatility Lock
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              bgcolor: '#e91e63',
            }}
          />
          <Typography variant="caption" sx={{ fontWeight: 500 }}>
            Margin Protection
          </Typography>
        </Box>
        <Box sx={{ flex: 1 }} />
        <Typography
          variant="caption"
          sx={{ color: 'text.secondary', fontStyle: 'italic' }}
        >
          Hover over candles and markers for details
        </Typography>
      </Box>

      {/* Chart */}
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
        showDataGaps={true}
        latestPrice={latestPrice}
        markers={tradeMarkers}
        onMarkerClick={handleMarkerClick}
        onResetView={handleResetView}
      />
    </Box>
  );
};

export default BacktestChart;
