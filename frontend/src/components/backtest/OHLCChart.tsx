import { useEffect, useRef, useState, useCallback } from 'react';
import {
  createChart,
  CandlestickSeries,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type Time,
  type SeriesMarker,
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
  calculateDataPoints,
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
  const isInitialLoadRef = useRef(true);

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

  // Calculate expected number of candles
  const expectedCandles = calculateDataPoints(
    new Date(startDate),
    new Date(endDate),
    selectedGranularity
  );

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

        // Fetch more candles initially (5000 max from API)
        const response = await apiClient.get<CandlesResponse>('/candles', {
          instrument,
          start_date: startDate,
          end_date: endDate,
          granularity,
          count: 5000,
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

    // Add trade markers immediately after setting data
    if (trades.length > 0) {
      console.log('[OHLCChart] Processing trades for markers:', {
        tradesCount: trades.length,
        firstTrade: trades[0],
        candleTimeRange: {
          first: allData[0]?.time,
          last: allData[allData.length - 1]?.time,
        },
      });

      const markers: SeriesMarker<Time>[] = trades.map((trade) => {
        const timestamp = new Date(trade.timestamp).getTime() / 1000;

        return {
          time: timestamp as Time,
          position: trade.action === 'buy' ? 'belowBar' : 'aboveBar',
          color: trade.action === 'buy' ? '#26a69a' : '#ef5350',
          shape: trade.action === 'buy' ? 'arrowUp' : 'arrowDown',
          text: `${trade.action.toUpperCase()} ${Math.abs(trade.units)} @ ${trade.price.toFixed(5)}`,
        };
      });

      console.log('[OHLCChart] Setting markers on new chart:', {
        markersCount: markers.length,
        firstMarker: markers[0],
        lastMarker: markers[markers.length - 1],
      });

      // Set markers on the candlestick series
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (candlestickSeries as any).setMarkers(markers);
        console.log('[OHLCChart] ✓ Markers set successfully');
      } catch (err) {
        console.error('[OHLCChart] ✗ Failed to set markers:', err);
      }
    }

    // Fit content on initial load
    if (isInitialLoadRef.current) {
      chart.timeScale().fitContent();
      isInitialLoadRef.current = false;
    }

    // Subscribe to visible range changes for infinite scrolling
    const timeScale = chart.timeScale();
    const handleVisibleRangeChange = () => {
      const logicalRange = timeScale.getVisibleLogicalRange();
      if (!logicalRange) return;

      const barsInfo = candlestickSeries.barsInLogicalRange(logicalRange);
      if (!barsInfo) return;

      // Load older data when scrolling near the left edge
      if (logicalRange.from < 50) {
        console.log('[OHLCChart] Near left edge, loading older data');
        loadOlderData();
      }

      // Load newer data when scrolling near the right edge
      const totalBars = allData.length;
      if (logicalRange.to > totalBars - 50) {
        console.log('[OHLCChart] Near right edge, loading newer data');
        loadNewerData();
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
  }, [allData, height, trades, loadOlderData, loadNewerData]);

  // Update chart data when allData changes (for infinite scroll)
  useEffect(() => {
    if (!candlestickSeriesRef.current || allData.length === 0) return;

    candlestickSeriesRef.current.setData(allData);

    // Re-apply markers after data update
    if (trades.length > 0) {
      const markers: SeriesMarker<Time>[] = trades.map((trade) => {
        const timestamp = new Date(trade.timestamp).getTime() / 1000;
        return {
          time: timestamp as Time,
          position: trade.action === 'buy' ? 'belowBar' : 'aboveBar',
          color: trade.action === 'buy' ? '#26a69a' : '#ef5350',
          shape: trade.action === 'buy' ? 'arrowUp' : 'arrowDown',
          text: `${trade.action.toUpperCase()} ${Math.abs(trade.units)} @ ${trade.price.toFixed(5)}`,
        };
      });

      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (candlestickSeriesRef.current as any).setMarkers(markers);
      } catch (err) {
        console.error('[OHLCChart] Failed to update markers:', err);
      }
    }
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
      {/* Controls and Info */}
      <Box
        sx={{
          mb: 2,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 2,
        }}
      >
        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          <Typography variant="body2" color="text.secondary">
            {trades.length > 0
              ? `${trades.length} trade${trades.length !== 1 ? 's' : ''} marked`
              : 'No trades'}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {allData.length} / {expectedCandles} candles
            {loadingMore && ' (loading...)'}
            {!loadingMore && allData.length < expectedCandles && (
              <Typography
                component="span"
                variant="body2"
                color="info.main"
                sx={{ ml: 1 }}
              >
                (scroll to load more)
              </Typography>
            )}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {new Date(startDate).toLocaleDateString()} -{' '}
            {new Date(endDate).toLocaleDateString()}
          </Typography>
        </Box>

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

      {/* Chart Container */}
      <Box ref={chartContainerRef} sx={{ position: 'relative' }} />
    </Box>
  );
}
