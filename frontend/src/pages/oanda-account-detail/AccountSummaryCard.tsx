import { Box, Card, CardContent, Chip, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { isAccountSnapshotRefreshActive } from '../../hooks/useAccounts';
import type {
  Account,
  AccountSnapshotRefreshStatus,
} from '../../types/strategy';
import { fmtBal, fmtTs, snapshotRefreshStatusLabel } from './formatters';

interface AccountSummaryCardProps {
  account: Account;
  trackedSnapshotRefreshStatus?: AccountSnapshotRefreshStatus;
}

export function AccountSummaryCard({
  account,
  trackedSnapshotRefreshStatus,
}: AccountSummaryCardProps) {
  const { t } = useTranslation(['settings']);

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Box display="flex" alignItems="center" gap={1} mb={2}>
          <Typography variant="h6">{account.account_id}</Typography>
          <Chip
            label={
              account.api_type === 'practice'
                ? t('settings:accounts.practice')
                : t('settings:accounts.live')
            }
            color={account.api_type === 'practice' ? 'default' : 'warning'}
            size="small"
          />
          {account.is_active && (
            <Chip label="Active" color="success" size="small" />
          )}
          {account.is_default && (
            <Chip
              label="Default"
              color="primary"
              variant="outlined"
              size="small"
            />
          )}
          {isAccountSnapshotRefreshActive(trackedSnapshotRefreshStatus) && (
            <Chip
              label={snapshotRefreshStatusLabel(
                t,
                trackedSnapshotRefreshStatus
              )}
              color="info"
              variant="outlined"
              size="small"
            />
          )}
          {account.snapshot_stale && (
            <Chip
              label={t('settings:accounts.snapshotStale', 'Snapshot stale')}
              color="warning"
              variant="outlined"
              size="small"
            />
          )}
          {account.snapshot_refresh_error && (
            <Chip
              label={t(
                'settings:accounts.snapshotRefreshFailed',
                'Refresh failed'
              )}
              color="error"
              variant="outlined"
              size="small"
            />
          )}
        </Box>
        <Box
          display="grid"
          gridTemplateColumns={{
            xs: '1fr',
            sm: 'repeat(2, 1fr)',
            md: 'repeat(4, 1fr)',
          }}
          gap={2}
        >
          <Box>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.balance')}
            </Typography>
            <Typography variant="h6">
              {fmtBal(account.balance, account.currency)}
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.nav')}
            </Typography>
            <Typography variant="h6">
              {fmtBal(account.nav ?? null, account.currency)}
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.unrealizedPnL')}
            </Typography>
            <Typography
              variant="h6"
              sx={{
                color:
                  parseFloat(account.unrealized_pnl) >= 0
                    ? 'success.main'
                    : 'error.main',
              }}
            >
              {parseFloat(account.unrealized_pnl) >= 0 ? '+' : ''}
              {fmtBal(account.unrealized_pnl, account.currency)}
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.currency')}
            </Typography>
            <Typography variant="h6">{account.currency}</Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.marginUsed')}
            </Typography>
            <Typography variant="body1">
              {fmtBal(account.margin_used, account.currency)}
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.marginAvailable')}
            </Typography>
            <Typography variant="body1">
              {fmtBal(account.margin_available, account.currency)}
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.openTrades')}
            </Typography>
            <Typography variant="body1">
              {account.open_trade_count ?? '\u2014'}
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.openPositions')}
            </Typography>
            <Typography variant="body1">
              {account.open_position_count ?? '\u2014'}
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.pendingOrders')}
            </Typography>
            <Typography variant="body1">
              {account.pending_order_count ?? '\u2014'}
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.positionMode')}
            </Typography>
            <Typography variant="body1">
              {account.position_mode ?? '\u2014'}
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.hedgingEnabled')}
            </Typography>
            <Typography variant="body1">
              {typeof account.hedging_enabled === 'boolean'
                ? String(account.hedging_enabled)
                : '\u2014'}
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.snapshotRefreshedAt', 'Snapshot refreshed')}
            </Typography>
            <Typography variant="body1">
              {fmtTs(account.snapshot_refreshed_at ?? null)}
            </Typography>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}
