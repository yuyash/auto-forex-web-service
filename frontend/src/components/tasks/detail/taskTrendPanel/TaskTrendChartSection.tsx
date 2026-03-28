import React from 'react';
import { Box, CircularProgress, LinearProgress, Paper } from '@mui/material';
import { getTimezoneAbbr } from '../../../../utils/chartTimezone';

interface TaskTrendChartSectionProps {
  chartContainerRef: React.RefObject<HTMLDivElement | null>;
  chartHeight: number;
  minChartHeight: number;
  isDark: boolean;
  timezone: string;
  loadingOlder: boolean;
  loadingNewer: boolean;
  isInitialLoading?: boolean;
}

export function TaskTrendChartSection({
  chartContainerRef,
  chartHeight,
  minChartHeight,
  isDark,
  timezone,
  loadingOlder,
  loadingNewer,
  isInitialLoading = false,
}: TaskTrendChartSectionProps) {
  return (
    <Paper
      variant="outlined"
      sx={{
        mt: 0,
        mb: 0,
        height: chartHeight,
        minHeight: minChartHeight,
        display: 'flex',
        position: 'relative',
      }}
    >
      {isInitialLoading && (
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            zIndex: 4,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: isDark ? 'rgba(19,23,34,0.6)' : 'rgba(255,255,255,0.6)',
          }}
        >
          <CircularProgress />
        </Box>
      )}
      {(loadingOlder || loadingNewer) && (
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 3,
            display: 'flex',
            gap: 1,
            px: 1,
            pt: 0.5,
          }}
        >
          <Box
            sx={{
              flex: 1,
              visibility: loadingOlder ? 'visible' : 'hidden',
            }}
          >
            <LinearProgress color="inherit" />
          </Box>
          <Box
            sx={{
              flex: 1,
              visibility: loadingNewer ? 'visible' : 'hidden',
            }}
          >
            <LinearProgress color="inherit" />
          </Box>
        </Box>
      )}
      <Box ref={chartContainerRef} sx={{ width: '100%', flex: 1 }} />
      <Box
        sx={{
          position: 'absolute',
          bottom: 8,
          right: 8,
          zIndex: 2,
          fontSize: '11px',
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          color: isDark ? 'rgba(255,255,255,0.45)' : 'rgba(51,65,85,0.5)',
          pointerEvents: 'none',
          userSelect: 'none',
        }}
      >
        TZ: {getTimezoneAbbr(timezone)}
      </Box>
    </Paper>
  );
}
