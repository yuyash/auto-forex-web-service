/**
 * MetricsChart Component
 *
 * Displays multiple metrics as line charts for an execution using MetricsLineChart.
 * Fetches data from GET /executions/<execution_id>/metrics/ with granularity support.
 * Displays separate charts for different metric categories.
 *
 * Requirements: 11.9, 12.2
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  Stack,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material';
import { MetricsLineChart } from '../../charts/MetricsLineChart';
import type { MetricSeries } from '../../charts/MetricsLineChart';
import { ExecutionsService } from '../../../api/generated/services/ExecutionsService';
import { GRANULARITY_OPTIONS } from '../../charts/EquityOHLCChart';

export interface MetricsChartProps {
  executionId: number;
  enableRealTimeUpdates?: boolean;
}

interface MetricsBin {
  timestamp: string;
  sequence: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
  open_positions: number;
  total_trades: number;
  tick_ask_min: number;
  tick_ask_max: number;
  tick_ask_avg: number;
  tick_bid_min: number;
  tick_bid_max: number;
  tick_bid_avg: number;
  tick_mid_min: number;
  tick_mid_max: number;
  tick_mid_avg: number;
}

interface MetricsResponse {
  metrics: MetricsBin[];
}

/**
 * Transform metrics bins to series data
 */
const transformToSeries = (
  bins: MetricsBin[]
): {
  pnlSeries: MetricSeries[];
  positionSeries: MetricSeries[];
  tickSeries: MetricSeries[];
} => {
  const pnlSeries: MetricSeries[] = [
    {
      id: 'realized_pnl',
      label: 'Realized PnL',
      data: bins.map((bin) => ({
        timestamp: bin.timestamp,
        value: bin.realized_pnl,
      })),
      color: '#26a69a',
      unit: ' USD',
    },
    {
      id: 'unrealized_pnl',
      label: 'Unrealized PnL',
      data: bins.map((bin) => ({
        timestamp: bin.timestamp,
        value: bin.unrealized_pnl,
      })),
      color: '#ff9800',
      unit: ' USD',
    },
    {
      id: 'total_pnl',
      label: 'Total PnL',
      data: bins.map((bin) => ({
        timestamp: bin.timestamp,
        value: bin.total_pnl,
      })),
      color: '#1976d2',
      unit: ' USD',
    },
  ];

  const positionSeries: MetricSeries[] = [
    {
      id: 'open_positions',
      label: 'Open Positions',
      data: bins.map((bin) => ({
        timestamp: bin.timestamp,
        value: bin.open_positions,
      })),
      color: '#9c27b0',
      unit: '',
    },
    {
      id: 'total_trades',
      label: 'Total Trades',
      data: bins.map((bin) => ({
        timestamp: bin.timestamp,
        value: bin.total_trades,
      })),
      color: '#4caf50',
      unit: '',
    },
  ];

  const tickSeries: MetricSeries[] = [
    {
      id: 'tick_ask_avg',
      label: 'Ask Price (Avg)',
      data: bins.map((bin) => ({
        timestamp: bin.timestamp,
        value: bin.tick_ask_avg,
      })),
      color: '#f44336',
      unit: '',
    },
    {
      id: 'tick_bid_avg',
      label: 'Bid Price (Avg)',
      data: bins.map((bin) => ({
        timestamp: bin.timestamp,
        value: bin.tick_bid_avg,
      })),
      color: '#00bcd4',
      unit: '',
    },
    {
      id: 'tick_mid_avg',
      label: 'Mid Price (Avg)',
      data: bins.map((bin) => ({
        timestamp: bin.timestamp,
        value: bin.tick_mid_avg,
      })),
      color: '#ff5722',
      unit: '',
    },
  ];

  return { pnlSeries, positionSeries, tickSeries };
};

export const MetricsChart: React.FC<MetricsChartProps> = ({
  executionId,
  enableRealTimeUpdates = false,
}) => {
  const [pnlSeries, setPnlSeries] = useState<MetricSeries[]>([]);
  const [positionSeries, setPositionSeries] = useState<MetricSeries[]>([]);
  const [tickSeries, setTickSeries] = useState<MetricSeries[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [granularity, setGranularity] = useState(60); // Default 1 minute

  const fetchMetricsData = useCallback(
    async (granularitySeconds: number) => {
      try {
        setLoading(true);
        setError(null);

        const response = (await ExecutionsService.getExecutionMetrics(
          executionId,
          undefined, // endTime
          granularitySeconds,
          undefined, // lastN
          undefined // startTime
        )) as MetricsResponse;

        const { pnlSeries, positionSeries, tickSeries } = transformToSeries(
          response.metrics
        );
        setPnlSeries(pnlSeries);
        setPositionSeries(positionSeries);
        setTickSeries(tickSeries);
      } catch (err) {
        console.error('Failed to fetch metrics data:', err);
        setError(
          err instanceof Error ? err.message : 'Failed to fetch metrics data'
        );
        setPnlSeries([]);
        setPositionSeries([]);
        setTickSeries([]);
      } finally {
        setLoading(false);
      }
    },
    [executionId]
  );

  // Initial fetch
  useEffect(() => {
    fetchMetricsData(granularity);
  }, [fetchMetricsData, granularity]);

  // Real-time updates
  useEffect(() => {
    if (!enableRealTimeUpdates) return;

    const interval = setInterval(() => {
      fetchMetricsData(granularity);
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, fetchMetricsData, granularity]);

  const handleGranularityChange = (event: SelectChangeEvent<number>) => {
    const newGranularity = Number(event.target.value);
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
      {/* Granularity Selector */}
      <Box
        sx={{
          mb: 3,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Typography variant="h6">Metrics Over Time</Typography>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel id="metrics-granularity-select-label">
            Granularity
          </InputLabel>
          <Select
            labelId="metrics-granularity-select-label"
            id="metrics-granularity-select"
            value={granularity}
            label="Granularity"
            onChange={handleGranularityChange}
            aria-label="Select time granularity for metrics"
          >
            {GRANULARITY_OPTIONS.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {/* Multiple Charts */}
      <Stack spacing={3}>
        {/* PnL Chart */}
        <MetricsLineChart
          series={pnlSeries}
          loading={loading}
          error={error}
          height={400}
          title="Profit & Loss"
          showLegend={true}
          yAxisLabel="PnL (USD)"
        />

        {/* Position & Trades Chart */}
        <MetricsLineChart
          series={positionSeries}
          loading={loading}
          error={error}
          height={300}
          title="Positions & Trades"
          showLegend={true}
          yAxisLabel="Count"
        />

        {/* Tick Prices Chart */}
        <MetricsLineChart
          series={tickSeries}
          loading={loading}
          error={error}
          height={300}
          title="Tick Prices"
          showLegend={true}
          yAxisLabel="Price"
        />
      </Stack>
    </Box>
  );
};

export default MetricsChart;
