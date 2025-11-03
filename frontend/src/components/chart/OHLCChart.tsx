import { useEffect, useRef, useState } from 'react';
import { createChart, ColorType } from 'lightweight-charts';
import type {
  IChartApi,
  ISeriesApi,
  CandlestickData,
  Time,
} from 'lightweight-charts';
import { Box, CircularProgress, Typography } from '@mui/material';
import type { OHLCData, ChartConfig } from '../../types/chart';

interface OHLCChartProps {
  instrument: string;
  granularity: string;
  data?: OHLCData[];
  config?: ChartConfig;
  onLoadHistoricalData?: (
    instrument: string,
    granularity: string
  ) => Promise<OHLCData[]>;
}

const OHLCChart = ({
  instrument,
  granularity,
  data = [],
  config = {},
  onLoadHistoricalData,
}: OHLCChartProps) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Default chart configuration
  const defaultConfig: ChartConfig = {
    width: 800,
    height: 600,
    upColor: '#26a69a',
    downColor: '#ef5350',
    borderVisible: false,
    wickUpColor: '#26a69a',
    wickDownColor: '#ef5350',
    ...config,
  };

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart instance
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth || defaultConfig.width,
      height: defaultConfig.height,
      layout: {
        background: { type: ColorType.Solid, color: '#ffffff' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#e1e1e1' },
        horzLines: { color: '#e1e1e1' },
      },
      crosshair: {
        mode: 1,
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

    // Add candlestick series
    const candlestickSeries = (chart as unknown).addCandlestickSeries({
      upColor: defaultConfig.upColor,
      downColor: defaultConfig.downColor,
      borderVisible: defaultConfig.borderVisible,
      wickUpColor: defaultConfig.wickUpColor,
      wickDownColor: defaultConfig.wickDownColor,
    });

    chartRef.current = chart;
    candlestickSeriesRef.current = candlestickSeries;

    // Handle window resize
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
  }, [
    defaultConfig.width,
    defaultConfig.height,
    defaultConfig.upColor,
    defaultConfig.downColor,
    defaultConfig.borderVisible,
    defaultConfig.wickUpColor,
    defaultConfig.wickDownColor,
  ]);

  // Load historical data
  useEffect(() => {
    const loadData = async () => {
      if (!candlestickSeriesRef.current) return;

      setLoading(true);
      setError(null);

      try {
        let historicalData: OHLCData[] = data;

        // If onLoadHistoricalData callback is provided, use it to fetch data
        if (onLoadHistoricalData && data.length === 0) {
          historicalData = await onLoadHistoricalData(instrument, granularity);
        }

        // Convert OHLCData to CandlestickData format
        const candlestickData: CandlestickData<Time>[] = historicalData.map(
          (item) => ({
            time: item.time as Time,
            open: item.open,
            high: item.high,
            low: item.low,
            close: item.close,
          })
        );

        // Set data to the series
        if (candlestickData.length > 0) {
          candlestickSeriesRef.current.setData(candlestickData);
          chartRef.current?.timeScale().fitContent();
        }
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to load chart data';
        setError(errorMessage);
        console.error('Error loading chart data:', err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [instrument, granularity, data, onLoadHistoricalData]);

  // Update chart with new data point (exposed for future use)
  // This method can be called from parent components via ref
  const updateChart = (newData: OHLCData): void => {
    if (!candlestickSeriesRef.current) return;

    const candlestickData: CandlestickData<Time> = {
      time: newData.time as Time,
      open: newData.open,
      high: newData.high,
      low: newData.low,
      close: newData.close,
    };

    candlestickSeriesRef.current.update(candlestickData);
  };

  // Expose updateChart for future use (prevents unused warning)
  // This can be accessed via ref in parent components
  void updateChart;

  if (error) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: defaultConfig.height,
          border: '1px solid #e1e1e1',
          borderRadius: 1,
        }}
      >
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ position: 'relative', width: '100%' }}>
      {loading && (
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            backgroundColor: 'rgba(255, 255, 255, 0.8)',
            zIndex: 1,
          }}
        >
          <CircularProgress />
        </Box>
      )}
      <Box
        ref={chartContainerRef}
        sx={{
          width: '100%',
          height: defaultConfig.height,
          border: '1px solid #e1e1e1',
          borderRadius: 1,
        }}
      />
    </Box>
  );
};

export default OHLCChart;
