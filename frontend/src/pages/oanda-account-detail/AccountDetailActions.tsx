import {
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import { Code as CodeIcon, Refresh as RefreshIcon } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import type { MarketStatusResponse } from '../../services/api/market';
import type {
  Account,
  AccountSnapshotRefreshStatus,
} from '../../types/strategy';
import { snapshotRefreshStatusLabel } from './formatters';

interface AccountDetailActionsProps {
  account: Account;
  isSnapshotRefreshInFlight: boolean;
  marketStatus?: MarketStatusResponse;
  trackedSnapshotRefreshStatus?: AccountSnapshotRefreshStatus;
  onOpenRawData: () => void;
  onRefreshSnapshot: () => void;
  onReloadAll: () => void;
}

export function AccountDetailActions({
  account,
  isSnapshotRefreshInFlight,
  marketStatus,
  trackedSnapshotRefreshStatus,
  onOpenRawData,
  onRefreshSnapshot,
  onReloadAll,
}: AccountDetailActionsProps) {
  const { t } = useTranslation(['settings', 'common']);

  return (
    <Box
      display="flex"
      alignItems="center"
      justifyContent={{ xs: 'flex-end', sm: 'flex-end' }}
      gap={1}
      flexWrap="wrap"
      mb={2}
    >
      {marketStatus && (
        <Chip
          label={
            marketStatus.is_open
              ? t('settings:accounts.marketOpen')
              : t('settings:accounts.marketClosed')
          }
          color={marketStatus.is_open ? 'success' : 'default'}
          size="small"
        />
      )}
      <Tooltip
        title={
          isSnapshotRefreshInFlight
            ? snapshotRefreshStatusLabel(
                t,
                trackedSnapshotRefreshStatus ?? 'queued'
              )
            : account.is_active
              ? t('settings:accounts.refreshSnapshot', 'Refresh snapshot')
              : t(
                  'settings:accounts.inactiveRefreshDisabled',
                  'Inactive accounts cannot be refreshed'
                )
        }
      >
        <span>
          <Button
            variant="outlined"
            startIcon={
              isSnapshotRefreshInFlight ? (
                <CircularProgress size={18} />
              ) : (
                <RefreshIcon />
              )
            }
            onClick={onRefreshSnapshot}
            disabled={!account.is_active || isSnapshotRefreshInFlight}
          >
            {t('settings:accounts.refreshSnapshot', 'Refresh snapshot')}
          </Button>
        </span>
      </Tooltip>
      <Tooltip title={t('common:actions.reload')}>
        <IconButton onClick={onReloadAll}>
          <RefreshIcon />
        </IconButton>
      </Tooltip>
      <Button
        variant="outlined"
        startIcon={<CodeIcon />}
        onClick={onOpenRawData}
      >
        {t('settings:accounts.rawData')}
      </Button>
    </Box>
  );
}
