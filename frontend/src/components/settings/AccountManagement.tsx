import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  CardActions,
  Typography,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Visibility,
  VisibilityOff,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useToast } from '../common/useToast';
import ConfirmDialog from '../common/ConfirmDialog';
import type { Account } from '../../types/strategy';
import { accountsApi } from '../../services/api/accounts';
import type { OandaAccounts, OandaAccountsRequest } from '../../api/generated';

interface AccountFormData {
  account_id: string;
  api_token: string;
  api_type: 'practice' | 'live';
}

const AccountManagement = () => {
  const { t } = useTranslation(['settings', 'common']);
  const { showSuccess, showError } = useToast();

  const isMountedRef = useRef(true);

  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [accountToDelete, setAccountToDelete] = useState<Account | null>(null);
  const [showApiToken, setShowApiToken] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [formData, setFormData] = useState<AccountFormData>({
    account_id: '',
    api_token: '',
    api_type: 'practice',
  });
  const [isDefault, setIsDefault] = useState(false);

  const [formErrors, setFormErrors] = useState<Partial<AccountFormData>>({});

  // Fetch accounts
  const fetchAccounts = useCallback(
    async ({ showLoading = true }: { showLoading?: boolean } = {}) => {
      try {
        if (showLoading) {
          setLoading(true);
        }
        const data = await accountsApi.list();

        const listedAccounts = Array.isArray(data) ? data : [];
        setAccounts(listedAccounts as Account[]);

        // Hydrate each account with live data (balance/margins/etc) from the detail endpoint.
        // Do this after the list loads so the UI renders quickly.
        if (listedAccounts.length > 0) {
          void (async () => {
            const results = await Promise.allSettled(
              listedAccounts.map((account: OandaAccounts) =>
                accountsApi.get(account.id)
              )
            );

            if (!isMountedRef.current) {
              return;
            }

            const hydratedAccounts = results
              .filter(
                (result): result is PromiseFulfilledResult<OandaAccounts> =>
                  result.status === 'fulfilled'
              )
              .map(
                (result: PromiseFulfilledResult<OandaAccounts>) => result.value
              );

            if (hydratedAccounts.length === 0) {
              return;
            }

            setAccounts((previousAccounts) =>
              previousAccounts.map(
                (account: Account) =>
                  (hydratedAccounts.find(
                    (hydrated) => hydrated.id === account.id
                  ) as Account | undefined) ?? account
              )
            );
          })();
        }
      } catch (caughtError) {
        console.error('Error fetching accounts:', caughtError);
        showError(t('common:errors.fetchFailed', 'Failed to load data'));
      } finally {
        if (showLoading) {
          setLoading(false);
        }
      }
    },
    [showError, t]
  );

  useEffect(() => {
    isMountedRef.current = true;
    fetchAccounts();
    return () => {
      isMountedRef.current = false;
    };
  }, [fetchAccounts]);

  // Open dialog for adding new account
  const handleAddClick = () => {
    setEditingAccount(null);
    setFormData({
      account_id: '',
      api_token: '',
      api_type: 'practice',
    });
    setIsDefault(accounts.length === 0); // First account is default
    setFormErrors({});
    setShowApiToken(false);
    setDialogOpen(true);
  };

  // Open dialog for editing account
  const handleEditClick = (account: Account) => {
    setEditingAccount(account);
    setFormData({
      account_id: account.account_id,
      api_token: '', // Don't populate token for security
      api_type: account.api_type,
    });
    setIsDefault(account.is_default || false);
    setFormErrors({});
    setShowApiToken(false);
    setDialogOpen(true);
  };

  // Close dialog
  const handleDialogClose = () => {
    setDialogOpen(false);
    setEditingAccount(null);
    setFormData({
      account_id: '',
      api_token: '',
      api_type: 'practice',
    });
    setIsDefault(false);
    setFormErrors({});
  };

  // Validate form
  const validateForm = (): boolean => {
    const errors: Partial<AccountFormData> = {};

    if (!formData.account_id.trim()) {
      errors.account_id = t(
        'common:validation.required',
        'This field is required'
      );
    }

    // Only require API token for new accounts or if it's being changed
    if (!editingAccount && !formData.api_token.trim()) {
      errors.api_token = t(
        'common:validation.required',
        'This field is required'
      );
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  // Submit form
  const handleSubmit = async () => {
    if (!validateForm()) {
      return;
    }

    setSubmitting(true);

    try {
      // Only include api_token if it's provided
      const payload: Partial<AccountFormData> & { is_default?: boolean } = {
        account_id: formData.account_id,
        api_type: formData.api_type,
        is_default: isDefault,
      };

      if (formData.api_token.trim()) {
        payload.api_token = formData.api_token;
      }

      if (editingAccount) {
        await accountsApi.update(
          editingAccount.id,
          payload as OandaAccountsRequest
        );
      } else {
        await accountsApi.create(payload as OandaAccountsRequest);
      }

      // Close immediately; refresh balances in the background.
      showSuccess(
        t('settings:messages.accountAdded', 'Account saved successfully')
      );
      handleDialogClose();
      await fetchAccounts({ showLoading: false });
    } catch (error) {
      console.error('Error saving account:', error);
      showError(
        error instanceof Error
          ? error.message
          : t('settings:messages.saveError', 'Failed to save account')
      );
    } finally {
      setSubmitting(false);
    }
  };

  // Open delete confirmation
  const handleDeleteClick = (account: Account) => {
    setAccountToDelete(account);
    setDeleteConfirmOpen(true);
  };

  // Confirm delete
  const handleDeleteConfirm = async () => {
    if (!accountToDelete) return;

    try {
      await accountsApi.delete(accountToDelete.id);

      showSuccess(
        t('settings:messages.accountDeleted', 'Account deleted successfully')
      );
      setDeleteConfirmOpen(false);
      setAccountToDelete(null);
      await fetchAccounts({ showLoading: false });
    } catch (error) {
      console.error('Error deleting account:', error);
      showError(t('common:errors.deleteFailed', 'Failed to delete'));
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
      // Intl throws for unsupported/invalid codes; fall back to simple formatting.
      return `${currencyCode} ${numericBalance.toFixed(2)}`;
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" py={4}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={2}
      >
        <Typography variant="h6">
          {t('settings:accounts.title', 'OANDA Accounts')}
        </Typography>
        <Button
          variant="contained"
          color="primary"
          startIcon={<AddIcon />}
          onClick={handleAddClick}
        >
          {t('settings:accounts.addAccount', 'Add Account')}
        </Button>
      </Box>

      <Alert severity="info" sx={{ mb: 3 }}>
        <Typography variant="body2">
          {t(
            'settings:accounts.defaultAccountInfo',
            'The default account is used to fetch market data and collect tick data for analysis. The candle chart will use the default account to display price data. You can switch the default account at any time.'
          )}
        </Typography>
      </Alert>

      {accounts.length === 0 ? (
        <Alert severity="info">
          {t(
            'common:noData',
            'No accounts found. Add your first account to get started.'
          )}
        </Alert>
      ) : (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              sm: 'repeat(2, 1fr)',
              md: 'repeat(3, 1fr)',
            },
            gap: 2,
          }}
        >
          {accounts.map((account) => (
            <Box key={account.id}>
              <Card>
                <CardActionArea
                  component={Link}
                  to={`/settings/accounts/${account.id}`}
                  aria-label={`View account ${account.account_id}`}
                >
                  <CardContent>
                    <Box
                      display="flex"
                      justifyContent="space-between"
                      alignItems="flex-start"
                      mb={2}
                    >
                      <Typography variant="h6" component="div" noWrap>
                        {account.account_id}
                      </Typography>
                      <Chip
                        label={
                          account.api_type === 'practice'
                            ? t('settings:accounts.practice', 'Practice')
                            : t('settings:accounts.live', 'Live')
                        }
                        color={
                          account.api_type === 'practice'
                            ? 'default'
                            : 'warning'
                        }
                        size="small"
                      />
                    </Box>

                    <Box mb={1}>
                      <Typography variant="body2" color="text.secondary">
                        {t('settings:accounts.balance', 'Balance')}
                      </Typography>
                      <Typography variant="h6">
                        {formatBalance(account.balance, account.currency)}
                      </Typography>
                    </Box>

                    <Box mb={1}>
                      <Typography variant="body2" color="text.secondary">
                        {t('settings:accounts.marginUsed', 'Margin Used')}
                      </Typography>
                      <Typography variant="body1">
                        {formatBalance(account.margin_used, account.currency)}
                      </Typography>
                    </Box>

                    <Box mb={1}>
                      <Typography variant="body2" color="text.secondary">
                        {t(
                          'settings:accounts.marginAvailable',
                          'Margin Available'
                        )}
                      </Typography>
                      <Typography variant="body1">
                        {formatBalance(
                          account.margin_available,
                          account.currency
                        )}
                      </Typography>
                    </Box>

                    <Box mb={1}>
                      <Typography variant="body2" color="text.secondary">
                        {t('settings:accounts.unrealizedPnL', 'Unrealized P&L')}
                      </Typography>
                      <Typography
                        variant="body1"
                        sx={{
                          color:
                            parseFloat(account.unrealized_pnl) >= 0
                              ? 'success.main'
                              : 'error.main',
                          fontWeight: 500,
                        }}
                      >
                        {parseFloat(account.unrealized_pnl) >= 0 ? '+' : ''}
                        {formatBalance(
                          account.unrealized_pnl,
                          account.currency
                        )}
                      </Typography>
                    </Box>

                    <Box mb={1}>
                      <Typography variant="body2" color="text.secondary">
                        {t('settings:accounts.currency', 'Currency')}
                      </Typography>
                      <Typography variant="body1">
                        {account.currency}
                      </Typography>
                    </Box>

                    <Box display="flex" gap={1}>
                      <Chip
                        label={account.is_active ? 'Active' : 'Inactive'}
                        color={account.is_active ? 'success' : 'default'}
                        size="small"
                      />
                      {account.is_default && (
                        <Chip
                          label="Default"
                          color="primary"
                          size="small"
                          variant="outlined"
                        />
                      )}
                    </Box>
                  </CardContent>
                </CardActionArea>
                <CardActions>
                  <IconButton
                    size="small"
                    color="primary"
                    onClick={(event) => {
                      event.stopPropagation();
                      handleEditClick(account);
                    }}
                    aria-label={t(
                      'settings:accounts.editAccount',
                      'Edit Account'
                    )}
                  >
                    <EditIcon />
                  </IconButton>
                  <IconButton
                    size="small"
                    color="error"
                    onClick={(event) => {
                      event.stopPropagation();
                      handleDeleteClick(account);
                    }}
                    aria-label={t(
                      'settings:accounts.deleteAccount',
                      'Delete Account'
                    )}
                  >
                    <DeleteIcon />
                  </IconButton>
                </CardActions>
              </Card>
            </Box>
          ))}
        </Box>
      )}

      {/* Add/Edit Dialog */}
      <Dialog
        open={dialogOpen}
        onClose={handleDialogClose}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {editingAccount
            ? t('settings:accounts.editAccount', 'Edit Account')
            : t('settings:accounts.addAccount', 'Add Account')}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <TextField
              fullWidth
              label={t('settings:accounts.accountId', 'Account ID')}
              value={formData.account_id}
              onChange={(e) =>
                setFormData({ ...formData, account_id: e.target.value })
              }
              error={!!formErrors.account_id}
              helperText={formErrors.account_id}
              margin="normal"
              required
            />

            <TextField
              fullWidth
              label={t('settings:accounts.apiToken', 'API Token')}
              type={showApiToken ? 'text' : 'password'}
              value={formData.api_token}
              onChange={(e) =>
                setFormData({ ...formData, api_token: e.target.value })
              }
              error={!!formErrors.api_token}
              helperText={
                formErrors.api_token ||
                (editingAccount
                  ? 'Leave blank to keep existing token'
                  : undefined)
              }
              margin="normal"
              required={!editingAccount}
              InputProps={{
                endAdornment: (
                  <IconButton
                    onClick={() => setShowApiToken(!showApiToken)}
                    edge="end"
                  >
                    {showApiToken ? <VisibilityOff /> : <Visibility />}
                  </IconButton>
                ),
              }}
            />

            <FormControl fullWidth margin="normal">
              <InputLabel id="api-type-label">
                {t('settings:accounts.apiType', 'API Type')}
              </InputLabel>
              <Select
                labelId="api-type-label"
                value={formData.api_type}
                label={t('settings:accounts.apiType', 'API Type')}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    api_type: e.target.value as 'practice' | 'live',
                  })
                }
              >
                <MenuItem value="practice">
                  {t('settings:accounts.practice', 'Practice')}
                </MenuItem>
                <MenuItem value="live">
                  {t('settings:accounts.live', 'Live')}
                </MenuItem>
              </Select>
            </FormControl>

            <Box sx={{ mt: 2 }}>
              <Box display="flex" alignItems="center" gap={1}>
                <input
                  type="checkbox"
                  id="is-default-checkbox"
                  checked={isDefault}
                  onChange={(e) => setIsDefault(e.target.checked)}
                  disabled={accounts.length === 0 && !editingAccount}
                />
                <label htmlFor="is-default-checkbox">
                  <Typography variant="body2">
                    {t(
                      'settings:accounts.setAsDefault',
                      'Set as default account'
                    )}
                  </Typography>
                </label>
              </Box>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mt: 0.5, display: 'block' }}
              >
                {t(
                  'settings:accounts.defaultAccountDescription',
                  'The default account is used to collect market data and latest tick data. Only one account can be set as default at a time.'
                )}
              </Typography>
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDialogClose} disabled={submitting}>
            {t('common:cancel', 'Cancel')}
          </Button>
          <Button
            onClick={handleSubmit}
            variant="contained"
            color="primary"
            disabled={submitting}
          >
            {submitting ? (
              <CircularProgress size={24} />
            ) : editingAccount ? (
              t('common:save', 'Save')
            ) : (
              t('common:add', 'Add')
            )}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteConfirmOpen}
        title={t('settings:accounts.deleteAccount', 'Delete Account')}
        message={t(
          'settings:accounts.confirmDelete',
          'Are you sure you want to delete this account?'
        )}
        confirmText={t('common:delete', 'Delete')}
        cancelText={t('common:cancel', 'Cancel')}
        confirmColor="error"
        onConfirm={handleDeleteConfirm}
        onCancel={() => {
          setDeleteConfirmOpen(false);
          setAccountToDelete(null);
        }}
      />
    </Box>
  );
};

export default AccountManagement;
