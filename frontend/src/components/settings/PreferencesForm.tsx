import { useState, useEffect } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
  Button,
  CircularProgress,
  Alert,
  Typography,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../common/useToast';

// Common IANA timezones
const TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Toronto',
  'America/Vancouver',
  'America/Mexico_City',
  'America/Sao_Paulo',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Europe/Rome',
  'Europe/Madrid',
  'Europe/Amsterdam',
  'Europe/Brussels',
  'Europe/Vienna',
  'Europe/Stockholm',
  'Europe/Moscow',
  'Asia/Tokyo',
  'Asia/Seoul',
  'Asia/Shanghai',
  'Asia/Hong_Kong',
  'Asia/Singapore',
  'Asia/Bangkok',
  'Asia/Dubai',
  'Asia/Kolkata',
  'Australia/Sydney',
  'Australia/Melbourne',
  'Australia/Brisbane',
  'Pacific/Auckland',
];

interface UserSettings {
  timezone: string;
  language: string;
  notification_enabled: boolean;
}

const PreferencesForm = () => {
  const { t, i18n } = useTranslation(['settings', 'common']);
  const { token, user, login } = useAuth();
  const { showSuccess, showError } = useToast();

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [settings, setSettings] = useState<UserSettings>({
    timezone: user?.timezone || 'UTC',
    language: user?.language || 'en',
    notification_enabled: true,
  });

  // Fetch current settings
  const fetchSettings = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/accounts/settings/', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch settings');
      }

      const data = await response.json();
      const userData =
        data && typeof data === 'object' && 'user' in data
          ? (data as { user?: Partial<UserSettings> }).user
          : undefined;
      const settingsData =
        data && typeof data === 'object' && 'settings' in data
          ? (data as { settings?: Partial<UserSettings> }).settings
          : undefined;
      setSettings({
        timezone:
          (userData as { timezone?: string } | undefined)?.timezone ||
          user?.timezone ||
          'UTC',
        language:
          (userData as { language?: string } | undefined)?.language ||
          user?.language ||
          'en',
        notification_enabled:
          (settingsData as { notification_enabled?: boolean } | undefined)
            ?.notification_enabled ?? true,
      });
    } catch (error) {
      console.error('Error fetching settings:', error);
      showError(t('common:errors.fetchFailed', 'Failed to load data'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    setSubmitting(true);

    try {
      const response = await fetch('/api/accounts/settings/', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(settings),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Failed to save settings');
      }

      const data = await response.json();

      // Update user in auth context if user data is returned
      if (data.user && user && token) {
        login(token, data.user);
      }

      // Update i18n language if it changed
      if (settings.language !== i18n.language) {
        await i18n.changeLanguage(settings.language);
      }

      showSuccess(
        t('settings:messages.saveSuccess', 'Settings saved successfully')
      );
    } catch (error) {
      console.error('Error saving settings:', error);
      showError(
        error instanceof Error
          ? error.message
          : t('settings:messages.saveError', 'Failed to save settings')
      );
    } finally {
      setSubmitting(false);
    }
  };

  // Handle timezone change
  const handleTimezoneChange = (value: string) => {
    setSettings({ ...settings, timezone: value });
  };

  // Handle language change
  const handleLanguageChange = (value: string) => {
    setSettings({ ...settings, language: value });
  };

  // Handle notification toggle
  const handleNotificationToggle = (checked: boolean) => {
    setSettings({ ...settings, notification_enabled: checked });
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" py={4}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box component="form" onSubmit={handleSubmit}>
      <Typography variant="h6" gutterBottom>
        {t('settings:preferences.title', 'User Preferences')}
      </Typography>

      <Box sx={{ mt: 3 }}>
        {/* Timezone Selector */}
        <FormControl fullWidth margin="normal">
          <InputLabel id="timezone-label">
            {t('settings:preferences.timezone', 'Timezone')}
          </InputLabel>
          <Select
            labelId="timezone-label"
            value={settings.timezone}
            label={t('settings:preferences.timezone', 'Timezone')}
            onChange={(e) => handleTimezoneChange(e.target.value)}
          >
            {TIMEZONES.map((tz) => (
              <MenuItem key={tz} value={tz}>
                {tz}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Language Selector */}
        <FormControl fullWidth margin="normal">
          <InputLabel id="language-label">
            {t('settings:preferences.language', 'Language')}
          </InputLabel>
          <Select
            labelId="language-label"
            value={settings.language}
            label={t('settings:preferences.language', 'Language')}
            onChange={(e) => handleLanguageChange(e.target.value)}
          >
            <MenuItem value="en">English</MenuItem>
            <MenuItem value="ja">日本語 (Japanese)</MenuItem>
          </Select>
        </FormControl>

        {/* Notification Preferences */}
        <Box sx={{ mt: 3, mb: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            {t('settings:preferences.notifications', 'Notifications')}
          </Typography>

          <FormControlLabel
            control={
              <Switch
                checked={settings.notification_enabled}
                onChange={(e) => handleNotificationToggle(e.target.checked)}
                color="primary"
              />
            }
            label={t(
              'settings:preferences.enableNotifications',
              'Enable Notifications'
            )}
          />
        </Box>

        {/* Info Alert */}
        <Alert severity="info" sx={{ mt: 2, mb: 3 }}>
          {t(
            'settings:preferences.timezoneInfo',
            'Changing your timezone will affect how timestamps are displayed throughout the application.'
          )}
        </Alert>

        {/* Submit Button */}
        <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={submitting}
            sx={{ minWidth: 120 }}
          >
            {submitting ? (
              <CircularProgress size={24} />
            ) : (
              t('common:save', 'Save')
            )}
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

export default PreferencesForm;
