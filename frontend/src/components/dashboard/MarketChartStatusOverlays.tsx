import { Box, Chip, CircularProgress, LinearProgress } from '@mui/material';

interface MarketChartStatusOverlaysProps {
  loadingOlder: boolean;
  loadingNewer: boolean;
  isRefreshing: boolean;
  error: string | null;
  isInitialLoading: boolean;
  isDark: boolean;
}

export function MarketChartStatusOverlays({
  loadingOlder,
  loadingNewer,
  isRefreshing,
  error,
  isInitialLoading,
  isDark,
}: MarketChartStatusOverlaysProps) {
  return (
    <>
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
            sx={{ flex: 1, visibility: loadingOlder ? 'visible' : 'hidden' }}
          >
            <LinearProgress color="inherit" />
          </Box>
          <Box
            sx={{ flex: 1, visibility: loadingNewer ? 'visible' : 'hidden' }}
          >
            <LinearProgress color="inherit" />
          </Box>
        </Box>
      )}

      {(isRefreshing || error) && (
        <Box
          sx={{
            position: 'absolute',
            top: 8,
            right: 8,
            zIndex: 3,
            display: 'flex',
            gap: 1,
          }}
        >
          {isRefreshing && <Chip size="small" label="Syncing candles" />}
          {error && <Chip size="small" color="error" label={error} />}
        </Box>
      )}

      {isInitialLoading && (
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1,
            backgroundColor: isDark
              ? 'rgba(19,23,34,0.7)'
              : 'rgba(255,255,255,0.7)',
          }}
        >
          <CircularProgress size={32} />
        </Box>
      )}
    </>
  );
}
