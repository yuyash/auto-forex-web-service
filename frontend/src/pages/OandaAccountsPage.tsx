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
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Breadcrumbs, PageContainer } from '../components/common';
import { useToast } from '../components/common/useToast';
import ConfirmDialog from '../components/common/ConfirmDialog';
import type { Account, AccountUpsertData } from '../types/strategy';
import {
  useCreateAccount,
  useDeleteAccount,
  useUpdateAccount,
} from '../hooks/useAccountMutations';
import { useAccounts, useAccount } from '../hooks/useAccounts';
import { useQueryClient } from '@tanstack/react-query';
import { logger } from '../utils/logger';
import { formatAppNumber } from '../utils/numberFormat';

interface AccountFormData {
  account_id: string;
  api_token: string;
  api_type: 'practice' | 'live';
}

const DEFAULT_ACCOUNT_CURRENCY = 'USD';

const resolveCurrencyCode = (currency?: string | null) => {
  if (!currency) return DEFAULT_ACCOUNT_CURRENCY;
  const trimmed = currency.trim().toUpperCase();
  return trimmed.length === 3 ? trimmed : DEFAULT_ACCOUNT_CURRENCY;
};

const formatBalance = (
  balance: string | number | null | undefined,
  currency?: string
) => {
  if (balance == null) return '—';
  const numericBalance =
    typeof balance === 'string' ? Number(balance) : balance;
  if (Number.isNaN(numericBalance)) return '—';
  const currencyCode = resolveCurrencyCode(currency);
  try {
    return `${currencyCode} ${formatAppNumber(numericBalance, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  } catch {
    return `${currencyCode} ${formatAppNumber(numericBalance, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }
};

// Card that fetches live data for each account
function LiveAccountCard({
  account,
  onEdit,
  onDelete,
}: {
  account: Account;
  onEdit: (a: Account) => void;
  onDelete: (a: Account) => void;
}) {
  const { t } = useTranslation(['settings', 'common']);
  const { data: liveAccount, isLoading } = useAccount(account.id, {
    enabled: true,
  });
  const a = liveAccount ?? account;

  return (
    <Card>
      <CardActionArea
        component={Link}
        to={`/oanda-accounts/${a.id}`}
        aria-label={`View account ${a.account_id}`}
      >
        <CardContent>
          <Box
            display="flex"
            justifyContent="space-between"
            alignItems="flex-start"
            mb={2}
          >
            <Box display="flex" alignItems="center" gap={1}>
              <Typography variant="h6" component="div" noWrap>
                {a.account_id}
              </Typography>
              {isLoading && <CircularProgress size={14} />}
            </Box>
            <Chip
              label={
                a.api_type === 'practice'
                  ? t('settings:accounts.practice')
                  : t('settings:accounts.live')
              }
              color={a.api_type === 'practice' ? 'default' : 'warning'}
            />
          </Box>
          <Box mb={1}>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.balance')}
            </Typography>
            <Typography variant="h6">
              {formatBalance(a.balance, a.currency)}
            </Typography>
          </Box>
          <Box mb={1}>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.marginUsed')}
            </Typography>
            <Typography variant="body1">
              {formatBalance(a.margin_used, a.currency)}
            </Typography>
          </Box>
          <Box mb={1}>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.marginAvailable')}
            </Typography>
            <Typography variant="body1">
              {formatBalance(a.margin_available, a.currency)}
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
                  parseFloat(a.unrealized_pnl) >= 0
                    ? 'success.main'
                    : 'error.main',
                fontWeight: 500,
              }}
            >
              {parseFloat(a.unrealized_pnl) >= 0 ? '+' : ''}
              {formatBalance(a.unrealized_pnl, a.currency)}
            </Typography>
          </Box>
          <Box mb={1}>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.currency')}
            </Typography>
            <Typography variant="body1">{a.currency}</Typography>
          </Box>
          <Box display="flex" gap={1}>
            <Chip
              label={a.is_active ? 'Active' : 'Inactive'}
              color={a.is_active ? 'success' : 'default'}
            />
            {a.is_default && (
              <Chip label="Default" color="primary" variant="outlined" />
            )}
          </Box>
        </CardContent>
      </CardActionArea>
      <CardActions>
        <IconButton
          color="primary"
          onClick={(e) => {
            e.stopPropagation();
            onEdit(a);
          }}
          aria-label={t('settings:accounts.editAccount')}
        >
          <EditIcon />
        </IconButton>
        <IconButton
          color="error"
          onClick={(e) => {
            e.stopPropagation();
            onDelete(a);
          }}
          aria-label={t('settings:accounts.deleteAccount')}
        >
          <DeleteIcon />
        </IconButton>
      </CardActions>
    </Card>
  );
}

export default function OandaAccountsPage() {
  const { t } = useTranslation(['settings', 'common']);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
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
  });
  const [isDefault, setIsDefault] = useState(false);
  const [formErrors, setFormErrors] = useState<
    Partial<Record<keyof AccountFormData, string>>
  >({});

  const handleAddClick = () => {
    setEditingAccount(null);
    setFormData({ account_id: '', api_token: '', api_type: 'practice' });
    setIsDefault(accounts.length === 0);
    setFormErrors({});
    setShowApiToken(false);
    setDialogOpen(true);
  };

  const handleEditClick = (account: Account) => {
    setEditingAccount(account);
    setFormData({
      account_id: account.account_id,
      api_token: '',
      api_type: account.api_type,
    });
    setIsDefault(account.is_default || false);
    setFormErrors({});
    setShowApiToken(false);
    setDialogOpen(true);
  };

  const handleDialogClose = () => {
    setDialogOpen(false);
    setEditingAccount(null);
    setFormData({ account_id: '', api_token: '', api_type: 'practice' });
    setIsDefault(false);
    setFormErrors({});
  };

  const validateForm = (): boolean => {
    const errors: Partial<AccountFormData> = {};
    if (!formData.account_id.trim()) {
      errors.account_id = t('common:validation.required');
    }
    if (!editingAccount && !formData.api_token.trim()) {
      errors.api_token = t('common:validation.required');
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;
    setSubmitting(true);
    try {
      const payload: Partial<AccountFormData> & { is_default?: boolean } = {
        account_id: formData.account_id,
        api_type: formData.api_type,
        is_default: isDefault,
      };
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
      let message = t('settings:messages.saveError');
      const err = error as Record<string, unknown>;
      if (err.details && typeof err.details === 'object') {
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
        if (messages.length > 0) message = messages.join(' ');
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

  const handleDeleteClick = (account: Account) => {
    setAccountToDelete(account);
    setDeleteConfirmOpen(true);
  };

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

  return (
    <PageContainer sx={{ mt: { xs: 2, sm: 4 }, mb: 4 }}>
      <Breadcrumbs />
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={2}
        gap={1}
      >
        <Typography
          variant="h4"
          sx={{ fontSize: { xs: '1.5rem', sm: '2.125rem' } }}
        >
          {t('settings:accounts.title')}
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, flexShrink: 0, flexWrap: 'wrap' }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() =>
              queryClient.invalidateQueries({ queryKey: ['accounts'] })
            }
          >
            {t('common:actions.refresh')}
          </Button>
          <Button
            variant="contained"
            color="primary"
            startIcon={<AddIcon />}
            onClick={handleAddClick}
          >
            {t('settings:accounts.addAccount')}
          </Button>
        </Box>
      </Box>

      <Alert severity="info" sx={{ mb: 3 }}>
        <Typography variant="body2">
          {t('settings:accounts.defaultAccountInfo')}
        </Typography>
      </Alert>

      {loading && (
        <Box display="flex" justifyContent="center" py={4}>
          <CircularProgress />
        </Box>
      )}

      {accountsError && (
        <Alert severity="error">{t('common:errors.fetchFailed')}</Alert>
      )}

      {!loading && !accountsError && accounts.length === 0 && (
        <Alert severity="info">{t('common:messages.noData')}</Alert>
      )}

      {!loading && accounts.length > 0 && (
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
              <LiveAccountCard
                account={account}
                onEdit={handleEditClick}
                onDelete={handleDeleteClick}
              />
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
                  ? t('settings:accounts.leaveBlankToKeepToken')
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
                    {t('settings:accounts.setAsDefault')}
                  </Typography>
                </label>
              </Box>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mt: 0.5, display: 'block' }}
              >
                {t('settings:accounts.defaultAccountDescription')}
              </Typography>
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDialogClose} disabled={submitting}>
            {t('common:actions.cancel')}
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
              t('common:actions.save')
            ) : (
              t('common:actions.add')
            )}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={deleteConfirmOpen}
        title={t('settings:accounts.deleteAccount')}
        message={t('settings:accounts.confirmDelete')}
        confirmText={t('common:actions.delete')}
        cancelText={t('common:actions.cancel')}
        confirmColor="error"
        onConfirm={handleDeleteConfirm}
        onCancel={() => {
          setDeleteConfirmOpen(false);
          setAccountToDelete(null);
        }}
      />
    </PageContainer>
  );
}
