import { useEffect, useRef, useState, useCallback } from 'react';
import {
  createChart,
  ColorType,
  CandlestickSeries,
  LineSeries,
  type IChartApi,
  type CandlestickData,
  type Time,
  type SeriesMarker,
  type LineData,
} from 'lightweight-charts';
import { Box, Typography, CircularProgress } from '@mui/material';
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
  onLoadNewerData?: (
    instrument: string,
    granularity: string
  ) => Promise<OHLCData[]>;
}

/**
 * Calculate the duration of a single candle in seconds based on granularity
 */
const getGranularityDuration = (granularity: string): number => {
  const unit = granularity.charAt(0);
  const value = parseInt(granularity.substring(1)) || 1;

  switch (unit) {
    case 'S':
      return value; // Seconds
    case 'M':
      return value * 60; // Minutes
    case 'H':
      return value * 3600; // Hours
    case 'D':
      return 86400; // Day
    case 'W':
      return 604800; // Week
    default:
      return 3600; // Default to 1 hour
  }
};

const OHLCChart = ({
  instrument,
  granularity,
  accountId = 'default',
  data = [],
  config = {},
  enableRealTimeUpdates = false,
  positions = [],
  orders = [],
  onLoadOlderData,
  onLoadNewerData,
}: OHLCChartProps) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ReturnType<
    IChartApi['addSeries']
  > | null>(null);
  const takeProfitSeriesRef = useRef<ReturnType<IChartApi['addSeries']> | null>(
    null
  );
  const stopLossSeriesRef = useRef<ReturnType<IChartApi['addSeries']> | null>(
    null
  );
  const priceIndicatorSeriesRef = useRef<ReturnType<
    IChartApi['addSeries']
  > | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scrollToEnd, setScrollToEnd] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingDirection, setLoadingDirection] = useState<
    'older' | 'newer' | null
  >(null);
  const currentCandleRef = useRef<CandlestickData<Time> | null>(null);
  const isLoadingOlderDataRef = useRef(false);
  const hasSubscribedToScrollRef = useRef(false);
  const preservedLogicalRangeRef = useRef<{ from: number; to: number } | null>(
    null
  );
  const loadingDirectionRef = useRef<'older' | 'newer' | null>(null);
  const dataLengthRef = useRef(0);
  const loadingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /**
   * Check if we should load older data based on scroll position
   * Returns true when within 10 bars of the left edge
   */
  const shouldLoadOlder = useCallback(
    (logicalRange: { from: number; to: number }): boolean => {
      return logicalRange.from < 10;
    },
    []
  );

  /**
   * Check if we should load newer data based on scroll position and time
   * Returns true when within 10 bars of the right edge AND not beyond current time
   */
  const shouldLoadNewer = useCallback(
    (
      logicalRange: { from: number; to: number },
      totalBars: number,
      newestTimestamp: number
    ): boolean => {
      // Check if within 10 bars of right edge
      const nearRightEdge = logicalRange.to > totalBars - 10;

      if (!nearRightEdge) {
        return false;
      }

      // Calculate current time in seconds
      const currentTime = Math.floor(Date.now() / 1000);

      // Calculate granularity duration to determine if we're at current time
      const granularityDuration = getGranularityDuration(granularity);

      // Check if the newest data is within one candle period of current time
      // If so, we're at the latest data and shouldn't fetch more
      const timeDifference = currentTime - newestTimestamp;
      const isAtCurrentTime = timeDifference <= granularityDuration;

      console.log('shouldLoadNewer check:', {
        nearRightEdge,
        currentTime,
        newestTimestamp,
        timeDifference,
        granularityDuration,
        isAtCurrentTime,
      });

      // Only load newer data if we're near the edge AND not at current time
      return nearRightEdge && !isAtCurrentTime;
    },
    [granularity]
  );

  // Stable error handler to prevent
  //  reconnection loops
  const handleWebSocketError = useCallback((err: Error) => {
    console.error('WebSocket error:', err);
    setError(err.message);
  }, []);

  // Connect to WebSocket for real-time updates (only if enabled)
  const {
    tickData,
    isConnected,
    error: wsError,
  } = useMarketData({
    accountId: enableRealTimeUpdates ? accountId : undefined,
    instrument: enableRealTimeUpdates ? instrument : undefined,
    throttleMs: 100,
    onError: handleWebSocketError,
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
      height: chartContainerRef.current.clientHeight || defaultConfig.height,
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
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: defaultConfig.upColor,
      downColor: defaultConfig.downColor,
      borderVisible: defaultConfig.borderVisible,
      wickUpColor: defaultConfig.wickUpColor,
      wickDownColor: defaultConfig.wickDownColor,
    });

    // Add take-profit line series
    const takeProfitSeries = chart.addSeries(LineSeries, {
      color: '#4caf50',
      lineWidth: 2,
      lineStyle: 2, // Dashed line
      title: 'Take Profit',
      priceLineVisible: false,
      lastValueVisible: true,
    });

    // Add stop-loss line series
    const stopLossSeries = chart.addSeries(LineSeries, {
      color: '#f44336',
      lineWidth: 2,
      lineStyle: 2, // Dashed line
      title: 'Stop Loss',
      priceLineVisible: false,
      lastValueVisible: true,
    });

    // Add real-time price indicator line series
    const priceIndicatorSeries = chart.addSeries(LineSeries, {
      color: '#2196F3', // Bright blue
      lineWidth: 2,
      lineStyle: 2, // Dashed line
      title: 'Live Price',
      priceLineVisible: true,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 4,
    });

    chartRef.current = chart;
    candlestickSeriesRef.current = candlestickSeries;
    takeProfitSeriesRef.current = takeProfitSeries;
    stopLossSeriesRef.current = stopLossSeries;
    priceIndicatorSeriesRef.current = priceIndicatorSeries;

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
    let scrollLoadingEnabled = false;
    let scrollTimeout: ReturnType<typeof setTimeout> | null = null;

    if (
      (onLoadOlderData || onLoadNewerData) &&
      !hasSubscribedToScrollRef.current
    ) {
      hasSubscribedToScrollRef.current = true;

      // Add a small delay before enabling scroll-based loading
      // This prevents immediate triggering when chart first loads
      scrollTimeout = setTimeout(() => {
        scrollLoadingEnabled = true;
      }, 1000);

      chart.timeScale().subscribeVisibleLogicalRangeChange(async () => {
        if (
          !scrollLoadingEnabled ||
          !chartRef.current ||
          !candlestickSeriesRef.current
        ) {
          return;
        }

        // Use chartRef.current instead of the local chart variable
        const currentChart = chartRef.current;
        if (!currentChart) return;

        const logicalRange = currentChart.timeScale().getVisibleLogicalRange();

        if (!logicalRange || isLoadingOlderDataRef.current) {
          return;
        }

        const series = candlestickSeriesRef.current;
        if (!series) return;

        // Get total number of bars in the dataset from ref (to avoid stale closure)
        const totalBars = dataLengthRef.current;

        // Get the newest timestamp from current data for time-based checks
        const newestTimestamp =
          data.length > 0 ? data[data.length - 1].time : 0;

        // Check if user scrolled to the left edge (beginning of data)
        // Load more data when within 10 bars of the start
        if (onLoadOlderData && shouldLoadOlder(logicalRange)) {
          console.log(
            'Loading older data, logicalRange.from:',
            logicalRange.from
          );
          isLoadingOlderDataRef.current = true;
          loadingDirectionRef.current = 'older';

          // Set loading state for UI indicator
          setIsLoading(true);
          setLoadingDirection('older');

          // Preserve the logical range (bar indices) to maintain scroll position
          // We'll adjust this after new data is loaded
          preservedLogicalRangeRef.current = {
            from: logicalRange.from,
            to: logicalRange.to,
          };
          console.log(
            'Preserved logical range for OLDER data:',
            preservedLogicalRangeRef.current
          );

          try {
            // Call the parent's loadOlderData function
            // The parent will update the data prop, which will trigger a re-render
            await onLoadOlderData(instrument, granularity);
            console.log('Older data loaded by parent');
          } catch (err) {
            console.error('Error loading older data:', err);
            // Clear preserved range on error
            preservedLogicalRangeRef.current = null;
            loadingDirectionRef.current = null;
          } finally {
            isLoadingOlderDataRef.current = false;

            // Clear loading indicator after 200ms
            if (loadingTimeoutRef.current) {
              clearTimeout(loadingTimeoutRef.current);
            }
            loadingTimeoutRef.current = setTimeout(() => {
              setIsLoading(false);
              setLoadingDirection(null);
            }, 200);
          }
        }
        // Check if user scrolled to the right edge (end of data)
        // Load more data when within 10 bars of the end AND not beyond current time
        else if (
          onLoadNewerData &&
          shouldLoadNewer(logicalRange, totalBars, newestTimestamp)
        ) {
          console.log(
            'Loading newer data, logicalRange.to:',
            logicalRange.to,
            'totalBars:',
            totalBars,
            'newestTimestamp:',
            newestTimestamp
          );
          isLoadingOlderDataRef.current = true;
          loadingDirectionRef.current = 'newer';

          // Set loading state for UI indicator
          setIsLoading(true);
          setLoadingDirection('newer');

          // Preserve the logical range for newer data too
          // When newer data is appended, we don't need to shift the range
          // but we need to preserve it to prevent the chart from resetting
          preservedLogicalRangeRef.current = {
            from: logicalRange.from,
            to: logicalRange.to,
          };
          console.log(
            'Preserved logical range for NEWER data:',
            preservedLogicalRangeRef.current
          );

          try {
            // Call the parent's loadNewerData function
            // The parent will update the data prop, which will trigger a re-render
            const addedData = await onLoadNewerData(instrument, granularity);

            // If no data was added (we're at the latest), trigger scroll to end
            if (!addedData || addedData.length === 0) {
              console.log('No newer data was added - triggering scroll to end');
              preservedLogicalRangeRef.current = null;
              loadingDirectionRef.current = null;
              // Trigger the scroll effect
              setScrollToEnd(true);
            } else {
              console.log(
                'Newer data loaded by parent:',
                addedData.length,
                'candles'
              );
            }
          } catch (err) {
            console.error('Error loading newer data:', err);
            // Clear preserved range on error too
            preservedLogicalRangeRef.current = null;
            loadingDirectionRef.current = null;
          } finally {
            isLoadingOlderDataRef.current = false;

            // Clear loading indicator after 200ms
            if (loadingTimeoutRef.current) {
              clearTimeout(loadingTimeoutRef.current);
            }
            loadingTimeoutRef.current = setTimeout(() => {
              setIsLoading(false);
              setLoadingDirection(null);
            }, 200);
          }
        }
      });
    }

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);

      // Clear the scroll loading timeout
      if (scrollTimeout) {
        clearTimeout(scrollTimeout);
      }

      // Clear the loading indicator timeout
      if (loadingTimeoutRef.current) {
        clearTimeout(loadingTimeoutRef.current);
      }

      // Disable scroll loading
      scrollLoadingEnabled = false;

      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
      candlestickSeriesRef.current = null;
      takeProfitSeriesRef.current = null;
      stopLossSeriesRef.current = null;
      priceIndicatorSeriesRef.current = null;
      currentCandleRef.current = null;
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
    instrument,
    granularity,
    onLoadOlderData,
    onLoadNewerData,
    shouldLoadOlder,
    shouldLoadNewer,
    data,
  ]);

  // Track previous data length to detect if we're loading older data
  const prevDataLengthRef = useRef(0);

  // Handle scrolling to end when no newer data is available
  useEffect(() => {
    if (scrollToEnd && chartRef.current && data.length > 0) {
      console.log('📊 Scrolling to end because no newer data available');
      try {
        const barsToShow = Math.min(100, data.length);
        const newRange = {
          from: Math.max(0, data.length - barsToShow),
          to: data.length - 1,
        };
        console.log('📊 Showing last', barsToShow, 'bars:', newRange);
        chartRef.current.timeScale().setVisibleLogicalRange(newRange);
      } catch (err) {
        console.warn('📊 Could not scroll to end:', err);
      }
      setScrollToEnd(false);
    }
  }, [scrollToEnd, data.length]);

  // Update chart when data prop changes (from parent component)
  useEffect(() => {
    if (!candlestickSeriesRef.current) return;

    if (data.length === 0) {
      console.warn('⚠️ Data prop is EMPTY! This will clear the chart.');
      return;
    }

    const dataLengthDiff = data.length - prevDataLengthRef.current;
    console.log(
      '📊 Data prop changed, length:',
      data.length,
      'previous:',
      prevDataLengthRef.current,
      'diff:',
      dataLengthDiff
    );
    console.log(
      '📊 Data time range:',
      data[0]?.time,
      'to',
      data[data.length - 1]?.time
    );
    console.log('📊 Loading direction:', loadingDirectionRef.current);

    const candlestickData: CandlestickData<Time>[] = data.map((item) => ({
      time: item.time as Time,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
    }));

    candlestickSeriesRef.current.setData(candlestickData);
    console.log('📊 setData called with', candlestickData.length, 'candles');

    // Update the data length ref for the scroll handler
    dataLengthRef.current = data.length;

    // Only call fitContent on initial load
    if (prevDataLengthRef.current === 0) {
      console.log('📊 Initial load - calling fitContent');
      chartRef.current?.timeScale().fitContent();
    } else if (
      preservedLogicalRangeRef.current &&
      chartRef.current &&
      loadingDirectionRef.current
    ) {
      const direction = loadingDirectionRef.current;
      const preserved = preservedLogicalRangeRef.current;

      console.log(
        '📊 Will restore range, direction:',
        direction,
        'preserved:',
        preserved
      );

      // Use setTimeout to ensure setData has completed before setting range
      setTimeout(() => {
        if (!chartRef.current) return;

        try {
          if (direction === 'older') {
            // When older data is loaded, the new bars are prepended to the beginning
            // We need to shift the logical range by the number of new bars added
            const newLogicalRange = {
              from: preserved.from + dataLengthDiff,
              to: preserved.to + dataLengthDiff,
            };
            console.log(
              '📊 Restoring logical range with offset (OLDER data):',
              newLogicalRange,
              'offset:',
              dataLengthDiff
            );
            chartRef.current
              .timeScale()
              .setVisibleLogicalRange(newLogicalRange);
          } else if (direction === 'newer') {
            // When newer data is appended, keep the same logical range
            // This maintains the user's view position
            console.log(
              '📊 Restoring logical range (NEWER data - no offset):',
              preserved
            );
            chartRef.current.timeScale().setVisibleLogicalRange(preserved);
          }
        } catch (err) {
          console.warn('📊 Could not set visible range:', err);
        }

        preservedLogicalRangeRef.current = null;
        loadingDirectionRef.current = null;
      }, 0);
    } else {
      console.log('📊 No range restoration needed');
    }

    prevDataLengthRef.current = data.length;
  }, [data]);

  // Update chart with real-time tick data
  useEffect(() => {
    if (
      !enableRealTimeUpdates ||
      !tickData ||
      !candlestickSeriesRef.current ||
      !chartRef.current ||
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
        if (candlestickSeriesRef.current && chartRef.current) {
          candlestickSeriesRef.current.update(currentCandleRef.current);
        }
      } else {
        // Update the current candle with the new tick
        const currentCandle = currentCandleRef.current;

        // Check if we need to start a new candle based on granularity
        // For simplicity, we'll update the current candle
        // In a production system, you'd calculate candle boundaries based on granularity
        currentCandle.close = price;
        currentCandle.high = Math.max(currentCandle.high, price);
        currentCandle.low = Math.min(currentCandle.low, price);

        if (candlestickSeriesRef.current && chartRef.current) {
          candlestickSeriesRef.current.update(currentCandle);
        }
      }
    } catch (err) {
      console.error('Error updating chart with tick data:', err);
    }
  }, [tickData, enableRealTimeUpdates, isConnected]);

  // Store the latest price for the indicator
  const latestPriceRef = useRef<number | null>(null);

  // Update price indicator with real-time tick data
  // The indicator spans the entire visible time range to remain visible during scrolling
  useEffect(() => {
    if (
      !enableRealTimeUpdates ||
      !tickData ||
      !priceIndicatorSeriesRef.current ||
      !chartRef.current ||
      !isConnected
    ) {
      return;
    }

    try {
      // Convert tick timestamp to Unix timestamp
      const tickTime = Math.floor(new Date(tickData.time).getTime() / 1000);

      // Use mid price for the indicator
      const price = tickData.mid;

      // Store the latest price for use when scrolling
      latestPriceRef.current = price;

      // Get the visible time range from the chart
      const timeScale = chartRef.current.timeScale();
      const visibleRange = timeScale.getVisibleRange();

      if (visibleRange) {
        // Create a horizontal line spanning the entire visible range
        // This ensures the indicator remains visible when scrolled away from latest candles
        const priceIndicatorData: LineData<Time>[] = [
          {
            time: visibleRange.from as Time,
            value: price,
          },
          {
            time: visibleRange.to as Time,
            value: price,
          },
        ];

        priceIndicatorSeriesRef.current.setData(priceIndicatorData);
      } else {
        // Fallback: if no visible range, just show at current time
        const priceIndicatorData: LineData<Time>[] = [
          {
            time: tickTime as Time,
            value: price,
          },
        ];

        priceIndicatorSeriesRef.current.setData(priceIndicatorData);
      }
    } catch (err) {
      console.error('Error updating price indicator with tick data:', err);
    }
  }, [tickData, enableRealTimeUpdates, isConnected]);

  // Update price indicator when visible range changes (during scrolling)
  // This keeps the indicator visible even when viewing historical data
  useEffect(() => {
    if (
      !enableRealTimeUpdates ||
      !priceIndicatorSeriesRef.current ||
      !chartRef.current ||
      !isConnected ||
      latestPriceRef.current === null
    ) {
      return;
    }

    const chart = chartRef.current;
    const priceIndicatorSeries = priceIndicatorSeriesRef.current;

    // Handler for updating the price indicator when scrolling
    const handleVisibleRangeChange = () => {
      if (!priceIndicatorSeries || latestPriceRef.current === null) {
        return;
      }

      try {
        const timeScale = chart.timeScale();
        const visibleRange = timeScale.getVisibleRange();

        if (visibleRange) {
          // Update the price indicator to span the new visible range
          // This maintains visibility regardless of scroll position
          const priceIndicatorData: LineData<Time>[] = [
            {
              time: visibleRange.from as Time,
              value: latestPriceRef.current,
            },
            {
              time: visibleRange.to as Time,
              value: latestPriceRef.current,
            },
          ];

          priceIndicatorSeries.setData(priceIndicatorData);
        }
      } catch (err) {
        console.error('Error updating price indicator during scroll:', err);
      }
    };

    // Subscribe to visible range changes to update the indicator span
    chart
      .timeScale()
      .subscribeVisibleLogicalRangeChange(handleVisibleRangeChange);

    // Cleanup subscription
    return () => {
      chart
        .timeScale()
        .unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange);
    };
  }, [enableRealTimeUpdates, isConnected]);

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
    if (
      candlestickSeriesRef.current &&
      'setMarkers' in candlestickSeriesRef.current &&
      typeof candlestickSeriesRef.current.setMarkers === 'function'
    ) {
      (
        candlestickSeriesRef.current.setMarkers as (
          markers: SeriesMarker<Time>[]
        ) => void
      )(markers);
    }
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
    <Box sx={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Loading indicator */}
      {isLoading && (
        <Box
          sx={{
            position: 'absolute',
            top: 8,
            left: 8,
            zIndex: 1000,
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderRadius: 1,
            px: 2,
            py: 1,
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          }}
        >
          <CircularProgress size={16} />
          <Typography variant="caption" sx={{ fontWeight: 500 }}>
            Loading {loadingDirection === 'older' ? 'older' : 'newer'} data...
          </Typography>
        </Box>
      )}

      <Box
        ref={chartContainerRef}
        sx={{
          width: '100%',
          height: '100%',
          border: '1px solid #e1e1e1',
          borderRadius: 1,
        }}
      />
    </Box>
  );
};

export default OHLCChart;
