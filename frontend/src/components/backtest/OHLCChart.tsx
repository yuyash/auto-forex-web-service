import { useEffect, useRef, useState } from 'react';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  Time,
} from 'lightweight-charts';
import { Box, CircularProgress, Typography, Alert } from '@mui/material';
import { calculateGranularity } from '../../utils/granularityCalculator';
import { apiClient } from '../../services/api/client';
import type { OHLCData } from '../../types/chart';

export interface Trade {
  timestamp: string;
  action: 'buy' | 'sell';
  price: number;
  units: number;
  pnl?: number;
}

export interface OHLCChartProps {
  instrument: string;
  startDate: string;
  endDate: string;
  trades: Trade[];
  granularity?: string;
  height?: number;
}

interface CandlesResponse {
  instrument: string;
  granularity: string;
  candles: OHLCData[];
}

export function OHLCChart({
  instrument,
  startDate,
  endDate,
  trades,
  granularity: providedGranularity,
  height = 500,
}: OHLCChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [candleData, setCandleData] = useState<CandlestickData[]>([]);

  // Calculate or use provided granularity
  const granularity =
    providedGranularity ||
    calculateGranularity(new Date(startDate), new Date(endDate));

  useEffect(() => {
    const fetchCandles = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await apiClient.get<CandlesResponse>('/candles', {
          instrument,
          start_date: startDate,
          end_date: endDate,
          granularity,
        });

        // Transform OHLC data to lightweight-charts format
        const transformedData: CandlestickData[] = response.candles.map(
          (candle) => ({
            time: candle.time as Time,
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
          })
        );

        setCandleData(transformedData);
      } catch (err) {
        console.error('Error fetching candles:', err);
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to load chart data. Please try again.'
        );
      } finally {
        setLoading(false);
      }
    };

    fetchCandles();
  }, [instrument, startDate, endDate, granularity]);

  useEffect(() => {
    if (!chartContainerRef.current || candleData.length === 0) return;

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#e1e1e1' },
        horzLines: { color: '#e1e1e1' },
      },
      crosshair: {
        mode: 1, // Normal crosshair
      },
      rightPriceScale: {
        borderColor: '#cccccc',
      },
      timeScale: {
        borderColor: '#cccccc',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // Add candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    });

    candlestickSeriesRef.current = candlestickSeries;

    // Set data
    candlestickSeries.setData(candleData);

    // Fit content
    chart.timeScale().fitContent();

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [candleData, height]);

  // Add trade markers
  useEffect(() => {
    if (!candlestickSeriesRef.current || trades.length === 0) return;

    const markers = trades.map((trade) => {
      const timestamp = new Date(trade.timestamp).getTime() / 1000;

      return {
        time: timestamp as Time,
        position: (trade.action === 'buy' ? 'belowBar' : 'aboveBar') as
          | 'belowBar'
          | 'aboveBar',
        color: trade.action === 'buy' ? '#26a69a' : '#ef5350',
        shape: (trade.action === 'buy' ? 'arrowUp' : 'arrowDown') as
          | 'arrowUp'
          | 'arrowDown',
        text: `${trade.action.toUpperCase()} ${Math.abs(trade.units)} @ ${trade.price.toFixed(5)}`,
      };
    });

    candlestickSeriesRef.current.setMarkers(markers);
  }, [trades]);

  if (loading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        height={height}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={2}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  if (candleData.length === 0) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        height={height}
      >
        <Typography color="text.secondary">
          No chart data available for this period
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Box ref={chartContainerRef} sx={{ position: 'relative' }} />
    </Box>
  );
}
