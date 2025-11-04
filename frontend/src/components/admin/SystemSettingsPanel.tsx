import React, { useState, useEffect } from 'react';
import {
  Paper,
  Typography,
  Box,
  Switch,
  FormControlLabel,
  Button,
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import type { SystemSettings } from '../../types/admin';

const SystemSettingsPanel: React.FC = () => {
  const { t } = useTranslation('admin');
  const { token } = useAuth();
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showLoginWarning, setShowLoginWarning] = useState(false);
  const [pendingSettings, setPendingSettings] =
    useState<Partial<SystemSettings> | null>(null);

  // Fetch current settings
  useEffect(() => {
    const fetchSettings = async () => {
      if (!token) return;

      try {
        const response = await fetch('/api/admin/system/settings', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          throw new Error('Failed to fetch system settings');
        }

        const data = await response.json();
        setSettings(data);
        setError(null);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to load system settings'
        );
      } finally {
        setLoading(false);
      }
    };

    fetchSettings();
  }, [token]);

  // Handle toggle change
  const handleToggleChange =
    (field: keyof SystemSettings) =>
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = event.target.checked;

      // Show warning dialog if disabling login
      if (field === 'login_enabled' && !newValue) {
        setPendingSettings({ [field]: newValue });
        setShowLoginWarning(true);
        return;
      }

      // Update settings immediately for other fields
      setSettings((prev) => (prev ? { ...prev, [field]: newValue } : null));
    };

  // Confirm login disable
  const handleConfirmLoginDisable = () => {
    if (pendingSettings) {
      setSettings((prev) => (prev ? { ...prev, ...pendingSettings } : null));
    }
    setShowLoginWarning(false);
    setPendingSettings(null);
  };

  // Cancel login disable
  const handleCancelLoginDisable = () => {
    setShowLoginWarning(false);
    setPendingSettings(null);
  };

  // Save settings
  const handleSave = async () => {
    if (!token || !settings) return;

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetch('/api/admin/system/settings', {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          registration_enabled: settings.registration_enabled,
          login_enabled: settings.login_enabled,
          email_whitelist_enabled: settings.email_whitelist_enabled,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to update system settings');
      }

      const data = await response.json();
      setSettings(data);
      setSuccess('System settings updated successfully');

      // Clear success message after 5 seconds
      setTimeout(() => setSuccess(null), 5000);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to update system settings'
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Paper elevation={2} sx={{ p: 3 }}>
        <Box
          display="flex"
          justifyContent="center"
          alignItems="center"
          minHeight="200px"
        >
          <CircularProgress />
        </Box>
      </Paper>
    );
  }

  if (error && !settings) {
    return (
      <Paper elevation={2} sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Paper>
    );
  }

  if (!settings) {
    return (
      <Paper elevation={2} sx={{ p: 3 }}>
        <Alert severity="info">No system settings available</Alert>
      </Paper>
    );
  }

  return (
    <>
      <Paper elevation={2} sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          {t('settings.title')}
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {success && (
          <Alert severity="success" sx={{ mb: 2 }}>
            {success}
          </Alert>
        )}

        <Box sx={{ mt: 3 }}>
          <FormControlLabel
            control={
              <Switch
                checked={settings.registration_enabled}
                onChange={handleToggleChange('registration_enabled')}
                disabled={saving}
              />
            }
            label={t('settings.registrationEnabled')}
          />
          <Typography
            variant="caption"
            display="block"
            color="text.secondary"
            sx={{ ml: 4, mb: 2 }}
          >
            Allow new users to register accounts
          </Typography>

          <FormControlLabel
            control={
              <Switch
                checked={settings.login_enabled}
                onChange={handleToggleChange('login_enabled')}
                disabled={saving}
              />
            }
            label={t('settings.loginEnabled')}
          />
          <Typography
            variant="caption"
            display="block"
            color="text.secondary"
            sx={{ ml: 4, mb: 2 }}
          >
            Allow users to log in to the system
          </Typography>

          <FormControlLabel
            control={
              <Switch
                checked={settings.email_whitelist_enabled}
                onChange={handleToggleChange('email_whitelist_enabled')}
                disabled={saving}
              />
            }
            label="Email Whitelist Enabled"
          />
          <Typography
            variant="caption"
            display="block"
            color="text.secondary"
            sx={{ ml: 4, mb: 2 }}
          >
            Only allow registration from whitelisted email addresses
          </Typography>
        </Box>

        <Box
          sx={{
            mt: 3,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Box>
            <Typography variant="caption" color="text.secondary">
              Last updated: {new Date(settings.last_updated).toLocaleString()}
            </Typography>
            <Typography
              variant="caption"
              display="block"
              color="text.secondary"
            >
              Updated by: {settings.updated_by}
            </Typography>
          </Box>
          <Button
            variant="contained"
            color="primary"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? <CircularProgress size={24} /> : t('settings.save')}
          </Button>
        </Box>
      </Paper>

      {/* Login Disable Warning Dialog */}
      <Dialog
        open={showLoginWarning}
        onClose={handleCancelLoginDisable}
        aria-labelledby="login-warning-dialog-title"
        aria-describedby="login-warning-dialog-description"
      >
        <DialogTitle id="login-warning-dialog-title">
          Warning: Disable Login
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="login-warning-dialog-description">
            Are you sure you want to disable login? This will prevent all users
            (including yourself) from logging in to the system. Existing
            logged-in users will remain active until their sessions expire.
            <br />
            <br />
            <strong>
              Make sure you have another way to re-enable login before
              proceeding.
            </strong>
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancelLoginDisable} color="primary">
            {t('common.cancel')}
          </Button>
          <Button onClick={handleConfirmLoginDisable} color="error" autoFocus>
            Disable Login
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default SystemSettingsPanel;
