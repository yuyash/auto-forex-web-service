import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Typography,
} from '@mui/material';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';
import { Breadcrumbs, PageContainer } from '../components/common';
import { useAccount } from '../hooks/useAccounts';
import { marketApi } from '../services/api/market';
import { AccountDetailActions } from './oanda-account-detail/AccountDetailActions';
import { AccountSummaryCard } from './oanda-account-detail/AccountSummaryCard';
import { fmtJson } from './oanda-account-detail/formatters';
import { OrdersTable } from './oanda-account-detail/OrdersTable';
import { PositionsTable } from './oanda-account-detail/PositionsTable';
import { useAccountSnapshotRefreshController } from './oanda-account-detail/useAccountSnapshotRefreshController';

export default function OandaAccountDetailPage() {
  const { t } = useTranslation(['settings', 'common']);
  const params = useParams();
  const queryClient = useQueryClient();
  const [rawDataOpen, setRawDataOpen] = useState(false);

  const containerSx = useMemo(() => ({ mt: 4, mb: 4 }), []);

  const accountId = useMemo(() => {
    const raw = params.id;
    const parsed = raw ? Number(raw) : NaN;
    return Number.isFinite(parsed) ? parsed : null;
  }, [params.id]);

  const {
    data: account = null,
    isLoading: loading,
    error: queryError,
  } = useAccount(accountId ?? 0, { enabled: accountId !== null });
  const {
    handleRefreshSnapshot,
    isSnapshotRefreshInFlight,
    trackedSnapshotRefreshStatus,
  } = useAccountSnapshotRefreshController({ account, accountId });

  const { data: marketStatus } = useQuery({
    queryKey: ['market-status'],
    queryFn: () => marketApi.getMarketStatus(),
    refetchInterval: 60000,
  });

  const error =
    accountId === null
      ? 'Invalid account id'
      : queryError instanceof Error
        ? queryError.message
        : queryError
          ? t('common:errors.fetchFailed')
          : null;

  const handleReloadAll = () => {
    queryClient.invalidateQueries({ queryKey: ['accounts'] });
    if (accountId) {
      queryClient.invalidateQueries({ queryKey: ['accounts', accountId] });
      queryClient.invalidateQueries({
        queryKey: ['oanda-positions', accountId],
      });
      queryClient.invalidateQueries({ queryKey: ['oanda-orders', accountId] });
    }
  };

  if (loading) {
    return (
      <PageContainer sx={containerSx}>
        <Breadcrumbs />
        <Box display="flex" justifyContent="center" alignItems="center" py={4}>
          <CircularProgress />
          <Typography variant="body2" color="text.secondary" sx={{ ml: 2 }}>
            {t('settings:accounts.loadingAccountData')}
          </Typography>
        </Box>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer sx={containerSx}>
        <Breadcrumbs />
        <Alert severity="error">{error}</Alert>
      </PageContainer>
    );
  }

  if (!account) {
    return (
      <PageContainer sx={containerSx}>
        <Breadcrumbs />
        <Alert severity="info">{t('common:messages.noData')}</Alert>
      </PageContainer>
    );
  }

  return (
    <PageContainer sx={containerSx}>
      <Breadcrumbs />
      <Box mb={2}>
        <Typography variant="h5">
          {t('settings:accounts.accountDetails')}: {account.account_id}
        </Typography>
      </Box>
      <AccountDetailActions
        account={account}
        isSnapshotRefreshInFlight={isSnapshotRefreshInFlight}
        marketStatus={marketStatus}
        trackedSnapshotRefreshStatus={trackedSnapshotRefreshStatus}
        onOpenRawData={() => setRawDataOpen(true)}
        onRefreshSnapshot={handleRefreshSnapshot}
        onReloadAll={handleReloadAll}
      />

      <AccountSummaryCard
        account={account}
        trackedSnapshotRefreshStatus={trackedSnapshotRefreshStatus}
      />

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {t('common:navigation.positions')}
          </Typography>
          <PositionsTable accountDbId={account.id} />
        </CardContent>
      </Card>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {t('common:navigation.orders')}
          </Typography>
          <OrdersTable accountDbId={account.id} />
        </CardContent>
      </Card>

      <Dialog
        open={rawDataOpen}
        onClose={() => setRawDataOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>{t('settings:accounts.rawData')}</DialogTitle>
        <DialogContent>
          <Typography
            variant="body2"
            component="pre"
            sx={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              bgcolor: 'grey.100',
              p: 2,
              borderRadius: 1,
              maxHeight: '60vh',
              overflow: 'auto',
              fontFamily: 'monospace',
              fontSize: '0.8rem',
            }}
          >
            {fmtJson(account.oanda_account)}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRawDataOpen(false)}>
            {t('common:actions.close')}
          </Button>
        </DialogActions>
      </Dialog>
    </PageContainer>
  );
}
