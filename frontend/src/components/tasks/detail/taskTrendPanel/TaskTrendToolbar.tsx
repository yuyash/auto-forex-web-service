import {
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap';
import RefreshIcon from '@mui/icons-material/Refresh';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import ClearIcon from '@mui/icons-material/Clear';
import type { SelectChangeEvent } from '@mui/material/Select';
import { useTranslation } from 'react-i18next';
import type { ReplaySummary } from './shared';

type ActiveCycleFilter = 'off' | 'long' | 'short';

interface TaskTrendToolbarProps {
  replaySummary: ReplaySummary;
  pnlCurrency: string;
  executionRunId?: string;
  isRefreshing: boolean;
  isCandleRefreshing: boolean;
  pollingIntervalMs: number;
  granularity: string;
  granularityOptions: Array<{ value: string; label: string }>;
  pollingIntervalOptions: Array<{ value: number; label: string }>;
  enableRealTimeUpdates: boolean;
  autoFollow: boolean;
  markersVisible: boolean;
  hasSelection: boolean;
  activeCycleFilter: ActiveCycleFilter;
  hasActiveLongCycles: boolean;
  hasActiveShortCycles: boolean;
  onPollingIntervalChange: (value: number) => void;
  onGranularityChange: (event: SelectChangeEvent<string>) => void;
  onToggleMarkers: () => void;
  onActiveCycleFilterChange: (value: ActiveCycleFilter) => void;
  onResetSelection: () => void;
  onFollow: () => void;
  onResetZoom: () => void;
  onReloadCandles: () => void;
}

export function TaskTrendToolbar({
  replaySummary,
  pnlCurrency,
  executionRunId,
  isRefreshing,
  isCandleRefreshing,
  pollingIntervalMs,
  granularity,
  granularityOptions,
  pollingIntervalOptions,
  enableRealTimeUpdates,
  autoFollow,
  markersVisible,
  hasSelection,
  activeCycleFilter,
  hasActiveLongCycles,
  hasActiveShortCycles,
  onPollingIntervalChange,
  onGranularityChange,
  onToggleMarkers,
  onActiveCycleFilterChange,
  onResetSelection,
  onFollow,
  onResetZoom,
  onReloadCandles,
}: TaskTrendToolbarProps) {
  const { t } = useTranslation('common');

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 0.5,
        mb: 1,
      }}
    >
      {/* Row 1: Summary stats + controls */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          height: 48,
          minHeight: 48,
          overflowX: 'auto',
        }}
      >
        <Box sx={{ px: 2, whiteSpace: 'nowrap' }}>
          <Typography variant="caption" color="text.secondary" lineHeight={1.2}>
            {t('tables.trend.realizedPnl')} ({pnlCurrency})
          </Typography>
          <Typography
            variant="body2"
            fontWeight="bold"
            lineHeight={1.4}
            color={
              replaySummary.realizedPnl >= 0 ? 'success.main' : 'error.main'
            }
          >
            {replaySummary.realizedPnl >= 0 ? '+' : ''}
            {replaySummary.realizedPnl.toFixed(2)} {pnlCurrency}
          </Typography>
        </Box>

        <Box sx={{ px: 2, whiteSpace: 'nowrap' }}>
          <Typography variant="caption" color="text.secondary" lineHeight={1.2}>
            {t('tables.trend.unrealizedPnl')} ({pnlCurrency})
          </Typography>
          <Typography
            variant="body2"
            fontWeight="bold"
            lineHeight={1.4}
            color={
              replaySummary.unrealizedPnl >= 0 ? 'success.main' : 'error.main'
            }
          >
            {replaySummary.unrealizedPnl >= 0 ? '+' : ''}
            {replaySummary.unrealizedPnl.toFixed(2)} {pnlCurrency}
          </Typography>
        </Box>

        <Box sx={{ px: 2, whiteSpace: 'nowrap' }}>
          <Typography variant="caption" color="text.secondary" lineHeight={1.2}>
            {t('tables.trend.totalTrades')}
          </Typography>
          <Typography variant="body2" fontWeight="bold" lineHeight={1.4}>
            {replaySummary.totalTrades} trades
          </Typography>
        </Box>

        <Box sx={{ px: 2, whiteSpace: 'nowrap' }}>
          <Typography variant="caption" color="text.secondary" lineHeight={1.2}>
            {t('tables.trend.openPositions')}
          </Typography>
          <Typography variant="body2" fontWeight="bold" lineHeight={1.4}>
            {replaySummary.openPositions} positions
          </Typography>
        </Box>

        {executionRunId != null && (
          <Box sx={{ px: 2, whiteSpace: 'nowrap' }}>
            <Typography
              variant="caption"
              color="text.secondary"
              lineHeight={1.2}
            >
              {t('tables.trend.executionId')}
            </Typography>
            <Typography variant="body2" fontWeight="bold" lineHeight={1.4}>
              {executionRunId}
            </Typography>
          </Box>
        )}

        <Box sx={{ flex: 1 }} />

        <Box
          sx={{
            width: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {(isRefreshing || isCandleRefreshing) && (
            <CircularProgress size={16} thickness={5} />
          )}
        </Box>

        <FormControl
          sx={{ minWidth: 100, '& .MuiInputBase-root': { height: 32 } }}
        >
          <InputLabel
            id="replay-polling-interval-label"
            sx={{ fontSize: '0.75rem' }}
          >
            {t('tables.trend.polling')}
          </InputLabel>
          <Select
            labelId="replay-polling-interval-label"
            value={pollingIntervalMs}
            label={t('tables.trend.polling')}
            onChange={(e) => onPollingIntervalChange(Number(e.target.value))}
            sx={{ fontSize: '0.75rem' }}
          >
            {pollingIntervalOptions.map((opt) => (
              <MenuItem
                key={opt.value}
                value={opt.value}
                sx={{ fontSize: '0.75rem' }}
              >
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl
          sx={{ minWidth: 110, '& .MuiInputBase-root': { height: 32 } }}
        >
          <InputLabel
            id="replay-granularity-label"
            sx={{ fontSize: '0.75rem' }}
          >
            {t('tables.trend.granularity')}
          </InputLabel>
          <Select
            labelId="replay-granularity-label"
            value={granularity}
            label={t('tables.trend.granularity')}
            onChange={onGranularityChange}
            sx={{ fontSize: '0.75rem' }}
          >
            {granularityOptions.map((g) => (
              <MenuItem
                key={g.value}
                value={g.value}
                sx={{ fontSize: '0.75rem' }}
              >
                {g.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {enableRealTimeUpdates && (
          <Button
            variant={autoFollow ? 'contained' : 'outlined'}
            onClick={onFollow}
            disabled={autoFollow}
            sx={{
              fontSize: '0.75rem',
              whiteSpace: 'nowrap',
              minWidth: 0,
              px: 1.5,
              height: 32,
            }}
          >
            {t('tables.trend.follow')}
          </Button>
        )}

        <Tooltip title={markersVisible ? 'Hide markers' : 'Show markers'}>
          <IconButton
            onClick={onToggleMarkers}
            sx={{ height: 32, width: 32 }}
            color={markersVisible ? 'primary' : 'default'}
          >
            {markersVisible ? (
              <VisibilityIcon fontSize="small" />
            ) : (
              <VisibilityOffIcon fontSize="small" />
            )}
          </IconButton>
        </Tooltip>

        {hasSelection ? (
          <Tooltip title="Reset selection">
            <IconButton
              onClick={onResetSelection}
              sx={{ height: 32, width: 32 }}
            >
              <ClearIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ) : null}

        <Tooltip title="Reset zoom (show all)">
          <IconButton onClick={onResetZoom} sx={{ height: 32, width: 32 }}>
            <ZoomOutMapIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        <Tooltip title={t('tables.trend.reloadCandles')}>
          <IconButton
            onClick={onReloadCandles}
            disabled={isCandleRefreshing}
            sx={{ height: 32, width: 32 }}
          >
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Row 2: Active cycle filter chips */}
      {(hasActiveLongCycles || hasActiveShortCycles) && (
        <Stack direction="row" spacing={0.75} sx={{ pl: 2 }}>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ alignSelf: 'center', mr: 0.5 }}
          >
            Active Cycles:
          </Typography>
          {hasActiveLongCycles && (
            <Chip
              size="small"
              clickable
              label="LONG"
              color={activeCycleFilter === 'long' ? 'success' : 'default'}
              variant={activeCycleFilter === 'long' ? 'filled' : 'outlined'}
              onClick={() =>
                onActiveCycleFilterChange(
                  activeCycleFilter === 'long' ? 'off' : 'long'
                )
              }
            />
          )}
          {hasActiveShortCycles && (
            <Chip
              size="small"
              clickable
              label="SHORT"
              color={activeCycleFilter === 'short' ? 'error' : 'default'}
              variant={activeCycleFilter === 'short' ? 'filled' : 'outlined'}
              onClick={() =>
                onActiveCycleFilterChange(
                  activeCycleFilter === 'short' ? 'off' : 'short'
                )
              }
            />
          )}
        </Stack>
      )}
    </Box>
  );
}
