/**
 * ChartContainer - Reusable Chart Wrapper Component
 *
 * Provides a consistent wrapper for charts with:
 * - Zoom and pan controls
 * - Granularity selector
 * - Loading and error states
 * - Responsive sizing
 * - MUI X Charts integration
 *
 * Requirements: 11.8, 11.9, 11.17, 11.18, 12.7, 12.8, 12.9
 */

import React, { type ReactNode, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  CircularProgress,
  Alert,
  AlertTitle,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  IconButton,
  Tooltip,
  Stack,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material/Select';
import {
  ZoomIn as ZoomInIcon,
  ZoomOut as ZoomOutIcon,
  ZoomOutMap as ResetZoomIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';

export interface GranularityOption {
  label: string;
  value: number; // Granularity in seconds
}

export interface ChartContainerProps {
  title?: string;
  children: ReactNode;
  isLoading?: boolean;
  error?: Error | null;
  granularity?: number;
  granularityOptions?: GranularityOption[];
  onGranularityChange?: (granularity: number) => void;
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onResetZoom?: () => void;
  onRefresh?: () => void;
  height?: number | string;
  minHeight?: number | string;
  showControls?: boolean;
  showGranularitySelector?: boolean;
  emptyMessage?: string;
  ariaLabel?: string;
}

/**
 * Default granularity options (in seconds)
 */
const DEFAULT_GRANULARITY_OPTIONS: GranularityOption[] = [
  { label: '1 second', value: 1 },
  { label: '5 seconds', value: 5 },
  { label: '10 seconds', value: 10 },
  { label: '30 seconds', value: 30 },
  { label: '1 minute', value: 60 },
  { label: '5 minutes', value: 300 },
  { label: '15 minutes', value: 900 },
  { label: '1 hour', value: 3600 },
  { label: '4 hours', value: 14400 },
  { label: '1 day', value: 86400 },
];

/**
 * ChartContainer Component
 *
 * Reusable wrapper for charts with controls, loading states, and error handling.
 *
 * @param title - Optional chart title
 * @param children - Chart component to render
 * @param isLoading - Loading state
 * @param error - Error object if chart failed to load
 * @param granularity - Current granularity in seconds
 * @param granularityOptions - Available granularity options
 * @param onGranularityChange - Callback when granularity changes
 * @param onZoomIn - Callback for zoom in action
 * @param onZoomOut - Callback for zoom out action
 * @param onResetZoom - Callback for reset zoom action
 * @param onRefresh - Callback for refresh action
 * @param height - Chart height (default: 500)
 * @param minHeight - Minimum chart height (default: 300)
 * @param showControls - Show zoom/pan controls (default: true)
 * @param showGranularitySelector - Show granularity selector (default: true)
 * @param emptyMessage - Message to show when no data
 * @param ariaLabel - Accessibility label for the chart
 *
 * @example
 * ```tsx
 * <ChartContainer
 *   title="Equity Curve"
 *   granularity={60}
 *   onGranularityChange={setGranularity}
 *   isLoading={isLoading}
 *   error={error}
 * >
 *   <EquityOHLCChart data={data} />
 * </ChartContainer>
 * ```
 */
export const ChartContainer: React.FC<ChartContainerProps> = ({
  title,
  children,
  isLoading = false,
  error = null,
  granularity,
  granularityOptions = DEFAULT_GRANULARITY_OPTIONS,
  onGranularityChange,
  onZoomIn,
  onZoomOut,
  onResetZoom,
  onRefresh,
  height = 500,
  minHeight = 300,
  showControls = true,
  showGranularitySelector = true,
  emptyMessage = 'No data available',
  ariaLabel,
}) => {
  const [localGranularity, setLocalGranularity] = useState<number>(
    granularity ?? granularityOptions[4]?.value ?? 60
  );

  const handleGranularityChange = (event: SelectChangeEvent<number>) => {
    const newGranularity = Number(event.target.value);
    setLocalGranularity(newGranularity);
    onGranularityChange?.(newGranularity);
  };

  const currentGranularity = granularity ?? localGranularity;

  return (
    <Paper
      elevation={2}
      sx={{
        p: 2,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
      role="region"
      aria-label={ariaLabel || title || 'Chart'}
    >
      {/* Header with title and controls */}
      {(title || showControls || showGranularitySelector) && (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 2,
            flexWrap: 'wrap',
            gap: 2,
          }}
        >
          {/* Title */}
          {title && (
            <Typography variant="h6" component="h2">
              {title}
            </Typography>
          )}

          {/* Controls */}
          <Stack direction="row" spacing={1} alignItems="center">
            {/* Granularity Selector */}
            {showGranularitySelector && onGranularityChange && (
              <FormControl size="small" sx={{ minWidth: 150 }}>
                <InputLabel id="granularity-select-label">
                  Granularity
                </InputLabel>
                <Select
                  labelId="granularity-select-label"
                  id="granularity-select"
                  value={currentGranularity}
                  label="Granularity"
                  onChange={handleGranularityChange}
                  aria-label="Select chart granularity"
                >
                  {granularityOptions.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}

            {/* Zoom Controls */}
            {showControls && (
              <>
                {onZoomIn && (
                  <Tooltip title="Zoom In">
                    <IconButton
                      onClick={onZoomIn}
                      size="small"
                      aria-label="Zoom in"
                    >
                      <ZoomInIcon />
                    </IconButton>
                  </Tooltip>
                )}
                {onZoomOut && (
                  <Tooltip title="Zoom Out">
                    <IconButton
                      onClick={onZoomOut}
                      size="small"
                      aria-label="Zoom out"
                    >
                      <ZoomOutIcon />
                    </IconButton>
                  </Tooltip>
                )}
                {onResetZoom && (
                  <Tooltip title="Reset Zoom">
                    <IconButton
                      onClick={onResetZoom}
                      size="small"
                      aria-label="Reset zoom"
                    >
                      <ResetZoomIcon />
                    </IconButton>
                  </Tooltip>
                )}
                {onRefresh && (
                  <Tooltip title="Refresh">
                    <IconButton
                      onClick={onRefresh}
                      size="small"
                      aria-label="Refresh chart"
                      disabled={isLoading}
                    >
                      <RefreshIcon />
                    </IconButton>
                  </Tooltip>
                )}
              </>
            )}
          </Stack>
        </Box>
      )}

      {/* Chart Content */}
      <Box
        sx={{
          flex: 1,
          minHeight,
          height,
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {/* Loading State */}
        {isLoading && (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 2,
            }}
          >
            <CircularProgress />
            <Typography variant="body2" color="text.secondary">
              Loading chart data...
            </Typography>
          </Box>
        )}

        {/* Error State */}
        {!isLoading && error && (
          <Alert severity="error" sx={{ width: '100%' }}>
            <AlertTitle>Error Loading Chart</AlertTitle>
            {error.message || 'Failed to load chart data. Please try again.'}
          </Alert>
        )}

        {/* Empty State */}
        {!isLoading && !error && !children && (
          <Typography variant="body2" color="text.secondary">
            {emptyMessage}
          </Typography>
        )}

        {/* Chart */}
        {!isLoading && !error && children && (
          <Box sx={{ width: '100%', height: '100%' }}>{children}</Box>
        )}
      </Box>
    </Paper>
  );
};

export default ChartContainer;
