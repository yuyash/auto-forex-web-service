import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Box,
  CircularProgress,
  IconButton,
  Alert,
} from '@mui/material';
import { Visibility, VisibilityOff } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';

interface AccountFormData {
  account_id: string;
  api_token: string;
  api_type: 'practice' | 'live';
}

interface AddAccountModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  token: string;
}

const AddAccountModal = ({
  open,
  onClose,
  onSuccess,
  token,
}: AddAccountModalProps) => {
  const { t } = useTranslation(['settings', 'common']);

  const [formData, setFormData] = useState<AccountFormData>({
    account_id: '',
    api_token: '',
    api_type: 'practice',
  });

  const [formErrors, setFormErrors] = useState<Partial<AccountFormData>>({});
  const [showApiToken, setShowApiToken] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form when modal opens
  useEffect(() => {
    if (open) {
      setFormData({
        account_id: '',
        api_token: '',
        api_type: 'practice',
      });
      setFormErrors({});
      setShowApiToken(false);
      setError(null);
    }
  }, [open]);

  // Reset form when modal opens/closes
  const handleClose = () => {
    setFormData({
      account_id: '',
      api_token: '',
      api_type: 'practice',
    });
    setFormErrors({});
    setShowApiToken(false);
    setError(null);
    onClose();
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

    if (!formData.api_token.trim()) {
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
    setError(null);

    try {
      const response = await fetch('/api/accounts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          errorData.message || errorData.error || 'Failed to add account'
        );
      }

      // Success
      onSuccess();
      handleClose();
    } catch (err) {
      console.error('Error adding account:', err);
      setError(
        err instanceof Error
          ? err.message
          : t('settings:messages.saveError', 'Failed to save account')
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {t('settings:accounts.addAccount', 'Add Account')}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ pt: 2 }}>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

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
            disabled={submitting}
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
            helperText={formErrors.api_token}
            margin="normal"
            required
            disabled={submitting}
            slotProps={{
              input: {
                endAdornment: (
                  <IconButton
                    onClick={() => setShowApiToken(!showApiToken)}
                    edge="end"
                    disabled={submitting}
                    aria-label={
                      showApiToken
                        ? t('common:hidePassword', 'Hide password')
                        : t('common:showPassword', 'Show password')
                    }
                  >
                    {showApiToken ? <VisibilityOff /> : <Visibility />}
                  </IconButton>
                ),
              },
            }}
          />

          <FormControl fullWidth margin="normal" disabled={submitting}>
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
        <Button onClick={handleClose} disabled={submitting}>
          {t('common:cancel', 'Cancel')}
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          color="primary"
          disabled={submitting}
        >
          {submitting ? <CircularProgress size={24} /> : t('common:add', 'Add')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default AddAccountModal;
