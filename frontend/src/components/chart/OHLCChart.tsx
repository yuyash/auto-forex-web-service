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
  fetchCandles: (
    instrument: string,
    granularity: string,
    count: number,
    before?: number,
    after?: number
  ) => Promise<OHLCData[]>;
  config?: ChartConfig;
  enableRealTimeUpdates?: boolean;
  positions?: Position[];
  orders?: Order[];
  onViewingLatestChange?: (isViewingLatest: boolean) => void;
  onChartReady?: (chartApi: IChartApi) => void;
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
  fetchCandles,
  config = {},
  enableRealTimeUpdates = false,
  positions = [],
  orders = [],
  onViewingLatestChange,
  onChartReady,
}: OHLCChartProps) => {
  // Chart refs
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
  const currentCandleRef = useRef<CandlestickData<Time> | null>(null);

  // Debounce timer ref for scroll handling
  const scrollDebounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );

  // Internal data state - single source of truth
  const [allData, setAllData] = useState<OHLCData[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [loadingDirection, setLoadingDirection] = useState<
    'older' | 'newer' | null
  >(null);
  const [error, setError] = useState<string | null>(null);
  const [isInitialLoad, setIsInitialLoad] = useState<boolean>(true);

  /**
   * Load initial data when component mounts or instrument/granularity changes
   */
  const loadInitialData = useCallback(async () => {
    console.log('🔄 Loading initial data for', instrument, granularity);
    setIsLoading(true);
    setLoadingDirection(null);
    setError(null);
    setIsInitialLoad(true);

    try {
      const data = await fetchCandles(instrument, granularity, 5000);
      // Only update data after successful fetch to prevent flash
      setAllData(data);
      console.log('✅ Loaded', data.length, 'candles');
      console.log(
        '📊 Data range:',
        data[0]?.time,
        'to',
        data[data.length - 1]?.time
      );
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load initial data';
      console.error('❌ Error loading initial data:', err);
      setError(errorMessage);
      // Only clear data on error
      setAllData([]);
    } finally {
      setIsLoading(false);
    }
  }, [instrument, granularity, fetchCandles]);

  /**
   * Load initial data on mount and when instrument/granularity changes
   */
  useEffect(() => {
    console.log('🔄 Instrument or granularity changed, loading fresh data');
    loadInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [instrument, granularity]);

  /**
   * Load older historical data (prepend to beginning)
   */
  const loadOlderData = useCallback(async () => {
    if (isLoading || allData.length === 0) {
      console.log(
        '⏸️ Skipping loadOlderData: isLoading=',
        isLoading,
        'allData.length=',
        allData.length
      );
      return;
    }

    const oldestTime = allData[0].time;
    console.log('🔄 Loading older data, current oldest:', oldestTime);

    setIsLoading(true);
    setLoadingDirection('older');

    try {
      const olderData = await fetchCandles(
        instrument,
        granularity,
        5000,
        oldestTime
      );

      console.log('📥 Received', olderData.length, 'older candles from API');
      if (olderData.length > 0) {
        console.log(
          '📊 Older data range:',
          olderData[0]?.time,
          'to',
          olderData[olderData.length - 1]?.time
        );
      }

      if (olderData.length > 0) {
        // Check if API returned actually older data or just the latest data
        const hasActuallyOlderData = olderData.some((c) => c.time < oldestTime);

        if (!hasActuallyOlderData) {
          console.warn(
            '⚠️ API returned no data older than',
            oldestTime,
            '- may have reached the beginning or API issue'
          );
          return;
        }

        // Filter out any candles that overlap with existing data (including boundary)
        const filteredOlderData = olderData.filter((c) => c.time < oldestTime);

        console.log(
          '🔍 After filtering:',
          filteredOlderData.length,
          'candles (removed',
          olderData.length - filteredOlderData.length,
          'duplicates)'
        );

        if (filteredOlderData.length > 0) {
          // Sort older data before prepending to ensure order
          filteredOlderData.sort((a, b) => a.time - b.time);
          setAllData((prevData) => [...filteredOlderData, ...prevData]);
          console.log(
            '➕ Prepended',
            filteredOlderData.length,
            'older candles'
          );
        }
      } else {
        console.log('ℹ️ No older data available');
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load older data';
      console.error('❌ Error loading older data:', err);
      setError(errorMessage);
      // Don't clear allData on error
    } finally {
      setIsLoading(false);
      setLoadingDirection(null);
    }
  }, [isLoading, allData, instrument, granularity, fetchCandles]);

  /**
   * Load newer data (append to end)
   */
  const loadNewerData = useCallback(async () => {
    if (isLoading || allData.length === 0) {
      console.log(
        '⏸️ Skipping loadNewerData: isLoading=',
        isLoading,
        'allData.length=',
        allData.length
      );
      return;
    }

    const newestTime = allData[allData.length - 1].time;
    const currentTime = Math.floor(Date.now() / 1000);
    const granularityDuration = getGranularityDuration(granularity);

    // Check if already at current time
    if (currentTime - newestTime <= granularityDuration) {
      console.log('ℹ️ Already at current time, no newer data to load');
      return;
    }

    console.log('🔄 Loading newer data, current newest:', newestTime);

    setIsLoading(true);
    setLoadingDirection('newer');

    try {
      // Use 'after' parameter to fetch candles starting after newestTime
      const newerData = await fetchCandles(
        instrument,
        granularity,
        5000,
        undefined, // no 'before'
        newestTime // 'after' parameter
      );

      console.log('📥 Received', newerData.length, 'newer candles from API');
      if (newerData.length > 0) {
        console.log(
          '📊 Newer data range:',
          newerData[0]?.time,
          'to',
          newerData[newerData.length - 1]?.time
        );
      }

      // Filter out any candles that overlap with existing data
      const newCandles = newerData.filter((c) => c.time > newestTime);

      if (newCandles.length > 0) {
        // Sort new candles before appending to ensure order
        newCandles.sort((a, b) => a.time - b.time);
        setAllData((prevData) => [...prevData, ...newCandles]);
        console.log('➕ Appended', newCandles.length, 'newer candles');
      } else {
        console.log('ℹ️ No new candles to append (already at latest)');
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load newer data';
      console.error('❌ Error loading newer data:', err);
      setError(errorMessage);
      // Don't clear allData on error
    } finally {
      setIsLoading(false);
      setLoadingDirection(null);
    }
  }, [isLoading, allData, instrument, granularity, fetchCandles]);

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

  // Store callbacks in refs to avoid recreating chart on every data change
  const loadOlderDataRef = useRef(loadOlderData);
  const loadNewerDataRef = useRef(loadNewerData);
  const allDataRef = useRef(allData);
  const isLoadingRef = useRef(isLoading);

  useEffect(() => {
    loadOlderDataRef.current = loadOlderData;
    loadNewerDataRef.current = loadNewerData;
    allDataRef.current = allData;
    isLoadingRef.current = isLoading;
  });

  // Initialize chart - only once on mount
  useEffect(() => {
    console.log('🎨 Initializing chart (should only happen once)');
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

    // Notify parent that chart is ready
    if (onChartReady) {
      onChartReady(chart);
    }

    // Handle window resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    // Subscribe to visible logical range changes for scroll-based loading
    const handleVisibleRangeChange = () => {
      if (!chartRef.current || isLoadingRef.current) {
        return;
      }

      const logicalRange = chartRef.current
        .timeScale()
        .getVisibleLogicalRange();
      if (!logicalRange || allDataRef.current.length === 0) {
        return;
      }

      const totalBars = allDataRef.current.length;

      // Check if user is viewing the latest candles (within 50 bars of the end)
      const isViewingLatest = logicalRange.to > totalBars - 50;
      if (onViewingLatestChange) {
        onViewingLatestChange(isViewingLatest);
      }

      // Clear existing debounce timer
      if (scrollDebounceTimerRef.current) {
        clearTimeout(scrollDebounceTimerRef.current);
      }

      // Debounce data loading - wait 300ms after user stops scrolling
      scrollDebounceTimerRef.current = setTimeout(() => {
        // Load older data when within 10 bars of left edge
        if (logicalRange.from < 10) {
          console.log('📍 Near left edge, loading older data');
          loadOlderDataRef.current();
        }
        // Load newer data when within 10 bars of right edge
        else if (logicalRange.to > totalBars - 10) {
          console.log('📍 Near right edge, loading newer data');
          loadNewerDataRef.current();
        }
      }, 300);
    };

    chart
      .timeScale()
      .subscribeVisibleLogicalRangeChange(handleVisibleRangeChange);

    // Cleanup
    return () => {
      console.log('🧹 Cleaning up chart');

      // Clear debounce timer
      if (scrollDebounceTimerRef.current) {
        clearTimeout(scrollDebounceTimerRef.current);
      }

      window.removeEventListener('resize', handleResize);

      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
      candlestickSeriesRef.current = null;
      takeProfitSeriesRef.current = null;
      stopLossSeriesRef.current = null;
      priceIndicatorSeriesRef.current = null;
      currentCandleRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Update chart rendering when allData changes
   */
  useEffect(() => {
    console.log('🔄 Render effect triggered', {
      hasChart: !!chartRef.current,
      hasSeries: !!candlestickSeriesRef.current,
      dataLength: allData.length,
    });

    if (!candlestickSeriesRef.current || !chartRef.current) {
      console.log('⚠️ Chart or series not ready yet');
      return;
    }

    if (allData.length === 0) {
      console.log('📊 No data to render yet - clearing chart');
      candlestickSeriesRef.current.setData([]);
      return;
    }

    console.log('📊 Rendering', allData.length, 'candles');
    console.log(
      '📊 Data range:',
      allData[0]?.time,
      'to',
      allData[allData.length - 1]?.time
    );

    // Filter out invalid data and map to candlestick format
    const candlestickData: CandlestickData<Time>[] = allData
      .filter((item) => {
        // Validate that all required fields are present and valid
        const isValid =
          item.time != null &&
          item.open != null &&
          item.high != null &&
          item.low != null &&
          item.close != null &&
          !isNaN(item.open) &&
          !isNaN(item.high) &&
          !isNaN(item.low) &&
          !isNaN(item.close);

        if (!isValid) {
          console.warn('⚠️ Filtering out invalid candle:', item);
        }

        return isValid;
      })
      .map((item) => ({
        time: item.time as Time,
        open: item.open,
        high: item.high,
        low: item.low,
        close: item.close,
      }));

    // Sort data by time in ascending order to ensure lightweight-charts requirement
    candlestickData.sort((a, b) => (a.time as number) - (b.time as number));

    // Remove duplicates - keep the last occurrence of each timestamp
    const deduplicatedData: CandlestickData<Time>[] = [];
    const seenTimes = new Set<number>();

    for (let i = candlestickData.length - 1; i >= 0; i--) {
      const time = candlestickData[i].time as number;
      if (!seenTimes.has(time)) {
        seenTimes.add(time);
        deduplicatedData.unshift(candlestickData[i]);
      }
    }

    if (deduplicatedData.length !== candlestickData.length) {
      console.warn(
        `⚠️ Removed ${candlestickData.length - deduplicatedData.length} duplicate timestamps`
      );
    }

    // Save the current visible TIME RANGE (not logical range) before updating data
    const timeScale = chartRef.current.timeScale();
    const visibleTimeRange = timeScale.getVisibleRange();

    console.log('📊 Setting data on series...');
    candlestickSeriesRef.current.setData(deduplicatedData);
    console.log('✅ Data set successfully');

    // Only fit content on initial load, otherwise preserve viewport
    if (isInitialLoad && allData.length > 0 && candlestickData.length > 0) {
      console.log('📐 Initial load - fitting content');
      chartRef.current.timeScale().fitContent();
      setIsInitialLoad(false);
    } else if (
      visibleTimeRange &&
      !isInitialLoad &&
      'setVisibleRange' in timeScale &&
      typeof timeScale.setVisibleRange === 'function'
    ) {
      // Restore the viewport TIME RANGE after data update
      // This maintains the same absolute time window regardless of data changes
      console.log('📍 Restoring viewport time range:', visibleTimeRange);
      timeScale.setVisibleRange(visibleTimeRange);
    }
  }, [allData, isInitialLoad]);

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
    <Box
      sx={{ position: 'relative', width: '100%', height: '100%' }}
      data-testid="ohlc-chart-container"
    >
      {/* Loading indicator */}
      {isLoading && (
        <Box
          data-testid="chart-loading-indicator"
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
          <Typography
            variant="caption"
            sx={{ fontWeight: 500 }}
            data-testid="loading-direction-text"
          >
            Loading {loadingDirection === 'older' ? 'older' : 'newer'} data...
          </Typography>
        </Box>
      )}

      <Box
        ref={chartContainerRef}
        data-testid="chart-canvas"
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
