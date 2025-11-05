import { useEffect, useRef, useState } from 'react';
import { createChart, ColorType } from 'lightweight-charts';
import type {
  IChartApi,
  CandlestickData,
  Time,
  SeriesMarker,
  LineData,
} from 'lightweight-charts';
import { Box, CircularProgress, Typography } from '@mui/material';
import type { OHLCData, ChartConfig, Position, Order } from '../../types/chart';
import useMarketData from '../../hooks/useMarketData';

interface OHLCChartProps {
  instrument: string;
  granularity: string;
  accountId?: string;
  data?: OHLCData[];
  config?: ChartConfig;
  enableRealTimeUpdates?: boolean;
  positions?: Position[];
  orders?: Order[];
  onLoadHistoricalData?: (
    instrument: string,
    granularity: string
  ) => Promise<OHLCData[]>;
  onLoadOlderData?: (
    instrument: string,
    granularity: string
  ) => Promise<OHLCData[]>;
}

const OHLCChart = ({
  instrument,
  granularity,
  accountId = 'default',
  data = [],
  config = {},
  enableRealTimeUpdates = false,
  positions = [],
  orders = [],
  onLoadHistoricalData,
  onLoadOlderData,
}: OHLCChartProps) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const candlestickSeriesRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const takeProfitSeriesRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const stopLossSeriesRef = useRef<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const currentCandleRef = useRef<CandlestickData<Time> | null>(null);
  const isLoadingOlderDataRef = useRef(false);
  const hasSubscribedToScrollRef = useRef(false);

  // Connect to WebSocket for real-time updates (only if enabled)
  const {
    tickData,
    isConnected,
    error: wsError,
  } = useMarketData({
    accountId: enableRealTimeUpdates ? accountId : undefined,
    instrument: enableRealTimeUpdates ? instrument : undefined,
    throttleMs: 100,
    onError: (err) => {
      console.error('WebSocket error:', err);
      setError(err.message);
    },
  });

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
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const candlestickSeries = (chart as any).addCandlestickSeries({
      upColor: defaultConfig.upColor,
      downColor: defaultConfig.downColor,
      borderVisible: defaultConfig.borderVisible,
      wickUpColor: defaultConfig.wickUpColor,
      wickDownColor: defaultConfig.wickDownColor,
    });

    // Add take-profit line series
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const takeProfitSeries = (chart as any).addLineSeries({
      color: '#4caf50',
      lineWidth: 2,
      lineStyle: 2, // Dashed line
      title: 'Take Profit',
      priceLineVisible: false,
      lastValueVisible: true,
    });

    // Add stop-loss line series
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const stopLossSeries = (chart as any).addLineSeries({
      color: '#f44336',
      lineWidth: 2,
      lineStyle: 2, // Dashed line
      title: 'Stop Loss',
      priceLineVisible: false,
      lastValueVisible: true,
    });

    chartRef.current = chart;
    candlestickSeriesRef.current = candlestickSeries;
    takeProfitSeriesRef.current = takeProfitSeries;
    stopLossSeriesRef.current = stopLossSeries;

    // Handle window resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    // Subscribe to visible logical range changes for lazy loading
    if (onLoadOlderData && !hasSubscribedToScrollRef.current) {
      hasSubscribedToScrollRef.current = true;

      chart.timeScale().subscribeVisibleLogicalRangeChange(async () => {
        const logicalRange = chart.timeScale().getVisibleLogicalRange();

        if (!logicalRange || isLoadingOlderDataRef.current) {
          return;
        }

        // Check if user scrolled to the left edge (beginning of data)
        // Load more data when within 10 bars of the start
        if (logicalRange.from < 10) {
          isLoadingOlderDataRef.current = true;

          try {
            const olderData = await onLoadOlderData(instrument, granularity);

            if (olderData && olderData.length > 0) {
              // Prepend older data to existing data
              const existingData = candlestickSeries.data();
              const combinedData = [
                ...olderData.map((item) => ({
                  time: item.time as Time,
                  open: item.open,
                  high: item.high,
                  low: item.low,
                  close: item.close,
                })),
                ...(existingData as CandlestickData<Time>[]),
              ];

              candlestickSeries.setData(combinedData);
            }
          } catch (err) {
            console.error('Error loading older data:', err);
          } finally {
            isLoadingOlderDataRef.current = false;
          }
        }
      });
    }

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
      hasSubscribedToScrollRef.current = false;
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

  // Update chart with real-time tick data
  useEffect(() => {
    if (
      !enableRealTimeUpdates ||
      !tickData ||
      !candlestickSeriesRef.current ||
      !isConnected
    ) {
      return;
    }

    try {
      // Convert tick timestamp to Unix timestamp
      const tickTime = Math.floor(new Date(tickData.time).getTime() / 1000);

      // Use mid price for the candle
      const price = tickData.mid;

      // If we don't have a current candle, create one
      if (!currentCandleRef.current) {
        currentCandleRef.current = {
          time: tickTime as Time,
          open: price,
          high: price,
          low: price,
          close: price,
        };
        candlestickSeriesRef.current.update(currentCandleRef.current);
      } else {
        // Update the current candle with the new tick
        const currentCandle = currentCandleRef.current;

        // Check if we need to start a new candle based on granularity
        // For simplicity, we'll update the current candle
        // In a production system, you'd calculate candle boundaries based on granularity
        currentCandle.close = price;
        currentCandle.high = Math.max(currentCandle.high, price);
        currentCandle.low = Math.min(currentCandle.low, price);

        candlestickSeriesRef.current.update(currentCandle);
      }
    } catch (err) {
      console.error('Error updating chart with tick data:', err);
    }
  }, [tickData, enableRealTimeUpdates, isConnected]);

  // Update error state from WebSocket
  useEffect(() => {
    if (wsError) {
      setError(wsError.message);
    }
  }, [wsError]);

  // Update position and order markers
  useEffect(() => {
    if (!candlestickSeriesRef.current) return;

    const markers: SeriesMarker<Time>[] = [];

    // Add position entry markers
    positions.forEach((position) => {
      if (position.instrument === instrument) {
        const positionTime = Math.floor(
          new Date(position.opened_at).getTime() / 1000
        ) as Time;

        markers.push({
          time: positionTime,
          position: position.direction === 'long' ? 'belowBar' : 'aboveBar',
          color: position.direction === 'long' ? '#2196f3' : '#ff9800',
          shape: position.direction === 'long' ? 'arrowUp' : 'arrowDown',
          text: `${position.direction.toUpperCase()} @ ${position.entry_price.toFixed(5)}`,
        });
      }
    });

    // Add pending order markers
    orders.forEach((order) => {
      if (
        order.instrument === instrument &&
        order.status === 'pending' &&
        order.price
      ) {
        const orderTime = Math.floor(
          new Date(order.created_at).getTime() / 1000
        ) as Time;

        markers.push({
          time: orderTime,
          position: order.direction === 'long' ? 'belowBar' : 'aboveBar',
          color: order.direction === 'long' ? '#64b5f6' : '#ffb74d',
          shape: 'circle',
          text: `${order.order_type.toUpperCase()} @ ${order.price.toFixed(5)}`,
        });
      }
    });

    // Set markers on the candlestick series
    candlestickSeriesRef.current.setMarkers(markers);
  }, [positions, orders, instrument]);

  // Update take-profit and stop-loss lines
  useEffect(() => {
    if (!takeProfitSeriesRef.current || !stopLossSeriesRef.current) return;

    // Collect all take-profit and stop-loss levels from positions and orders
    const takeProfitLevels: number[] = [];
    const stopLossLevels: number[] = [];

    positions.forEach((position) => {
      if (position.instrument === instrument) {
        if (position.take_profit) {
          takeProfitLevels.push(position.take_profit);
        }
        if (position.stop_loss) {
          stopLossLevels.push(position.stop_loss);
        }
      }
    });

    orders.forEach((order) => {
      if (order.instrument === instrument && order.status === 'pending') {
        if (order.take_profit) {
          takeProfitLevels.push(order.take_profit);
        }
        if (order.stop_loss) {
          stopLossLevels.push(order.stop_loss);
        }
      }
    });

    // Get the current time range from the chart
    const timeScale = chartRef.current?.timeScale();
    const visibleRange = timeScale?.getVisibleRange();

    if (visibleRange) {
      // Create horizontal lines for take-profit levels
      if (takeProfitLevels.length > 0) {
        const takeProfitData: LineData<Time>[] = [];
        takeProfitLevels.forEach((level) => {
          takeProfitData.push({
            time: visibleRange.from as Time,
            value: level,
          });
          takeProfitData.push({
            time: visibleRange.to as Time,
            value: level,
          });
        });
        takeProfitSeriesRef.current.setData(takeProfitData);
      } else {
        takeProfitSeriesRef.current.setData([]);
      }

      // Create horizontal lines for stop-loss levels
      if (stopLossLevels.length > 0) {
        const stopLossData: LineData<Time>[] = [];
        stopLossLevels.forEach((level) => {
          stopLossData.push({
            time: visibleRange.from as Time,
            value: level,
          });
          stopLossData.push({
            time: visibleRange.to as Time,
            value: level,
          });
        });
        stopLossSeriesRef.current.setData(stopLossData);
      } else {
        stopLossSeriesRef.current.setData([]);
      }
    }
  }, [positions, orders, instrument]);

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
