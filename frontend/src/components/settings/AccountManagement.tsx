import { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
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
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../common/useToast';
import ConfirmDialog from '../common/ConfirmDialog';
import PositionDifferentiationDialog from './PositionDifferentiationDialog';
import type { Account } from '../../types/strategy';

interface AccountFormData {
  account_id: string;
  api_token: string;
  api_type: 'practice' | 'live';
}

const AccountManagement = () => {
  const { t } = useTranslation(['settings', 'common']);
  const { token } = useAuth();
  const { showSuccess, showError } = useToast();

  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [accountToDelete, setAccountToDelete] = useState<Account | null>(null);
  const [showApiToken, setShowApiToken] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [positionDiffDialogOpen, setPositionDiffDialogOpen] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState<Account | null>(null);

  const [formData, setFormData] = useState<AccountFormData>({
    account_id: '',
    api_token: '',
    api_type: 'practice',
  });

  const [formErrors, setFormErrors] = useState<Partial<AccountFormData>>({});

  // Fetch accounts
  const fetchAccounts = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/accounts/', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch accounts');
      }

      const data = await response.json();
      setAccounts(data);
    } catch (error) {
      console.error('Error fetching accounts:', error);
      showError(t('common:errors.fetchFailed', 'Failed to load data'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // Open dialog for adding new account
  const handleAddClick = () => {
    setEditingAccount(null);
    setFormData({
      account_id: '',
      api_token: '',
      api_type: 'practice',
    });
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
      const url = editingAccount
        ? `/api/accounts/${editingAccount.id}/`
        : '/api/accounts/';
      const method = editingAccount ? 'PUT' : 'POST';

      // Only include api_token if it's provided
      const payload: Partial<AccountFormData> = {
        account_id: formData.account_id,
        api_type: formData.api_type,
      };

      if (formData.api_token.trim()) {
        payload.api_token = formData.api_token;
      }

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Failed to save account');
      }

      showSuccess(
        t('settings:messages.accountAdded', 'Account saved successfully')
      );
      handleDialogClose();
      fetchAccounts();
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
      const response = await fetch(`/api/accounts/${accountToDelete.id}/`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to delete account');
      }

      showSuccess(
        t('settings:messages.accountDeleted', 'Account deleted successfully')
      );
      setDeleteConfirmOpen(false);
      setAccountToDelete(null);
      fetchAccounts();
    } catch (error) {
      console.error('Error deleting account:', error);
      showError(t('common:errors.deleteFailed', 'Failed to delete'));
    }
  };

  // Open position differentiation dialog
  const handlePositionDiffClick = (account: Account) => {
    setSelectedAccount(account);
    setPositionDiffDialogOpen(true);
  };

  // Close position differentiation dialog
  const handlePositionDiffClose = () => {
    setPositionDiffDialogOpen(false);
    setSelectedAccount(null);
  };

  // Handle position differentiation save
  const handlePositionDiffSave = () => {
    fetchAccounts();
  };

  // Format balance
  const formatBalance = (balance: number, currency: string) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(balance);
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
        mb={3}
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
                        account.api_type === 'practice' ? 'default' : 'warning'
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
                      {t('settings:accounts.currency', 'Currency')}
                    </Typography>
                    <Typography variant="body1">{account.currency}</Typography>
                  </Box>

                  <Box>
                    <Chip
                      label={account.is_active ? 'Active' : 'Inactive'}
                      color={account.is_active ? 'success' : 'default'}
                      size="small"
                    />
                  </Box>
                </CardContent>
                <CardActions>
                  <IconButton
                    size="small"
                    color="primary"
                    onClick={() => handleEditClick(account)}
                    aria-label={t(
                      'settings:accounts.editAccount',
                      'Edit Account'
                    )}
                  >
                    <EditIcon />
                  </IconButton>
                  <IconButton
                    size="small"
                    color="secondary"
                    onClick={() => handlePositionDiffClick(account)}
                    aria-label={t(
                      'settings:accounts.positionDifferentiation',
                      'Position Differentiation'
                    )}
                  >
                    <SettingsIcon />
                  </IconButton>
                  <IconButton
                    size="small"
                    color="error"
                    onClick={() => handleDeleteClick(account)}
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

      {/* Position Differentiation Dialog */}
      {selectedAccount && (
        <PositionDifferentiationDialog
          open={positionDiffDialogOpen}
          account={selectedAccount}
          onClose={handlePositionDiffClose}
          onSave={handlePositionDiffSave}
        />
      )}
    </Box>
  );
};

export default AccountManagement;
