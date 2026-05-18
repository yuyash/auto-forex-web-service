import { Box, Paper, Typography } from '@mui/material';
import type { ReactNode } from 'react';

interface ChartPanelProps {
  title: string;
  valueLabel?: string;
  height: number;
  headerPrefix?: ReactNode;
  headerActions?: ReactNode;
  children: ReactNode;
}

export function ChartPanel({
  title,
  valueLabel,
  height,
  headerPrefix,
  headerActions,
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
          alignItems: 'center',
          mb: 0.25,
          gap: 1,
          minWidth: 0,
        }}
      >
        <Box
          sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minWidth: 0 }}
        >
          {headerPrefix}
          <Typography variant="subtitle2" noWrap>
            {title}
          </Typography>
        </Box>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: 0.75,
            flexShrink: 0,
          }}
        >
          {headerActions}
          {valueLabel ? (
            <Typography variant="body2" color="text.secondary" noWrap>
              {valueLabel}
            </Typography>
          ) : null}
        </Box>
      </Box>
      {/* position:relative wrapper gives the absolute child a concrete
          reference rectangle, which Safari needs to resolve flex-based
          dimensions for the chart surface. */}
      <Box
        data-chart-panel-plot="true"
        sx={{
          flex: 1,
          position: 'relative',
          minHeight: 0,
          minWidth: 0,
          width: '100%',
          overflow: 'hidden',
        }}
      >
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            minWidth: 0,
            minHeight: 0,
            display: 'flex',
            justifyContent: 'flex-start',
            alignItems: 'stretch',
            overflow: 'hidden',
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
