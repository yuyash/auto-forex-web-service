/**
 * EquityChart Component
 *
 * Displays equity curve data for an execution using EquityOHLCChart.
 * Fetches data from GET /executions/<execution_id>/equity/ with granularity support.
 *
 * Requirements: 11.8, 12.3
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Box, Alert } from '@mui/material';
import EquityOHLCChart from '../../charts/EquityOHLCChart';
import type { OHLCDataPoint } from '../../charts/EquityOHLCChart';
import { ExecutionsService } from '../../../api/generated/services/ExecutionsService';

export interface EquityChartProps {
  executionId: number;
  enableRealTimeUpdates?: boolean;
}

interface EquityBin {
  timestamp: string;
  realized_pnl_min: number;
  realized_pnl_max: number;
  realized_pnl_avg: number;
  realized_pnl_median: number;
  unrealized_pnl_min: number;
  unrealized_pnl_max: number;
  unrealized_pnl_avg: number;
  unrealized_pnl_median: number;
  tick_ask_min: number;
  tick_ask_max: number;
  tick_ask_avg: number;
  tick_ask_median: number;
  tick_bid_min: number;
  tick_bid_max: number;
  tick_bid_avg: number;
  tick_bid_median: number;
  tick_mid_min: number;
  tick_mid_max: number;
  tick_mid_avg: number;
  tick_mid_median: number;
  trade_count: number;
}

interface EquityResponse {
  bins: EquityBin[];
}

/**
 * Transform equity bins to OHLC data points
 * Uses total PnL (realized + unrealized) for OHLC values
 */
const transformToOHLC = (bins: EquityBin[]): OHLCDataPoint[] => {
  return bins.map((bin) => {
    // Calculate total PnL for OHLC
    const totalMin = bin.realized_pnl_min + bin.unrealized_pnl_min;
    const totalMax = bin.realized_pnl_max + bin.unrealized_pnl_max;
    const totalAvg = bin.realized_pnl_avg + bin.unrealized_pnl_avg;
    const totalMedian = bin.realized_pnl_median + bin.unrealized_pnl_median;

    return {
      timestamp: bin.timestamp,
      open: totalAvg, // Use average as open
      high: totalMax,
      low: totalMin,
      close: totalMedian, // Use median as close
      volume: bin.trade_count,
    };
  });
};

export const EquityChart: React.FC<EquityChartProps> = ({
  executionId,
  enableRealTimeUpdates = false,
}) => {
  const [data, setData] = useState<OHLCDataPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [granularity, setGranularity] = useState(60); // Default 1 minute

  const fetchEquityData = useCallback(
    async (granularitySeconds: number) => {
      try {
        setLoading(true);
        setError(null);

        const response = (await ExecutionsService.getExecutionEquity(
          executionId,
          undefined, // endTime
          granularitySeconds,
          undefined // startTime
        )) as EquityResponse;

        const ohlcData = transformToOHLC(response.bins);
        setData(ohlcData);
      } catch (err) {
        console.error('Failed to fetch equity data:', err);
        setError(
          err instanceof Error ? err.message : 'Failed to fetch equity data'
        );
        setData([]);
      } finally {
        setLoading(false);
      }
    },
    [executionId]
  );

  // Initial fetch
  useEffect(() => {
    fetchEquityData(granularity);
  }, [fetchEquityData, granularity]);

  // Real-time updates
  useEffect(() => {
    if (!enableRealTimeUpdates) return;

    const interval = setInterval(() => {
      fetchEquityData(granularity);
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, fetchEquityData, granularity]);

  const handleGranularityChange = (newGranularity: number) => {
    setGranularity(newGranularity);
  };

  if (error && !loading) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <EquityOHLCChart
        data={data}
        loading={loading}
        error={error}
        height={500}
        initialGranularity={granularity}
        onGranularityChange={handleGranularityChange}
        showGranularitySelector={true}
        title="Equity Curve"
      />
    </Box>
  );
};

export default EquityChart;
