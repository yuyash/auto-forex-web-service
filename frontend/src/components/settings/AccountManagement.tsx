import { useState } from 'react';
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
  FormControlLabel,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
  Switch,
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
import type { Account, AccountUpsertData } from '../../types/strategy';
import {
  useCreateAccount,
  useDeleteAccount,
  useUpdateAccount,
} from '../../hooks/useAccountMutations';
import { useAccounts } from '../../hooks/useAccounts';
import { logger } from '../../utils/logger';
import { useNumberFormatter } from '../../hooks/useNumberFormatter';
import { currencySymbol } from '../../utils/numberFormat';

interface AccountFormData {
  account_id: string;
  api_token: string;
  api_type: 'practice' | 'live';
  live_max_exposure_guard_enabled: boolean;
  live_max_estimated_exposure_units: string;
  live_max_initial_order_guard_enabled: boolean;
  live_max_initial_order_units: string;
  live_max_order_guard_enabled: boolean;
  live_max_order_units: string;
}

const DEFAULT_MAX_GROSS_UNITS = '200000';
const DEFAULT_MAX_INITIAL_ORDER_UNITS = '10000';
const DEFAULT_MAX_ORDER_UNITS = '10000';

const AccountManagement = () => {
  const { t } = useTranslation(['settings', 'common']);
  const { formatNumber } = useNumberFormatter();
  const { showSuccess, showError } = useToast();
  const {
    data: rawAccounts,
    isLoading: loading,
    error: accountsError,
  } = useAccounts();
  const accounts = rawAccounts ?? [];
  const createAccount = useCreateAccount();
  const updateAccount = useUpdateAccount();
  const deleteAccount = useDeleteAccount();
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
    live_max_exposure_guard_enabled: false,
    live_max_estimated_exposure_units: DEFAULT_MAX_GROSS_UNITS,
    live_max_initial_order_guard_enabled: true,
    live_max_initial_order_units: DEFAULT_MAX_INITIAL_ORDER_UNITS,
    live_max_order_guard_enabled: false,
    live_max_order_units: DEFAULT_MAX_ORDER_UNITS,
  });
  const [isDefault, setIsDefault] = useState(false);

  const [formErrors, setFormErrors] = useState<
    Partial<Record<keyof AccountFormData, string>>
  >({});

  // Open dialog for adding new account
  const handleAddClick = () => {
    setEditingAccount(null);
    setFormData({
      account_id: '',
      api_token: '',
      api_type: 'practice',
      live_max_exposure_guard_enabled: false,
      live_max_estimated_exposure_units: DEFAULT_MAX_GROSS_UNITS,
      live_max_initial_order_guard_enabled: true,
      live_max_initial_order_units: DEFAULT_MAX_INITIAL_ORDER_UNITS,
      live_max_order_guard_enabled: false,
      live_max_order_units: DEFAULT_MAX_ORDER_UNITS,
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
      live_max_exposure_guard_enabled:
        account.live_max_exposure_guard_enabled ?? false,
      live_max_estimated_exposure_units: String(
        account.live_max_estimated_exposure_units ??
          Number(DEFAULT_MAX_GROSS_UNITS)
      ),
      live_max_initial_order_guard_enabled:
        account.live_max_initial_order_guard_enabled ?? true,
      live_max_initial_order_units: String(
        account.live_max_initial_order_units ??
          Number(DEFAULT_MAX_INITIAL_ORDER_UNITS)
      ),
      live_max_order_guard_enabled:
        account.live_max_order_guard_enabled ?? false,
      live_max_order_units: String(
        account.live_max_order_units ?? Number(DEFAULT_MAX_ORDER_UNITS)
      ),
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
      live_max_exposure_guard_enabled: false,
      live_max_estimated_exposure_units: DEFAULT_MAX_GROSS_UNITS,
      live_max_initial_order_guard_enabled: true,
      live_max_initial_order_units: DEFAULT_MAX_INITIAL_ORDER_UNITS,
      live_max_order_guard_enabled: false,
      live_max_order_units: DEFAULT_MAX_ORDER_UNITS,
    });
    setIsDefault(false);
    setFormErrors({});
  };

  // Validate form
  const validateForm = (): boolean => {
    const errors: Partial<Record<keyof AccountFormData, string>> = {};

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
    if (formData.live_max_exposure_guard_enabled) {
      const maxGrossUnits = Number(formData.live_max_estimated_exposure_units);
      if (
        !Number.isInteger(maxGrossUnits) ||
        !Number.isFinite(maxGrossUnits) ||
        maxGrossUnits <= 0
      ) {
        errors.live_max_estimated_exposure_units = t(
          'settings:accounts.maxGrossUnitsValidation',
          'Enter a positive whole number.'
        );
      }
    }
    if (formData.live_max_initial_order_guard_enabled) {
      const maxInitialOrderUnits = Number(
        formData.live_max_initial_order_units
      );
      if (
        !Number.isInteger(maxInitialOrderUnits) ||
        !Number.isFinite(maxInitialOrderUnits) ||
        maxInitialOrderUnits <= 0
      ) {
        errors.live_max_initial_order_units = t(
          'settings:accounts.maxInitialOrderUnitsValidation',
          'Enter a positive whole number.'
        );
      }
    }
    if (formData.live_max_order_guard_enabled) {
      const maxOrderUnits = Number(formData.live_max_order_units);
      if (
        !Number.isInteger(maxOrderUnits) ||
        !Number.isFinite(maxOrderUnits) ||
        maxOrderUnits <= 0
      ) {
        errors.live_max_order_units = t(
          'settings:accounts.maxOrderUnitsValidation',
          'Enter a positive whole number.'
        );
      }
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
      const payload: AccountUpsertData = {
        account_id: formData.account_id,
        api_type: formData.api_type,
        is_default: isDefault,
        live_max_exposure_guard_enabled:
          formData.live_max_exposure_guard_enabled,
        live_max_initial_order_guard_enabled:
          formData.live_max_initial_order_guard_enabled,
        live_max_order_guard_enabled: formData.live_max_order_guard_enabled,
      };
      if (formData.live_max_exposure_guard_enabled) {
        payload.live_max_estimated_exposure_units = Number(
          formData.live_max_estimated_exposure_units || DEFAULT_MAX_GROSS_UNITS
        );
      }
      if (formData.live_max_initial_order_guard_enabled) {
        payload.live_max_initial_order_units = Number(
          formData.live_max_initial_order_units ||
            DEFAULT_MAX_INITIAL_ORDER_UNITS
        );
      }
      if (formData.live_max_order_guard_enabled) {
        payload.live_max_order_units = Number(
          formData.live_max_order_units || DEFAULT_MAX_ORDER_UNITS
        );
      }

      if (formData.api_token.trim()) {
        payload.api_token = formData.api_token;
      }

      if (editingAccount) {
        await updateAccount.mutate({
          id: editingAccount.id,
          data: payload as AccountUpsertData,
        });
      } else {
        await createAccount.mutate(payload as AccountUpsertData);
      }

      showSuccess(t('settings:messages.accountAdded'));
      handleDialogClose();
    } catch (error: unknown) {
      logger.error('Error saving account', {
        error: error instanceof Error ? error.message : String(error),
      });

      // Extract validation details from TransformedApiError or ApiError
      let message = t('settings:messages.saveError');
      const err = error as Record<string, unknown>;

      if (err.details && typeof err.details === 'object') {
        // DRF returns field-level errors like { account_id: ["..."], api_token: ["..."] }
        const details = err.details as Record<string, unknown>;
        const fieldErrors: Partial<Record<keyof AccountFormData, string>> = {};
        const messages: string[] = [];

        for (const [key, val] of Object.entries(details)) {
          const msgs = Array.isArray(val) ? val.map(String) : [String(val)];
          if (key in formData) {
            fieldErrors[key as keyof AccountFormData] = msgs.join(', ');
          }
          messages.push(...msgs);
        }

        if (Object.keys(fieldErrors).length > 0) {
          setFormErrors((prev) => ({ ...prev, ...fieldErrors }));
        }
        if (messages.length > 0) {
          message = messages.join(' ');
        }
      } else if (err.message && typeof err.message === 'string') {
        message = err.message;
      } else if (error instanceof Error) {
        message = error.message;
      }

      showError(message);
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
      await deleteAccount.mutate(accountToDelete.id);

      showSuccess(t('settings:messages.accountDeleted'));
      setDeleteConfirmOpen(false);
      setAccountToDelete(null);
    } catch (error) {
      logger.error('Error deleting account', {
        error: error instanceof Error ? error.message : String(error),
      });
      showError(t('common:errors.deleteFailed'));
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
    const symbol = currencySymbol(currencyCode);
    const prefix =
      symbol === currencyCode.trim().toUpperCase() ? `${symbol} ` : symbol;

    return `${prefix}${formatNumber(numericBalance, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" py={4}>
        <CircularProgress />
      </Box>
    );
  }

  if (accountsError) {
    return <Alert severity="error">{t('common:errors.fetchFailed')}</Alert>;
  }

  return (
    <Box>
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={2}
      >
        <Typography variant="h6">{t('settings:accounts.title')}</Typography>
        <Button
          variant="contained"
          color="primary"
          startIcon={<AddIcon />}
          onClick={handleAddClick}
        >
          {t('settings:accounts.addAccount')}
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
                            ? t('settings:accounts.practice')
                            : t('settings:accounts.live')
                        }
                        color={
                          account.api_type === 'practice'
                            ? 'default'
                            : 'warning'
                        }
                      />
                    </Box>

                    <Box mb={1}>
                      <Typography variant="body2" color="text.secondary">
                        {t('settings:accounts.balance')}
                      </Typography>
                      <Typography variant="h6">
                        {formatBalance(account.balance, account.currency)}
                      </Typography>
                    </Box>

                    <Box mb={1}>
                      <Typography variant="body2" color="text.secondary">
                        {t('settings:accounts.marginUsed')}
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
                        {t('settings:accounts.unrealizedPnL')}
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
                        {t('settings:accounts.currency')}
                      </Typography>
                      <Typography variant="body1">
                        {account.currency}
                      </Typography>
                    </Box>

                    <Box display="flex" gap={1} flexWrap="wrap">
                      <Chip
                        label={account.is_active ? 'Active' : 'Inactive'}
                        color={account.is_active ? 'success' : 'default'}
                      />
                      {account.is_default && (
                        <Chip
                          label="Default"
                          color="primary"
                          variant="outlined"
                        />
                      )}
                      {account.live_max_exposure_guard_enabled && (
                        <Chip
                          label={t('settings:accounts.maxGrossUnitsChip', {
                            defaultValue: 'Max Gross {{units}}',
                            units: formatNumber(
                              account.live_max_estimated_exposure_units ?? 0,
                              {
                                maximumFractionDigits: 0,
                              }
                            ),
                          })}
                          color="secondary"
                          variant="outlined"
                        />
                      )}
                      {account.live_max_initial_order_guard_enabled && (
                        <Chip
                          label={t(
                            'settings:accounts.maxInitialOrderUnitsChip',
                            {
                              defaultValue: 'Max Initial {{units}}',
                              units: formatNumber(
                                account.live_max_initial_order_units ?? 0,
                                {
                                  maximumFractionDigits: 0,
                                }
                              ),
                            }
                          )}
                          color="secondary"
                          variant="outlined"
                        />
                      )}
                      {account.live_max_order_guard_enabled && (
                        <Chip
                          label={t('settings:accounts.maxOrderUnitsChip', {
                            defaultValue: 'Max Order {{units}}',
                            units: formatNumber(
                              account.live_max_order_units ?? 0,
                              {
                                maximumFractionDigits: 0,
                              }
                            ),
                          })}
                          color="secondary"
                          variant="outlined"
                        />
                      )}
                    </Box>
                  </CardContent>
                </CardActionArea>
                <CardActions>
                  <IconButton
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
            ? t('settings:accounts.editAccount')
            : t('settings:accounts.addAccount')}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <TextField
              fullWidth
              label={t('settings:accounts.accountId')}
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
              label={t('settings:accounts.apiToken')}
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
                {t('settings:accounts.apiType')}
              </InputLabel>
              <Select
                labelId="api-type-label"
                value={formData.api_type}
                label={t('settings:accounts.apiType')}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    api_type: e.target.value as 'practice' | 'live',
                  })
                }
              >
                <MenuItem value="practice">
                  {t('settings:accounts.practice')}
                </MenuItem>
                <MenuItem value="live">{t('settings:accounts.live')}</MenuItem>
              </Select>
            </FormControl>

            <Box sx={{ mt: 2 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.live_max_exposure_guard_enabled}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        live_max_exposure_guard_enabled: e.target.checked,
                      })
                    }
                  />
                }
                label={t(
                  'settings:accounts.maxGrossUnitsGuard',
                  'Max Gross Units check'
                )}
              />
              {formData.live_max_exposure_guard_enabled && (
                <TextField
                  fullWidth
                  label={t(
                    'settings:accounts.maxGrossUnits',
                    'Max Gross Units'
                  )}
                  type="text"
                  inputMode="decimal"
                  value={formData.live_max_estimated_exposure_units}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      live_max_estimated_exposure_units: e.target.value,
                    })
                  }
                  error={!!formErrors.live_max_estimated_exposure_units}
                  helperText={formErrors.live_max_estimated_exposure_units}
                  margin="normal"
                  inputProps={{ min: 1, step: 1 }}
                />
              )}
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.live_max_initial_order_guard_enabled}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        live_max_initial_order_guard_enabled: e.target.checked,
                      })
                    }
                  />
                }
                label={t(
                  'settings:accounts.maxInitialOrderUnitsGuard',
                  'Max Initial Order Units check'
                )}
              />
              {formData.live_max_initial_order_guard_enabled && (
                <TextField
                  fullWidth
                  label={t(
                    'settings:accounts.maxInitialOrderUnits',
                    'Max Initial Order Units'
                  )}
                  type="text"
                  inputMode="decimal"
                  value={formData.live_max_initial_order_units}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      live_max_initial_order_units: e.target.value,
                    })
                  }
                  error={!!formErrors.live_max_initial_order_units}
                  helperText={formErrors.live_max_initial_order_units}
                  margin="normal"
                  inputProps={{ min: 1, step: 1 }}
                />
              )}
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.live_max_order_guard_enabled}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        live_max_order_guard_enabled: e.target.checked,
                      })
                    }
                  />
                }
                label={t(
                  'settings:accounts.maxOrderUnitsGuard',
                  'Max Order Units check'
                )}
              />
              {formData.live_max_order_guard_enabled && (
                <TextField
                  fullWidth
                  label={t(
                    'settings:accounts.maxOrderUnits',
                    'Max Order Units'
                  )}
                  type="text"
                  inputMode="decimal"
                  value={formData.live_max_order_units}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      live_max_order_units: e.target.value,
                    })
                  }
                  error={!!formErrors.live_max_order_units}
                  helperText={formErrors.live_max_order_units}
                  margin="normal"
                  inputProps={{ min: 1, step: 1 }}
                />
              )}
            </Box>

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
            {t('common:cancel')}
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
              t('common:save')
            ) : (
              t('common:add')
            )}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteConfirmOpen}
        title={t('settings:accounts.deleteAccount')}
        message={t(
          'settings:accounts.confirmDelete',
          'Are you sure you want to delete this account?'
        )}
        confirmText={t('common:delete')}
        cancelText={t('common:cancel')}
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
