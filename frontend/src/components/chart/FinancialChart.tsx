/**
 * FinancialChart - Core Chart Component
 *
 * Base chart component that wraps react-financial-charts and provides common functionality
 * for displaying OHLC candlestick charts with overlays, markers, and interactive features.
 *
 * Features:
 * - Candlestick rendering with OHLC data
 * - Custom markers (buy/sell/start/end) with SVG paths
 * - Vertical and horizontal line overlays
 * - Pan and zoom interactions
 * - OHLC tooltip on hover
 * - Reset view functionality
 * - Marker visibility toggles
 * - Timezone-aware axis formatting
 * - Scroll-based data loading callbacks
 */

import React, { useState, useMemo, useCallback, useRef } from 'react';
import {
  Chart,
  ChartCanvas,
  GenericChartComponent,
} from 'react-financial-charts';
import { getAxisCanvas } from '@react-financial-charts/core';
import { CandlestickSeries } from '@react-financial-charts/series';
import { XAxis, YAxis } from '@react-financial-charts/axes';
import { discontinuousTimeScaleProviderBuilder } from '@react-financial-charts/scales';
import {
  MouseCoordinateX,
  MouseCoordinateY,
  CrossHairCursor,
} from '@react-financial-charts/coordinates';
import {
  Annotate,
  SvgPathAnnotation,
  LabelAnnotation,
} from '@react-financial-charts/annotations';
import { OHLCTooltip } from '@react-financial-charts/tooltip';
import { timeFormat } from 'd3-time-format';
import {
  Box,
  Button,
  ButtonGroup,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import { formatInTimeZone } from 'date-fns-tz';
import type {
  ChartMarker,
  VerticalLine,
  HorizontalLine,
} from '../../utils/chartMarkers';
import {
  buyPath,
  sellPath,
  circlePath,
  doubleCirclePath,
} from '../../utils/chartMarkers';
import { useResizeObserver } from '../../hooks/useResizeObserver';

/**
 * OHLC Data interface for chart rendering
 */
export interface OHLCData {
  date: Date;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

/**
 * FinancialChart Props
 */
export interface FinancialChartProps {
  // Data
  data: OHLCData[];

  // Dimensions
  width?: number; // Optional fixed width, if not provided will be responsive
  height?: number;

  // Overlays
  verticalLines?: VerticalLine[];
  horizontalLines?: HorizontalLine[];
  markers?: ChartMarker[];

  // Interactions
  onMarkerClick?: (marker: ChartMarker) => void;
  onResetView?: () => void;
  onUpdateView?: () => void;

  // Configuration
  initialVisibleRange?: { from: Date; to: Date };
  enablePan?: boolean;
  enableZoom?: boolean;
  showGrid?: boolean;
  showCrosshair?: boolean;
  showOHLCTooltip?: boolean;
  showResetButton?: boolean;
  enableMarkerToggle?: boolean;
  timezone?: string; // IANA timezone (e.g., 'America/New_York', 'UTC')
  latestPrice?: number | null; // Latest mid price to display on right Y-axis
  showDataGaps?: boolean; // Show visual indicators for missing data periods

  // Loading and error states
  loading?: boolean;
  error?: string | null;
}

/**
 * FinancialChart Component
 */
export const FinancialChart: React.FC<FinancialChartProps> = ({
  data,
  width: fixedWidth,
  height = 500,
  verticalLines = [],
  horizontalLines = [],
  markers = [],
  onMarkerClick,
  onResetView,
  onUpdateView,
  initialVisibleRange,
  enablePan = true,
  enableZoom = true,
  showGrid = true,
  showCrosshair = true,
  showOHLCTooltip = true,
  showResetButton = true,
  enableMarkerToggle = true,
  timezone = 'UTC',
  latestPrice = null,
  showDataGaps = false,
  loading = false,
  error = null,
}) => {
  // Container ref for responsive width
  const containerRef = useRef<HTMLDivElement>(null);
  const { width: containerWidth } = useResizeObserver(containerRef);

  // Use fixed width if provided, otherwise use container width
  // Subtract border (2px), margins, and add buffer to prevent overflow
  // Using a more conservative subtraction to account for all spacing
  const width =
    fixedWidth || (containerWidth > 0 ? Math.floor(containerWidth - 10) : 0);

  // State for marker visibility toggles
  const [showBuySellMarkers, setShowBuySellMarkers] = useState(true);
  const [showStartEndMarkers, setShowStartEndMarkers] = useState(true);
  const [resetKey, setResetKey] = useState(0);

  // Suppress unused variable warnings
  void enablePan;
  void enableZoom;
  void onUpdateView;

  // Configure the scale
  const xScaleProvider =
    discontinuousTimeScaleProviderBuilder().inputDateAccessor(
      (d: OHLCData) => d.date
    );

  const {
    data: chartData,
    xScale,
    xAccessor,
    displayXAccessor,
  } = useMemo(() => xScaleProvider(data), [data, xScaleProvider]);

  // Extra bottom margin to support two stacked X axes (time + date).
  const margin = { left: 50, right: 50, top: 10, bottom: 75 };

  // Calculate initial x extents
  const initialXExtents = useMemo(() => {
    if (!chartData || chartData.length === 0) return undefined;

    if (initialVisibleRange) {
      // Find indices for the initial visible range
      const fromIndex = chartData.findIndex(
        (d) => d.date >= initialVisibleRange.from
      );
      const toIndex = chartData.findIndex(
        (d) => d.date >= initialVisibleRange.to
      );

      if (fromIndex !== -1 && toIndex !== -1) {
        return [xAccessor(chartData[fromIndex]), xAccessor(chartData[toIndex])];
      }
    }

    // Default: show all data
    return [
      xAccessor(chartData[0]),
      xAccessor(chartData[chartData.length - 1]),
    ];
  }, [chartData, initialVisibleRange, xAccessor]);

  // Handle reset view
  const handleResetView = useCallback(() => {
    setResetKey((prev) => prev + 1);
    onResetView?.();
  }, [onResetView]);

  // Filter markers based on visibility toggles
  const visibleMarkers = useMemo(() => {
    const filtered = markers.filter((marker) => {
      if (
        marker.type === 'buy' ||
        marker.type === 'sell' ||
        marker.type === 'initial_entry'
      ) {
        return showBuySellMarkers;
      }
      if (marker.type === 'start_strategy' || marker.type === 'end_strategy') {
        return showStartEndMarkers;
      }
      return true; // Show other marker types by default
    });

    return filtered;
  }, [markers, showBuySellMarkers, showStartEndMarkers]);

  // Detect data gaps - periods where data is missing
  const dataGaps = useMemo(() => {
    if (
      !showDataGaps ||
      !chartData ||
      chartData.length < 2 ||
      !initialVisibleRange
    ) {
      return [];
    }

    const gaps: Array<{
      start: Date;
      end: Date;
      type: 'start' | 'middle' | 'end';
    }> = [];

    // Calculate expected interval based on first few candles (used for all gap detection)
    let avgInterval = 3600000; // Default 1 hour in milliseconds
    if (chartData.length >= 3) {
      const interval1 =
        chartData[1].date.getTime() - chartData[0].date.getTime();
      const interval2 =
        chartData[2].date.getTime() - chartData[1].date.getTime();
      avgInterval = (interval1 + interval2) / 2;
    }

    // Check for gap at the beginning (before first candle)
    const requestedStart = initialVisibleRange.from;
    const firstCandle = chartData[0].date;
    const timeDiffStart = firstCandle.getTime() - requestedStart.getTime();

    // For start gaps, use 2x threshold to avoid flagging small timing differences
    // This is more lenient because market data often starts slightly after requested time
    if (timeDiffStart > avgInterval * 2) {
      gaps.push({
        start: requestedStart,
        end: firstCandle,
        type: 'start',
      });
    }

    // Check for gap at the end (after last candle)
    const requestedEnd = initialVisibleRange.to;
    const lastCandle = chartData[chartData.length - 1].date;
    const timeDiffEnd = requestedEnd.getTime() - lastCandle.getTime();

    // For end gaps, use a lower threshold (0.5x) to show when backtest ends before next candle
    // This helps visualize that there's no data after the last candle until the requested end time
    if (timeDiffEnd > avgInterval * 0.5) {
      gaps.push({
        start: lastCandle,
        end: requestedEnd,
        type: 'end',
      });
    }

    // Check for gaps between candles (large time jumps - weekends, holidays, etc.)
    // Use 1.5x threshold for middle gaps to catch weekend closures
    const gapThreshold = avgInterval * 1.5;

    for (let i = 0; i < chartData.length - 1; i++) {
      const current = chartData[i].date;
      const next = chartData[i + 1].date;
      const timeDiff = next.getTime() - current.getTime();

      if (timeDiff > gapThreshold) {
        gaps.push({
          start: current,
          end: next,
          type: 'middle',
        });
      }
    }

    return gaps;
  }, [chartData, showDataGaps, initialVisibleRange]);

  // Format time for axis based on timezone and data density
  // Note: react-financial-charts passes the index to tickFormat, not the date
  // Calculate visible time range and data density
  const getVisibleTimeRange = useCallback(() => {
    if (!chartData || chartData.length < 2) return 0;

    // Get first and last visible dates
    const firstDate = chartData[0]?.date;
    const lastDate = chartData[chartData.length - 1]?.date;

    if (!firstDate || !lastDate) return 0;

    return lastDate.getTime() - firstDate.getTime();
  }, [chartData]);

  // Determine optimal format based on data range and density
  const getOptimalFormat = useCallback(() => {
    if (!chartData || chartData.length < 2) return 'MMM dd';

    const visibleRange = getVisibleTimeRange();
    const dataPointCount = chartData.length;

    const oneMinute = 60 * 1000;
    const oneHour = 60 * oneMinute;
    const oneDay = 24 * oneHour;
    const oneWeek = 7 * oneDay;
    const oneMonth = 30 * oneDay;

    // Calculate average time between data points (granularity)
    const avgInterval =
      dataPointCount > 1 ? visibleRange / (dataPointCount - 1) : visibleRange;

    // Key insight: If granularity is less than a day, always show time
    const isIntradayData = avgInterval < oneDay;

    // Determine format based on both range and granularity
    if (visibleRange <= oneDay) {
      // Single day view: show only time
      return 'HH:mm';
    } else if (visibleRange <= 3 * oneDay) {
      // 1-3 days: show date and time
      return 'MM-dd HH:mm';
    } else if (visibleRange <= oneWeek) {
      // Up to 1 week
      if (isIntradayData) {
        // Intraday data: show date and time
        return 'MM-dd HH:mm';
      } else {
        // Daily or less frequent: just date
        return 'MMM dd';
      }
    } else if (visibleRange <= oneMonth) {
      // 1 week to 1 month
      if (isIntradayData) {
        // Intraday data: show date and time
        return 'MM-dd HH:mm';
      } else {
        // Daily data: just date
        return 'MMM dd';
      }
    } else if (visibleRange <= 6 * oneMonth) {
      // 1-6 months
      if (isIntradayData) {
        // Intraday data: show date and time
        return 'MM-dd HH:mm';
      } else {
        // Daily data: month and day
        return 'MMM dd';
      }
    } else if (visibleRange <= 365 * oneDay) {
      // 6 months to 1 year
      if (isIntradayData) {
        // Intraday data: show date and time
        return 'yyyy-MM-dd HH:mm';
      } else {
        // Daily data: month and year
        return 'MMM yyyy';
      }
    } else {
      // More than 1 year
      if (isIntradayData) {
        // Intraday data: show date and time
        return 'yyyy-MM-dd HH:mm';
      } else {
        // Daily data: year-month-day
        return 'yyyy-MM-dd';
      }
    }
  }, [chartData, getVisibleTimeRange]);

  // Calculate optimal number of ticks based on chart width
  // Aim for one tick every 80-120 pixels for good readability
  const calculateOptimalTicks = useCallback((chartWidth: number) => {
    const minTickSpacing = 80; // Minimum pixels between ticks
    const maxTicks = Math.floor(chartWidth / minTickSpacing);

    // Round to nice numbers: 3, 6, 9, 12, 15, 18, 21, 24, etc.
    const niceNumbers = [3, 6, 9, 12, 15, 18, 21, 24, 30];

    // Find the largest nice number that doesn't exceed maxTicks
    for (let i = niceNumbers.length - 1; i >= 0; i--) {
      if (niceNumbers[i] <= maxTicks) {
        return niceNumbers[i];
      }
    }

    // Fallback to maxTicks if it's smaller than our smallest nice number
    return Math.max(3, maxTicks);
  }, []);

  // Calculate ticks based on current width
  const optimalTicks = useMemo(() => {
    return calculateOptimalTicks(width);
  }, [width, calculateOptimalTicks]);

  const getTimezoneDayKey = useCallback(
    (date: Date) => {
      // A stable day identifier in the configured timezone.
      if (timezone && timezone !== 'UTC') {
        try {
          return formatInTimeZone(date, timezone, 'yyyy-MM-dd');
        } catch (err) {
          console.warn('Invalid timezone; falling back to UTC:', timezone, err);
        }
      }
      return timeFormat('%Y-%m-%d')(date);
    },
    [timezone]
  );

  const formatDateUnderTick = useCallback(
    (tickValue: number) => {
      const idx = Math.round(Number(tickValue));
      const d = chartData?.[idx];
      if (!d?.date) return '';

      if (timezone && timezone !== 'UTC') {
        try {
          return formatInTimeZone(d.date, timezone, 'MMM d');
        } catch (err) {
          console.warn('Invalid timezone; falling back to UTC:', timezone, err);
        }
      }
      return timeFormat('%b %-d')(d.date);
    },
    [chartData, timezone]
  );

  const dateTickValues = useMemo(() => {
    if (!chartData || chartData.length === 0) return undefined;

    const dayStartIndices: number[] = [];
    let lastDayKey: string | null = null;

    for (let i = 0; i < chartData.length; i++) {
      const d = chartData[i];
      const key = getTimezoneDayKey(d.date);
      if (key !== lastDayKey) {
        dayStartIndices.push(i);
        lastDayKey = key;
      }
    }

    if (dayStartIndices.length <= 2) return dayStartIndices;

    // Sample day labels so they don't overlap on long ranges.
    const maxLabels = Math.max(2, Math.floor(width / 140));
    if (dayStartIndices.length <= maxLabels) return dayStartIndices;

    const sampled: number[] = [];
    for (let j = 0; j < maxLabels; j++) {
      const idx = Math.round(
        (j * (dayStartIndices.length - 1)) / (maxLabels - 1)
      );
      sampled.push(dayStartIndices[idx]);
    }
    return Array.from(new Set(sampled));
  }, [chartData, getTimezoneDayKey, width]);

  // We need to look up the actual date from the data array
  const formatTime = useCallback(
    (index: number) => {
      try {
        // Get the actual data point from the index
        const dataPoint = chartData?.[index];
        if (!dataPoint || !dataPoint.date) {
          return '';
        }

        const date = dataPoint.date;

        // Validate date
        if (!(date instanceof Date) || isNaN(date.getTime())) {
          console.error('Invalid date at index', index, ':', date);
          return '';
        }

        // Get optimal format
        const format = getOptimalFormat();

        // Check if this is intraday data
        const visibleRange = getVisibleTimeRange();
        const dataPointCount = chartData.length;
        const avgInterval =
          dataPointCount > 1
            ? visibleRange / (dataPointCount - 1)
            : visibleRange;
        const oneDay = 24 * 60 * 60 * 1000;
        const isIntradayData = avgInterval < oneDay;

        // For intraday data, keep axis ticks as *time only*.
        // If we want to show a date label once per day, we draw it separately on the axis canvas
        // (see "Custom X-axis tick labels" below).
        if (isIntradayData && visibleRange > oneDay) {
          if (timezone && timezone !== 'UTC') {
            try {
              return formatInTimeZone(date, timezone, 'HH:mm');
            } catch (err) {
              console.warn(
                'Invalid timezone; falling back to UTC:',
                timezone,
                err
              );
            }
          }
          return timeFormat('%H:%M')(date);
        }

        // For daily+ data or single-day view, use the standard format
        if (timezone && timezone !== 'UTC') {
          try {
            return formatInTimeZone(date, timezone, format);
          } catch (err) {
            console.warn(
              'Invalid timezone; falling back to UTC:',
              timezone,
              err
            );
          }
        }

        // Convert format to d3-time-format syntax
        const d3Format = format
          .replace('yyyy', '%Y')
          .replace('MMM', '%b')
          .replace('MM', '%m')
          .replace('dd', '%d')
          .replace('HH', '%H')
          .replace('mm', '%M');

        return timeFormat(d3Format)(date);
      } catch (err) {
        console.error('Error formatting time at index', index, ':', err);
        return '';
      }
    },
    [timezone, chartData, getOptimalFormat, getVisibleTimeRange]
  );

  // Validate date range
  const dateRangeError = useMemo(() => {
    if (initialVisibleRange) {
      const { from, to } = initialVisibleRange;

      // Check if dates are valid
      if (!(from instanceof Date) || isNaN(from.getTime())) {
        return 'Invalid start date in visible range';
      }
      if (!(to instanceof Date) || isNaN(to.getTime())) {
        return 'Invalid end date in visible range';
      }

      // Check if date range is valid (from < to)
      if (from >= to) {
        return 'Invalid date range: start date must be before end date';
      }
    }
    return null;
  }, [initialVisibleRange]);

  // Show loading indicator
  if (loading) {
    return (
      <Box
        ref={containerRef}
        sx={{
          width: '100%',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: height,
          border: '1px solid #e0e0e0',
          borderRadius: 1,
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  // Show error message
  if (error || dateRangeError) {
    return (
      <Box ref={containerRef} sx={{ width: '100%', p: 2 }}>
        <Alert severity="error">{error || dateRangeError}</Alert>
      </Box>
    );
  }

  // Guard against empty data
  if (!chartData || chartData.length === 0) {
    return (
      <Box ref={containerRef} sx={{ width: '100%', p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary">
          No data available for this period
        </Typography>
      </Box>
    );
  }

  // Wait for width measurement if no fixed width provided
  if (!width || width === 0) {
    return (
      <Box
        ref={containerRef}
        sx={{
          width: '100%',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: height,
          border: '1px solid #e0e0e0',
          borderRadius: 1,
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  // Get marker path based on shape
  const getMarkerPath = (shape?: string) => {
    switch (shape) {
      case 'triangleUp':
        return buyPath;
      case 'triangleDown':
        return sellPath;
      case 'circle':
        return circlePath;
      case 'doubleCircle':
        return doubleCirclePath;
      default:
        return buyPath;
    }
  };

  // Tolerance for matching a marker timestamp to a candle timestamp.
  // Many event sources emit timestamps that fall within the candle, not exactly on its boundary.
  // NOTE: Keep this as a non-hook calculation because this component has early returns
  // (loading/error/empty/width=0) and adding hooks below them can break hook ordering.
  const markerMatchToleranceMs = (() => {
    if (!chartData || chartData.length < 2) return 0;
    const a = chartData[0]?.date?.getTime();
    const b = chartData[1]?.date?.getTime();
    if (!a || !b) return 0;
    const interval = Math.abs(b - a);
    if (!interval || isNaN(interval)) return 0;
    return Math.max(1, Math.floor(interval / 2));
  })();

  // Render chart with error boundary
  const renderChart = () => {
    try {
      return (
        <Box
          sx={{
            border: '1px solid #e0e0e0',
            borderRadius: 1,
            overflow: 'visible',
            width: '100%',
            maxWidth: '100%',
            '& .react-financial-charts': {
              maxWidth: '100%',
              overflow: 'visible',
            },
            '& canvas': {
              maxWidth: '100%',
            },
          }}
          key={resetKey}
        >
          <ChartCanvas
            height={height}
            width={width}
            ratio={1}
            margin={margin}
            data={chartData}
            xScale={xScale}
            xAccessor={xAccessor}
            displayXAccessor={displayXAccessor}
            xExtents={initialXExtents}
            seriesName="OHLC"
          >
            <Chart id={1} yExtents={(d: OHLCData) => [d.high, d.low]}>
              {/* Axes with grid lines */}
              <XAxis
                tickStrokeStyle="#666"
                showGridLines={showGrid}
                gridLinesStrokeStyle="#e0e0e0"
                tickFormat={formatTime}
                ticks={optimalTicks}
              />

              {/* Date line under time ticks */}
              <XAxis
                showGridLines={false}
                showDomain={false}
                tickFormat={formatDateUnderTick}
                tickValues={dateTickValues}
                showTicks={true}
                innerTickSize={0}
                outerTickSize={0}
                tickStrokeStyle="transparent"
                tickLabelFill="#666"
                fontSize={11}
                tickPadding={24}
              />
              <YAxis
                ticks={10}
                tickStrokeStyle="#666"
                showGridLines={showGrid}
                gridLinesStrokeStyle="#e0e0e0"
              />

              {/* Right Y-axis for latest price */}
              {latestPrice !== null && (
                <YAxis
                  axisAt="right"
                  orient="right"
                  ticks={0}
                  tickStrokeStyle="transparent"
                  showGridLines={false}
                />
              )}

              {/* Data gap shading overlay */}
              {dataGaps.length > 0 && (
                <GenericChartComponent
                  drawOn={['draw', 'pan', 'mousemove', 'zoom']}
                  canvasToDraw={getAxisCanvas}
                  canvasDraw={(
                    ctx: CanvasRenderingContext2D,
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    moreProps: any
                  ) => {
                    const {
                      xScale,
                      chartConfig,
                      xAccessor: morePropsXAccessor,
                      plotData,
                    } = moreProps;
                    const yScale = chartConfig.yScale;
                    const yRange = yScale.range();
                    const yMin = Math.min(...yRange);
                    const yMax = Math.max(...yRange);
                    const height = yMax - yMin;

                    dataGaps.forEach((gap) => {
                      let x1, x2;

                      // Handle different gap types with appropriate positioning
                      if (gap.type === 'start') {
                        // Gap before first candle: from left edge to first candle
                        const firstDataPoint = plotData[0];
                        x1 = xScale.range()[0]; // Left edge of chart
                        x2 = xScale(morePropsXAccessor(firstDataPoint));
                      } else if (gap.type === 'end') {
                        // Gap after last candle: from last candle to right edge
                        const lastDataPoint = plotData[plotData.length - 1];
                        x1 = xScale(morePropsXAccessor(lastDataPoint));
                        x2 = xScale.range()[1]; // Right edge of chart
                      } else {
                        // Middle gap: between two candles
                        // Find the candles before and after the gap
                        const startIndex = plotData.findIndex(
                          (d: OHLCData) => d.date >= gap.start
                        );
                        const endIndex = plotData.findIndex(
                          (d: OHLCData) => d.date >= gap.end
                        );

                        if (startIndex === -1 || endIndex === -1) {
                          return;
                        }

                        // Position from the candle before the gap to the candle after
                        x1 = xScale(
                          morePropsXAccessor(
                            plotData[startIndex === 0 ? 0 : startIndex - 1]
                          )
                        );
                        x2 = xScale(morePropsXAccessor(plotData[endIndex]));
                      }

                      // Skip if coordinates are invalid
                      if (
                        isNaN(x1) ||
                        isNaN(x2) ||
                        x1 === undefined ||
                        x2 === undefined
                      ) {
                        return;
                      }

                      const width = Math.abs(x2 - x1);
                      const x = Math.min(x1, x2);

                      // Skip if width is too small to render meaningfully (less than 5 pixels)
                      if (width < 5) {
                        return;
                      }

                      // Draw semi-transparent orange rectangle
                      ctx.fillStyle = 'rgba(255, 152, 0, 0.2)';
                      ctx.fillRect(x, yMin, width, height);

                      // Draw dashed border
                      ctx.strokeStyle = '#ff9800';
                      ctx.lineWidth = 2;
                      ctx.setLineDash([8, 4]);
                      ctx.strokeRect(x, yMin, width, height);
                      ctx.setLineDash([]);

                      // Draw diagonal stripes (only if gap is wide enough)
                      if (width > 20) {
                        ctx.save();
                        ctx.strokeStyle = 'rgba(255, 152, 0, 0.4)';
                        ctx.lineWidth = 2;
                        const stripeSpacing = 15;

                        // Clip to the gap rectangle to prevent stripes from extending beyond
                        ctx.beginPath();
                        ctx.rect(x, yMin, width, height);
                        ctx.clip();

                        // Draw diagonal stripes from top-left to bottom-right
                        for (
                          let offset = -height;
                          offset < width + height;
                          offset += stripeSpacing
                        ) {
                          ctx.beginPath();
                          ctx.moveTo(x + offset, yMin);
                          ctx.lineTo(x + offset + height, yMin + height);
                          ctx.stroke();
                        }

                        ctx.restore();
                      }

                      // Draw warning triangle
                      const centerX = x + width / 2;
                      const centerY = yMin + 30;

                      ctx.fillStyle = '#ff9800';
                      ctx.strokeStyle = '#e65100';
                      ctx.lineWidth = 1.5;
                      ctx.beginPath();
                      ctx.moveTo(centerX - 12, centerY - 8);
                      ctx.lineTo(centerX, centerY - 20);
                      ctx.lineTo(centerX + 12, centerY - 8);
                      ctx.closePath();
                      ctx.fill();
                      ctx.stroke();

                      // Draw exclamation mark
                      ctx.fillStyle = 'white';
                      ctx.font = 'bold 12px sans-serif';
                      ctx.textAlign = 'center';
                      ctx.textBaseline = 'middle';
                      ctx.fillText('!', centerX, centerY - 14);

                      // Draw "Missing Data" text
                      ctx.fillStyle = '#e65100';
                      ctx.font = 'bold 12px sans-serif';
                      ctx.fillText('Missing Data', centerX, centerY + 8);

                      // Draw gap type
                      ctx.fillStyle = '#666';
                      ctx.font = '10px sans-serif';
                      const typeText =
                        gap.type === 'start'
                          ? '(Before Start)'
                          : gap.type === 'end'
                            ? '(After End)'
                            : '(Data Gap)';
                      ctx.fillText(typeText, centerX, centerY + 22);
                    });
                  }}
                />
              )}

              {/* Candlestick series */}
              <CandlestickSeries />

              {/* OHLC Tooltip with enhanced information */}
              {showOHLCTooltip && (
                <>
                  <OHLCTooltip
                    origin={[0, 0]}
                    textFill={(d: OHLCData) =>
                      d.close > d.open ? '#26a69a' : '#ef5350'
                    }
                    labelFill="#666"
                    fontSize={12}
                    ohlcFormat={(n: number | { valueOf(): number }) => {
                      const value = typeof n === 'number' ? n : n.valueOf();
                      return value.toFixed(5);
                    }}
                    displayTexts={{
                      o: 'O: ',
                      h: 'H: ',
                      l: 'L: ',
                      c: 'C: ',
                      na: 'N/A',
                    }}
                  />
                  <GenericChartComponent
                    drawOn={['mousemove', 'pan']}
                    canvasDraw={(
                      ctx: CanvasRenderingContext2D,
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      moreProps: any
                    ) => {
                      const { currentItem } = moreProps;
                      if (!currentItem) return;

                      const candle = currentItem as OHLCData;

                      // Format timestamp
                      let timestamp: string;
                      if (timezone && timezone !== 'UTC') {
                        try {
                          timestamp = formatInTimeZone(
                            candle.date,
                            timezone,
                            'yyyy-MM-dd HH:mm:ss'
                          );
                        } catch (err) {
                          console.warn(
                            'Invalid timezone; falling back to UTC:',
                            timezone,
                            err
                          );
                          timestamp = candle.date.toLocaleString('en-US', {
                            timeZone: 'UTC',
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit',
                          });
                        }
                      } else {
                        timestamp = candle.date.toLocaleString('en-US', {
                          timeZone: 'UTC',
                          year: 'numeric',
                          month: '2-digit',
                          day: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        });
                      }

                      // Draw timestamp above OHLC values
                      ctx.fillStyle = '#666';
                      ctx.font = '12px sans-serif';
                      ctx.textAlign = 'left';
                      ctx.textBaseline = 'top';
                      ctx.fillText(timestamp, 5, 5);
                    }}
                  />
                </>
              )}

              {/* Mouse coordinates */}
              <MouseCoordinateX displayFormat={formatTime} />
              <MouseCoordinateY displayFormat={(d: number) => d.toFixed(5)} />

              {/* Crosshair cursor */}
              {showCrosshair && <CrossHairCursor />}

              {/* Vertical lines */}
              {verticalLines.map((line, idx) => (
                <Annotate
                  key={`vline-${idx}`}
                  with={SvgPathAnnotation}
                  when={(d: OHLCData) =>
                    d.date.getTime() === line.date.getTime()
                  }
                  usingProps={{
                    path: () =>
                      `M 0 0 L 0 ${height - margin.top - margin.bottom}`,
                    stroke: line.color,
                    strokeWidth: line.strokeWidth || 2,
                    strokeDasharray: line.strokeDasharray,
                  }}
                />
              ))}

              {/* Horizontal lines */}
              {horizontalLines.map((line, idx) => (
                <Annotate
                  key={`hline-${idx}`}
                  with={SvgPathAnnotation}
                  when={() => true}
                  usingProps={{
                    path: () =>
                      `M 0 0 L ${width - margin.left - margin.right} 0`,
                    stroke: line.color,
                    strokeWidth: line.strokeWidth || 1,
                    strokeDasharray: line.strokeDasharray || '5,5',
                    y: ({ yScale }: { yScale: (price: number) => number }) => {
                      const yPos = yScale(line.price);
                      return isNaN(yPos) ? 0 : yPos;
                    },
                  }}
                />
              ))}

              {/* Custom markers with enhanced tooltips */}
              {visibleMarkers.map((marker, idx) => {
                const markerPath = getMarkerPath(marker.shape);
                const isStartEnd =
                  marker.type === 'start_strategy' ||
                  marker.type === 'end_strategy';

                const matchesCandle = (d: OHLCData) => {
                  const dt = d.date?.getTime();
                  const mt = marker.date?.getTime();
                  if (!dt || !mt) return false;
                  if (!markerMatchToleranceMs) return dt === mt;
                  return Math.abs(dt - mt) <= markerMatchToleranceMs;
                };

                return (
                  <React.Fragment key={`marker-group-${marker.id || idx}`}>
                    {/* Marker shape with hover effect */}
                    <Annotate
                      with={SvgPathAnnotation}
                      when={matchesCandle}
                      usingProps={{
                        path: markerPath,
                        pathWidth: isStartEnd ? 10 : 20,
                        pathHeight: 10,
                        fill: marker.color,
                        stroke: isStartEnd ? marker.color : '#000',
                        strokeWidth: isStartEnd ? 1 : 0.5,
                        opacity: 0.9,
                        y: ({
                          yScale,
                          datum,
                        }: {
                          yScale: (price: number) => number;
                          datum: OHLCData;
                        }) => {
                          // For start/end markers, position at candle high
                          let targetPrice = marker.price;
                          if (isStartEnd && datum) {
                            targetPrice = datum.high;
                          }

                          // NaN validation for marker positioning
                          const yPos = yScale(targetPrice);
                          return isNaN(yPos) ? 0 : yPos;
                        },
                        tooltip: marker.tooltip,
                        onClick: onMarkerClick
                          ? () => onMarkerClick(marker)
                          : undefined,
                        style: {
                          cursor: onMarkerClick ? 'pointer' : 'default',
                        },
                      }}
                    />
                    {/* Marker label */}
                    {marker.label && (
                      <Annotate
                        with={LabelAnnotation}
                        when={matchesCandle}
                        usingProps={{
                          text: marker.label,
                          y: ({
                            yScale,
                            datum,
                          }: {
                            yScale: (price: number) => number;
                            datum: OHLCData;
                          }) => {
                            // For start/end markers, position at candle high
                            let targetPrice = marker.price;
                            if (isStartEnd && datum) {
                              targetPrice = datum.high;
                            }

                            // NaN validation
                            const yPos = yScale(targetPrice);
                            if (isNaN(yPos)) return 0;

                            // Position label based on marker type
                            if (marker.type === 'buy') {
                              return yPos + 15; // Below buy marker
                            } else if (marker.type === 'sell') {
                              return yPos - 15; // Above sell marker
                            } else {
                              return yPos - 18; // Above start/end marker
                            }
                          },
                          fill: '#000000',
                          fontSize: 10,
                          fontWeight: 'bold',
                        }}
                      />
                    )}
                  </React.Fragment>
                );
              })}
            </Chart>
          </ChartCanvas>
        </Box>
      );
    } catch (err) {
      console.error('Chart rendering error:', err);
      const errorMessage =
        err instanceof Error ? err.message : 'Unknown error occurred';
      return (
        <Box sx={{ p: 2 }}>
          <Alert severity="error">
            <Typography variant="body2" fontWeight="bold">
              Chart Rendering Error
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              {errorMessage}
            </Typography>
            <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>
              Please try refreshing the page or contact support if the problem
              persists.
            </Typography>
          </Alert>
        </Box>
      );
    }
  };

  return (
    <Box
      ref={containerRef}
      sx={{
        width: '100%',
        maxWidth: '100%',
        overflow: 'visible',
        boxSizing: 'border-box',
      }}
    >
      {/* Data gaps info banner */}
      {showDataGaps && dataGaps.length > 0 && (
        <Alert
          severity="warning"
          sx={{
            mb: 2,
            backgroundColor: 'rgba(255, 152, 0, 0.1)',
            border: '1px solid #ff9800',
            '& .MuiAlert-icon': {
              color: '#ff9800',
            },
          }}
        >
          <Typography variant="body2" fontWeight="bold" sx={{ mb: 0.5 }}>
            {dataGaps.length} Data Gap{dataGaps.length > 1 ? 's' : ''} Detected
          </Typography>
          <Typography variant="caption" sx={{ display: 'block' }}>
            Orange striped areas indicate periods where no market data is
            available from OANDA. This may occur during weekends, holidays, or
            market closures.
          </Typography>
        </Alert>
      )}

      {/* Control buttons */}
      {(showResetButton || enableMarkerToggle) && (
        <Box sx={{ mb: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          {showResetButton && (
            <Button variant="outlined" size="small" onClick={handleResetView}>
              Reset View
            </Button>
          )}
          {enableMarkerToggle && markers.length > 0 && (
            <ButtonGroup size="small" variant="outlined">
              <Button
                variant={showBuySellMarkers ? 'contained' : 'outlined'}
                onClick={() => setShowBuySellMarkers(!showBuySellMarkers)}
              >
                Buy/Sell Markers
              </Button>
              <Button
                variant={showStartEndMarkers ? 'contained' : 'outlined'}
                onClick={() => setShowStartEndMarkers(!showStartEndMarkers)}
              >
                Start/End Markers
              </Button>
            </ButtonGroup>
          )}
        </Box>
      )}

      {/* Chart */}
      {renderChart()}
    </Box>
  );
};

export default FinancialChart;
