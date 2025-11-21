import { useEffect, useRef, useState, useCallback } from 'react';
import {
  createChart,
  CandlestickSeries,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type Time,
  type Logical,
} from 'lightweight-charts';
import {
  Box,
  CircularProgress,
  Typography,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  type SelectChangeEvent,
} from '@mui/material';
import {
  calculateGranularity,
  getAvailableGranularities,
  type OandaGranularity,
} from '../../utils/granularityCalculator';
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
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [allData, setAllData] = useState<CandlestickData[]>([]);
  const [verticalLines, setVerticalLines] = useState<{
    start: number | null;
    end: number | null;
  }>({ start: null, end: null });
  const isInitialLoadRef = useRef(true);
  const allowScrollLoadRef = useRef(false);

  // Calculate default granularity to show entire range
  const defaultGranularity = calculateGranularity(
    new Date(startDate),
    new Date(endDate)
  );

  // Use state for granularity to allow user control
  const [selectedGranularity, setSelectedGranularity] =
    useState<OandaGranularity>(
      (providedGranularity as OandaGranularity) || defaultGranularity
    );

  const granularity = selectedGranularity;

  const handleGranularityChange = (event: SelectChangeEvent<string>) => {
    setSelectedGranularity(event.target.value as OandaGranularity);
  };

  // Fetch initial candles (larger batch for better UX)
  useEffect(() => {
    const fetchInitialCandles = async () => {
      try {
        setLoading(true);
        setError(null);
        isInitialLoadRef.current = true;

        // Fetch candles for the exact date range (no count limit)
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

        console.log('[OHLCChart] Initial candles fetched:', {
          requested: {
            instrument,
            startDate,
            endDate,
            granularity,
          },
          received: {
            count: transformedData.length,
            firstCandle: transformedData[0],
            lastCandle: transformedData[transformedData.length - 1],
          },
        });

        setAllData(transformedData);
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

    fetchInitialCandles();
  }, [instrument, startDate, endDate, granularity]);

  // Load older data when scrolling left
  const loadOlderData = useCallback(async () => {
    if (loadingMore || allData.length === 0) return;

    const oldestTime = allData[0].time;
    const oldestDate = new Date((oldestTime as number) * 1000);

    console.log('[OHLCChart] Loading older data before:', oldestDate);

    try {
      setLoadingMore(true);

      // Calculate how far back to fetch (500 candles)
      const response = await apiClient.get<CandlesResponse>('/candles', {
        instrument,
        end_date: oldestDate.toISOString(),
        granularity,
        count: 500,
      });

      const olderData: CandlestickData[] = response.candles.map((candle) => ({
        time: candle.time as Time,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      }));

      // Filter out any data that overlaps with existing data
      const filteredOlderData = olderData.filter((c) => c.time < oldestTime);

      if (filteredOlderData.length > 0) {
        console.log('[OHLCChart] Prepending older data:', {
          count: filteredOlderData.length,
          oldestNew: filteredOlderData[0],
        });
        setAllData((prev) => [...filteredOlderData, ...prev]);
      } else {
        console.log('[OHLCChart] No older data available');
      }
    } catch (err) {
      console.error('[OHLCChart] Failed to load older data:', err);
    } finally {
      setLoadingMore(false);
    }
  }, [instrument, granularity, loadingMore, allData]);

  // Load newer data when scrolling right
  const loadNewerData = useCallback(async () => {
    if (loadingMore || allData.length === 0) return;

    const newestTime = allData[allData.length - 1].time;
    const newestDate = new Date((newestTime as number) * 1000);

    console.log('[OHLCChart] Loading newer data after:', newestDate);

    try {
      setLoadingMore(true);

      // Calculate how far forward to fetch (500 candles)
      const response = await apiClient.get<CandlesResponse>('/candles', {
        instrument,
        start_date: newestDate.toISOString(),
        granularity,
        count: 500,
      });

      const newerData: CandlestickData[] = response.candles.map((candle) => ({
        time: candle.time as Time,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      }));

      // Filter out any data that overlaps with existing data
      const filteredNewerData = newerData.filter((c) => c.time > newestTime);

      if (filteredNewerData.length > 0) {
        console.log('[OHLCChart] Appending newer data:', {
          count: filteredNewerData.length,
          newestNew: filteredNewerData[filteredNewerData.length - 1],
        });
        setAllData((prev) => [...prev, ...filteredNewerData]);
      } else {
        console.log('[OHLCChart] No newer data available');
      }
    } catch (err) {
      console.error('[OHLCChart] Failed to load newer data:', err);
    } finally {
      setLoadingMore(false);
    }
  }, [instrument, granularity, loadingMore, allData]);

  // Create and manage chart
  useEffect(() => {
    if (!chartContainerRef.current || allData.length === 0) return;

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
        rightOffset: 0,
        lockVisibleTimeRangeOnResize: true,
        shiftVisibleRangeOnNewBar: false,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
    });

    chartRef.current = chart;

    // Add candlestick series
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    });

    candlestickSeriesRef.current = candlestickSeries;

    // Set data
    candlestickSeries.setData(allData);

    // Trade markers temporarily disabled
    // TODO: Re-enable when lightweight-charts marker API is fixed

    // Set visible range to backtest period with buffer on initial load
    const startTime = new Date(startDate).getTime() / 1000;
    const endTime = new Date(endDate).getTime() / 1000;

    if (isInitialLoadRef.current) {
      // Add 10% buffer on each side so vertical lines are visible
      const timeRange = endTime - startTime;
      const buffer = timeRange * 0.1;

      const minTime = startTime - buffer;
      const maxTime = endTime + buffer;

      // Use setVisibleLogicalRange instead of setVisibleRange
      // Find the logical indices for the time range
      const minIndex = allData.findIndex((d) => (d.time as number) >= minTime);
      const maxIndex = allData.findIndex((d) => (d.time as number) >= maxTime);

      if (minIndex !== -1 && maxIndex !== -1) {
        chart.timeScale().setVisibleLogicalRange({
          from: Math.max(0, minIndex) as Logical,
          to: Math.min(allData.length - 1, maxIndex) as Logical,
        });
      }

      isInitialLoadRef.current = false;

      // Enable scroll loading after a delay to prevent auto-load on mount
      setTimeout(() => {
        allowScrollLoadRef.current = true;
      }, 1000);
    }

    // Update vertical line positions
    const chartTimeScale = chart.timeScale();

    const updateVerticalLines = () => {
      const startTime = new Date(startDate).getTime() / 1000;
      const endTime = new Date(endDate).getTime() / 1000;

      // Try using timeToCoordinate first
      let startX: number | null = chartTimeScale.timeToCoordinate(
        startTime as Time
      );
      let endX: number | null = chartTimeScale.timeToCoordinate(
        endTime as Time
      );

      // If that fails, manually calculate based on visible range
      if (startX === null || endX === null) {
        const visibleRange = chartTimeScale.getVisibleRange();
        if (visibleRange && chartContainerRef.current) {
          const chartWidth = chartContainerRef.current.clientWidth;
          const timeRange =
            (visibleRange.to as number) - (visibleRange.from as number);

          if (startX === null) {
            const startOffset = startTime - (visibleRange.from as number);
            startX = Math.round((startOffset / timeRange) * chartWidth);
          }

          if (endX === null) {
            const endOffset = endTime - (visibleRange.from as number);
            endX = Math.round((endOffset / timeRange) * chartWidth);
          }
        }
      }

      console.log('[OHLCChart] Vertical lines calculated:', { startX, endX });

      // Only update if we have valid coordinates
      if (startX !== null && endX !== null) {
        setVerticalLines({ start: startX, end: endX });
      }
    };

    // Delay initial update to ensure chart is fully rendered
    setTimeout(updateVerticalLines, 200);

    // Update on scroll/zoom
    chartTimeScale.subscribeVisibleLogicalRangeChange(updateVerticalLines);

    // Prevent scrolling beyond data range
    const timeScale = chart.timeScale();
    const handleVisibleRangeChange = () => {
      const logicalRange = timeScale.getVisibleLogicalRange();
      if (!logicalRange) return;

      // Clamp the visible range to prevent scrolling beyond data
      let needsAdjustment = false;
      let newFrom = logicalRange.from;
      let newTo = logicalRange.to;

      if ((logicalRange.from as number) < 0) {
        newFrom = 0 as Logical;
        needsAdjustment = true;
      }

      if ((logicalRange.to as number) > allData.length) {
        newTo = allData.length as Logical;
        needsAdjustment = true;
      }

      if (needsAdjustment) {
        timeScale.setVisibleLogicalRange({ from: newFrom, to: newTo });
      }
    };

    timeScale.subscribeVisibleLogicalRangeChange(handleVisibleRangeChange);

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
      timeScale.unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange);
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [
    allData,
    height,
    trades,
    loadOlderData,
    loadNewerData,
    startDate,
    endDate,
  ]);

  // Update chart data when allData changes (for infinite scroll)
  useEffect(() => {
    if (!candlestickSeriesRef.current || allData.length === 0) return;

    candlestickSeriesRef.current.setData(allData);

    // Trade markers temporarily disabled
    // TODO: Re-enable when lightweight-charts marker API is fixed
  }, [allData, trades]);

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

  if (allData.length === 0) {
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
      {/* Granularity Control */}
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'flex-end' }}>
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel id="granularity-select-label">Granularity</InputLabel>
          <Select
            labelId="granularity-select-label"
            id="granularity-select"
            value={selectedGranularity}
            label="Granularity"
            onChange={handleGranularityChange}
          >
            {getAvailableGranularities().map((gran) => (
              <MenuItem key={gran} value={gran}>
                {gran}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {/* Chart Container with Vertical Lines */}
      <Box ref={chartContainerRef} sx={{ position: 'relative' }}>
        {/* Vertical line overlays for backtest start/end */}
        {verticalLines.start !== null && (
          <>
            <Box
              sx={{
                position: 'absolute',
                left: `${verticalLines.start}px`,
                top: 0,
                bottom: 0,
                width: '2px',
                borderLeft: '2px dashed #666',
                pointerEvents: 'none',
                zIndex: 1,
              }}
            />
            <Box
              sx={{
                position: 'absolute',
                left: `${verticalLines.start + 5}px`,
                top: '10px',
                bgcolor: 'rgba(255, 255, 255, 0.9)',
                px: 1,
                py: 0.5,
                borderRadius: 1,
                border: '1px solid #666',
                pointerEvents: 'none',
                zIndex: 2,
                fontSize: '0.75rem',
                fontWeight: 'bold',
                color: '#666',
              }}
            >
              Start: {new Date(startDate).toLocaleString()}
            </Box>
          </>
        )}
        {verticalLines.end !== null && (
          <>
            <Box
              sx={{
                position: 'absolute',
                left: `${verticalLines.end}px`,
                top: 0,
                bottom: 0,
                width: '2px',
                borderLeft: '2px dashed #666',
                pointerEvents: 'none',
                zIndex: 1,
              }}
            />
            <Box
              sx={{
                position: 'absolute',
                left: `${verticalLines.end - 180}px`,
                top: '10px',
                bgcolor: 'rgba(255, 255, 255, 0.9)',
                px: 1,
                py: 0.5,
                borderRadius: 1,
                border: '1px solid #666',
                pointerEvents: 'none',
                zIndex: 2,
                fontSize: '0.75rem',
                fontWeight: 'bold',
                color: '#666',
              }}
            >
              End: {new Date(endDate).toLocaleString()}
            </Box>
          </>
        )}
      </Box>
    </Box>
  );
}
