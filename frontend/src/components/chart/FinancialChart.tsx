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

import React, {
  useState,
  useMemo,
  useCallback,
  useEffect,
  useRef,
} from 'react';
import { Chart, ChartCanvas } from 'react-financial-charts';
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
import { buyPath, sellPath, doubleCirclePath } from '../../utils/chartMarkers';
import { CHART_CONFIG } from '../../config/chartConfig';
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
  onVisibleRangeChange?: (range: { from: Date; to: Date }) => void;
  onLoadMore?: (direction: 'older' | 'newer') => void;
  onMarkerClick?: (marker: ChartMarker) => void;
  onResetView?: () => void;

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
  onVisibleRangeChange,
  onLoadMore,
  onMarkerClick,
  onResetView,
  initialVisibleRange,
  enablePan = true, // Note: Pan is always enabled in react-financial-charts
  enableZoom = true, // Note: Zoom is always enabled in react-financial-charts
  showGrid = true,
  showCrosshair = true,
  showOHLCTooltip = true,
  showResetButton = true,
  enableMarkerToggle = true,
  timezone = 'UTC',
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
  // Note: Visible range tracking is reserved for future implementation
  // react-financial-charts doesn't provide direct callbacks for range changes
  const [currentVisibleRange, setCurrentVisibleRange] = useState<{
    from: Date;
    to: Date;
  } | null>(null);

  // Suppress unused variable warnings - these are part of the public API
  // and will be used when visible range tracking is implemented
  void enablePan;
  void enableZoom;
  void setCurrentVisibleRange;

  // Ref to track if we've already triggered load more
  const loadMoreTriggeredRef = useRef<{ older: boolean; newer: boolean }>({
    older: false,
    newer: false,
  });

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

  const margin = { left: 50, right: 50, top: 10, bottom: 30 };

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
    loadMoreTriggeredRef.current = { older: false, newer: false };
    onResetView?.();
  }, [onResetView]);

  // Monitor visible range changes and trigger load more callbacks
  useEffect(() => {
    if (
      !currentVisibleRange ||
      !onLoadMore ||
      !chartData ||
      chartData.length === 0
    ) {
      return;
    }

    const threshold = CHART_CONFIG.SCROLL_LOAD_THRESHOLD;
    const firstDataDate = chartData[0].date;
    const lastDataDate = chartData[chartData.length - 1].date;

    // Calculate time difference for threshold
    const totalDuration = lastDataDate.getTime() - firstDataDate.getTime();
    const thresholdDuration = (totalDuration / chartData.length) * threshold;

    // Check if we're near the left edge (older data)
    const nearLeftEdge =
      currentVisibleRange.from.getTime() - firstDataDate.getTime() <
      thresholdDuration;

    // Check if we're near the right edge (newer data)
    const nearRightEdge =
      lastDataDate.getTime() - currentVisibleRange.to.getTime() <
      thresholdDuration;

    if (nearLeftEdge && !loadMoreTriggeredRef.current.older) {
      loadMoreTriggeredRef.current.older = true;
      onLoadMore('older');
    } else if (!nearLeftEdge) {
      loadMoreTriggeredRef.current.older = false;
    }

    if (nearRightEdge && !loadMoreTriggeredRef.current.newer) {
      loadMoreTriggeredRef.current.newer = true;
      onLoadMore('newer');
    } else if (!nearRightEdge) {
      loadMoreTriggeredRef.current.newer = false;
    }
  }, [currentVisibleRange, onLoadMore, chartData]);

  // Notify parent of visible range changes
  useEffect(() => {
    if (currentVisibleRange && onVisibleRangeChange) {
      onVisibleRangeChange(currentVisibleRange);
    }
  }, [currentVisibleRange, onVisibleRangeChange]);

  // Filter markers based on visibility toggles
  const visibleMarkers = useMemo(() => {
    return markers.filter((marker) => {
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
  }, [markers, showBuySellMarkers, showStartEndMarkers]);

  // Format time for axis based on timezone
  // Note: react-financial-charts passes the index to tickFormat, not the date
  // Calculate visible time range in milliseconds
  const getVisibleTimeRange = useCallback(() => {
    if (!chartData || chartData.length < 2) return 0;

    // Get first and last visible dates
    const firstDate = chartData[0]?.date;
    const lastDate = chartData[chartData.length - 1]?.date;

    if (!firstDate || !lastDate) return 0;

    return lastDate.getTime() - firstDate.getTime();
  }, [chartData]);

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

        // Calculate visible time range
        const visibleRange = getVisibleTimeRange();
        const oneHour = 60 * 60 * 1000;
        const oneDay = 24 * oneHour;
        const oneWeek = 7 * oneDay;
        const oneMonth = 30 * oneDay;

        // Choose format based on visible time range
        let format: string;

        if (visibleRange <= oneDay) {
          // Less than 1 day: show time only (HH:mm)
          format = 'HH:mm';
        } else if (visibleRange <= oneWeek) {
          // 1 day to 1 week: show date and time (MMM dd HH:mm)
          format = 'MMM dd HH:mm';
        } else if (visibleRange <= oneMonth) {
          // 1 week to 1 month: show date with abbreviated month (MMM dd)
          format = 'MMM dd';
        } else {
          // More than 1 month: show date with year (yyyy-MM-dd)
          format = 'yyyy-MM-dd';
        }

        if (timezone && timezone !== 'UTC') {
          return formatInTimeZone(date, timezone, format);
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
    [timezone, chartData, getVisibleTimeRange]
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
      case 'doubleCircle':
        return doubleCirclePath;
      default:
        return buyPath;
    }
  };

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
              />
              <YAxis
                ticks={10}
                tickStrokeStyle="#666"
                showGridLines={showGrid}
                gridLinesStrokeStyle="#e0e0e0"
              />

              {/* Candlestick series */}
              <CandlestickSeries />

              {/* OHLC Tooltip */}
              {showOHLCTooltip && (
                <OHLCTooltip
                  origin={[0, 0]}
                  textFill={(d: OHLCData) =>
                    d.close > d.open ? '#26a69a' : '#ef5350'
                  }
                  labelFill="#666"
                  fontSize={12}
                />
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

              {/* Custom markers */}
              {visibleMarkers.map((marker, idx) => {
                const markerPath = getMarkerPath(marker.shape);
                const isStartEnd =
                  marker.type === 'start_strategy' ||
                  marker.type === 'end_strategy';

                return (
                  <React.Fragment key={`marker-group-${marker.id || idx}`}>
                    {/* Marker shape */}
                    <Annotate
                      with={SvgPathAnnotation}
                      when={(d: OHLCData) =>
                        d.date.getTime() === marker.date.getTime()
                      }
                      usingProps={{
                        path: markerPath,
                        pathWidth: isStartEnd ? 10 : 20,
                        pathHeight: 10,
                        fill: marker.color,
                        stroke: isStartEnd ? marker.color : undefined,
                        strokeWidth: isStartEnd ? 1 : undefined,
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
                      }}
                    />
                    {/* Marker label */}
                    {marker.label && (
                      <Annotate
                        with={LabelAnnotation}
                        when={(d: OHLCData) =>
                          d.date.getTime() === marker.date.getTime()
                        }
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
