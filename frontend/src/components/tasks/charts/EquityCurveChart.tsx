import React from 'react';
import { Box, Typography } from '@mui/material';
import type { EquityPoint } from '../../../types/execution';

interface EquityCurveChartProps {
  data: EquityPoint[];
  height?: number;
}

export const EquityCurveChart: React.FC<EquityCurveChartProps> = ({
  data,
  height = 400,
}) => {
  if (!data || data.length === 0) {
    return (
      <Box
        sx={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Typography color="text.secondary">No equity data available</Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        height,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Typography color="text.secondary">
        Equity curve: {data.length} data points
      </Typography>
    </Box>
  );
};
