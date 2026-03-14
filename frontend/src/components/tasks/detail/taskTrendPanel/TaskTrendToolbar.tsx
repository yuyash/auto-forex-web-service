import {
  Box,
  Button,
  CircularProgress,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Tooltip,
  Typography,
} from '@mui/material';
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap';
import type { SelectChangeEvent } from '@mui/material/Select';
import { useTranslation } from 'react-i18next';
import type { ReplaySummary } from './shared';

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
  onPollingIntervalChange: (value: number) => void;
  onGranularityChange: (event: SelectChangeEvent<string>) => void;
  onFollow: () => void;
  onResetZoom: () => void;
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
  onPollingIntervalChange,
  onGranularityChange,
  onFollow,
  onResetZoom,
}: TaskTrendToolbarProps) {
  const { t } = useTranslation('common');

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        mb: 1,
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
          color={replaySummary.realizedPnl >= 0 ? 'success.main' : 'error.main'}
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
          <Typography variant="caption" color="text.secondary" lineHeight={1.2}>
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
        <InputLabel id="replay-granularity-label" sx={{ fontSize: '0.75rem' }}>
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

      <Tooltip title="Reset zoom (show all)">
        <IconButton onClick={onResetZoom} sx={{ height: 32, width: 32 }}>
          <ZoomOutMapIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
}
