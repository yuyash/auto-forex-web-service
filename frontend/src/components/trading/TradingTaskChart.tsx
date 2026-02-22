/**
 * TradingTaskChart - Stub component for price chart with trade markers
 */

import React from 'react';
import { Box, Typography } from '@mui/material';
import type { Trade } from '../../types/execution';

interface TradingTaskChartProps {
  instrument: string;
  startDate?: string;
  stopDate?: string;
  trades: Trade[];
  strategyLayers?: unknown[];
  height?: number;
  timezone?: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
  onTradeClick?: (tradeIndex: number) => void;
}

export const TradingTaskChart: React.FC<TradingTaskChartProps> = ({
  instrument,
  height = 400,
}) => {
  return (
    <Box
      sx={{
        height,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        border: '1px dashed',
        borderColor: 'divider',
        borderRadius: 1,
      }}
    >
      <Typography variant="body2" color="text.secondary">
        Price chart for {instrument} (coming soon)
      </Typography>
    </Box>
  );
};

export default TradingTaskChart;
