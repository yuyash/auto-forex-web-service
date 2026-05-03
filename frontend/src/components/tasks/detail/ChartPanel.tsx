import { Box, Paper, Typography } from '@mui/material';
import type { ReactNode } from 'react';

interface ChartPanelProps {
  title: string;
  valueLabel?: string;
  height: number;
  headerPrefix?: ReactNode;
  children: ReactNode;
}

export function ChartPanel({
  title,
  valueLabel,
  height,
  headerPrefix,
  children,
}: ChartPanelProps) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: { xs: 0.25, sm: 1 },
        height,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
        width: '100%',
        mx: 'auto',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          mb: 0.25,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {headerPrefix}
          <Typography variant="subtitle2">{title}</Typography>
        </Box>
        {valueLabel ? (
          <Typography variant="body2" color="text.secondary">
            {valueLabel}
          </Typography>
        ) : null}
      </Box>
      {/* position:relative wrapper gives the absolute child a concrete
          reference rectangle, which Safari needs to resolve flex-based
          dimensions for the chart canvas. */}
      <Box
        sx={{
          flex: 1,
          position: 'relative',
          minHeight: 0,
          minWidth: 0,
        }}
      >
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            justifyContent: 'flex-start',
            alignItems: 'stretch',
            '& .MuiCharts-root': {
              width: '100%',
              height: '100%',
            },
            '& [class*="MuiChartsWrapper-root"]': {
              width: '100% !important',
              height: '100% !important',
            },
            '& .MuiChartsSurface-root': {
              width: '100% !important',
              height: '100% !important',
            },
            '& svg': {
              display: 'block',
            },
          }}
        >
          {children}
        </Box>
      </Box>
    </Paper>
  );
}
