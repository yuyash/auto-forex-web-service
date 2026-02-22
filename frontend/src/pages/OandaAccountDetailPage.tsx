import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Container,
  Divider,
  Typography,
} from '@mui/material';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { accountsApi } from '../services/api/accounts';
import type { Account } from '../types/strategy';

const formatJson = (value: unknown) => {
  if (value == null) {
    return '—';
  }

  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const DEFAULT_ACCOUNT_CURRENCY = 'USD';

const resolveCurrencyCode = (currency?: string | null) => {
  if (!currency) {
    return DEFAULT_ACCOUNT_CURRENCY;
  }

  const trimmed = currency.trim().toUpperCase();
  return trimmed.length === 3 ? trimmed : DEFAULT_ACCOUNT_CURRENCY;
};

const formatBalance = (
  balance: string | number | null | undefined,
  currency?: string
) => {
  if (balance == null) {
    return '—';
  }

  const numericBalance =
    typeof balance === 'string' ? Number(balance) : balance;
  if (Number.isNaN(numericBalance)) {
    return '—';
  }

  const currencyCode = resolveCurrencyCode(currency);

  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currencyCode,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(numericBalance);
  } catch {
    return `${currencyCode} ${numericBalance.toFixed(2)}`;
  }
};

export default function OandaAccountDetailPage() {
  const { t } = useTranslation(['settings', 'common']);
  const params = useParams();

  const containerSx = useMemo(() => ({ mt: 4, mb: 4, px: 3 }), []);

  const accountId = useMemo(() => {
    const raw = params.id;
    const parsed = raw ? Number(raw) : NaN;
    return Number.isFinite(parsed) ? parsed : null;
  }, [params.id]);

  const [account, setAccount] = useState<Account | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    const run = async () => {
      if (!accountId) {
        setError('Invalid account id');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);
        const detail = await accountsApi.get(accountId);
        if (!mounted) return;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        setAccount(detail as any as Account);
      } catch (caughtError) {
        if (!mounted) return;
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : t('common:errors.fetchFailed', 'Failed to load data')
        );
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    void run();

    return () => {
      mounted = false;
    };
  }, [accountId, t]);

  if (loading) {
    return (
      <Container maxWidth={false} sx={containerSx}>
        <Box display="flex" justifyContent="center" alignItems="center" py={4}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth={false} sx={containerSx}>
        <Box>
          <Box mb={2}>
            <Button component={Link} to="/settings" variant="outlined">
              {t('common:back', 'Back')}
            </Button>
          </Box>
          <Alert severity="error">{error}</Alert>
        </Box>
      </Container>
    );
  }

  if (!account) {
    return (
      <Container maxWidth={false} sx={containerSx}>
        <Box>
          <Box mb={2}>
            <Button component={Link} to="/settings" variant="outlined">
              {t('common:back', 'Back')}
            </Button>
          </Box>
          <Alert severity="info">{t('common:noData', 'No data')}</Alert>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth={false} sx={containerSx}>
      <Box>
        <Box
          display="flex"
          alignItems="center"
          justifyContent="space-between"
          mb={2}
        >
          <Typography variant="h6">
            {t('settings:accounts.accountDetails', 'Account Details')}
          </Typography>
          <Button component={Link} to="/settings" variant="outlined">
            {t('common:back', 'Back')}
          </Button>
        </Box>

        <Card>
          <CardContent>
            <Typography variant="h6" component="div" gutterBottom>
              {account.account_id}
            </Typography>

            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.apiType', 'API Type')}: {account.api_type}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.currency', 'Currency')}: {account.currency}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.positionMode', 'Position Mode')}:
              {account.position_mode ?? '—'}
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              {t('settings:accounts.hedgingEnabled', 'Hedging Enabled')}:
              {typeof account.hedging_enabled === 'boolean'
                ? String(account.hedging_enabled)
                : '—'}
            </Typography>

            <Divider sx={{ my: 2 }} />

            <Box
              display="grid"
              gridTemplateColumns={{ xs: '1fr', md: '1fr 1fr' }}
              gap={2}
            >
              <Box>
                <Typography variant="body2" color="text.secondary">
                  {t('settings:accounts.balance', 'Balance')}
                </Typography>
                <Typography variant="h6">
                  {formatBalance(account.balance, account.currency)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  {t('settings:accounts.nav', 'NAV')}
                </Typography>
                <Typography variant="h6">
                  {formatBalance(account.nav ?? null, account.currency)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  {t('settings:accounts.marginUsed', 'Margin Used')}
                </Typography>
                <Typography variant="body1">
                  {formatBalance(account.margin_used, account.currency)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  {t('settings:accounts.marginAvailable', 'Margin Available')}
                </Typography>
                <Typography variant="body1">
                  {formatBalance(account.margin_available, account.currency)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  {t('settings:accounts.unrealizedPnL', 'Unrealized P&L')}
                </Typography>
                <Typography variant="body1">
                  {formatBalance(account.unrealized_pnl, account.currency)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  {t('settings:accounts.openTrades', 'Open Trades')}
                </Typography>
                <Typography variant="body1">
                  {account.open_trade_count ?? '—'}
                </Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  {t('settings:accounts.openPositions', 'Open Positions')}
                </Typography>
                <Typography variant="body1">
                  {account.open_position_count ?? '—'}
                </Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  {t('settings:accounts.pendingOrders', 'Pending Orders')}
                </Typography>
                <Typography variant="body1">
                  {account.pending_order_count ?? '—'}
                </Typography>
              </Box>
            </Box>

            <Divider sx={{ my: 2 }} />

            <Typography variant="body2" color="text.secondary" gutterBottom>
              {t(
                'settings:accounts.oandaAccountFlags',
                'OANDA Account Flags / Parameters'
              )}
            </Typography>
            <Typography
              variant="body2"
              component="pre"
              sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
            >
              {formatJson(account.oanda_account)}
            </Typography>
          </CardContent>
        </Card>
      </Box>
    </Container>
  );
}
