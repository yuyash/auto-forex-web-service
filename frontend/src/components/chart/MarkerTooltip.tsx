/**
 * MarkerTooltip Component
 *
 * Custom tooltip component for displaying detailed information about chart markers
 * (buy/sell/start/end events) when hovering over them.
 */

import React from 'react';
import { Box, Paper, Typography } from '@mui/material';
import type { ChartMarker } from '../../utils/chartMarkers';

export interface MarkerTooltipProps {
  marker: ChartMarker | null;
  position: { x: number; y: number } | null;
}

export const MarkerTooltip: React.FC<MarkerTooltipProps> = ({
  marker,
  position,
}) => {
  if (!marker || !position) {
    return null;
  }

  const getMarkerTypeLabel = (type: ChartMarker['type']) => {
    switch (type) {
      case 'buy':
        return 'Buy Order';
      case 'sell':
        return 'Sell Order';
      case 'start_strategy':
        return 'Strategy Start';
      case 'end_strategy':
        return 'Strategy End';
      case 'initial_entry':
        return 'Initial Entry';
      default:
        return 'Event';
    }
  };

  const getMarkerColor = (type: ChartMarker['type']) => {
    switch (type) {
      case 'buy':
        return '#00bcd4';
      case 'sell':
        return '#ff9800';
      case 'start_strategy':
      case 'end_strategy':
        return '#757575';
      default:
        return '#666';
    }
  };

  return (
    <Paper
      sx={{
        position: 'fixed',
        left: position.x + 10,
        top: position.y - 10,
        zIndex: 9999,
        pointerEvents: 'none',
        maxWidth: 300,
        boxShadow: 3,
        border: `2px solid ${getMarkerColor(marker.type)}`,
      }}
    >
      <Box sx={{ p: 1.5 }}>
        <Typography
          variant="subtitle2"
          sx={{
            fontWeight: 'bold',
            color: getMarkerColor(marker.type),
            mb: 0.5,
          }}
        >
          {getMarkerTypeLabel(marker.type)}
        </Typography>

        <Typography variant="caption" component="div" sx={{ mb: 0.5 }}>
          <strong>Time:</strong> {marker.date.toLocaleString()}
        </Typography>

        <Typography variant="caption" component="div" sx={{ mb: 0.5 }}>
          <strong>Price:</strong> {marker.price.toFixed(5)}
        </Typography>

        {marker.tooltip && (
          <Typography
            variant="caption"
            component="div"
            sx={{ mt: 1, color: 'text.secondary' }}
          >
            {marker.tooltip}
          </Typography>
        )}
      </Box>
    </Paper>
  );
};

export default MarkerTooltip;
