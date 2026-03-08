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
  Divider,
  ToggleButtonGroup,
  ToggleButton,
} from '@mui/material';
import { LightMode, DarkMode, SettingsBrightness } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { useAccessibility } from '../../hooks/useAccessibility';
import { useToast } from '../common/useToast';
import type { ThemeMode } from '../../contexts/AccessibilityContextDefinition';

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

const GeneralSettings = () => {
  const { t, i18n } = useTranslation(['settings', 'common']);
  const { token, user, login } = useAuth();
  const { themeMode, setThemeMode } = useAccessibility();
  const { showSuccess, showError } = useToast();

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [settings, setSettings] = useState<UserSettings>({
    timezone: user?.timezone || 'UTC',
    language: user?.language || 'en',
    notification_enabled: true,
  });

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/accounts/settings/', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to fetch settings');
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
      showError(t('common:errors.fetchFailed'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

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
      if (data.user && user && token) {
        const currentRefreshToken = localStorage.getItem('refresh_token') || '';
        login(token, currentRefreshToken, data.user);
      }
      if (settings.language !== i18n.language) {
        await i18n.changeLanguage(settings.language);
      }
      showSuccess(t('settings:messages.saveSuccess'));
    } catch (error) {
      console.error('Error saving settings:', error);
      showError(
        error instanceof Error
          ? error.message
          : t('settings:messages.saveError')
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleThemeModeChange = (
    _event: React.MouseEvent<HTMLElement>,
    newMode: ThemeMode | null
  ) => {
    if (newMode !== null) {
      setThemeMode(newMode);
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
    <Box component="form" onSubmit={handleSubmit}>
      {/* Theme Section */}
      <Typography variant="h6" gutterBottom>
        {t('settings:preferences.theme')}
      </Typography>
      <Box sx={{ mb: 3 }}>
        <ToggleButtonGroup
          value={themeMode}
          exclusive
          onChange={handleThemeModeChange}
          aria-label={t('settings:preferences.theme')}
          size="small"
        >
          <ToggleButton
            value="light"
            aria-label={t('settings:preferences.lightMode')}
          >
            <LightMode sx={{ mr: 1 }} />
            {t('settings:preferences.lightMode')}
          </ToggleButton>
          <ToggleButton
            value="dark"
            aria-label={t('settings:preferences.darkMode')}
          >
            <DarkMode sx={{ mr: 1 }} />
            {t('settings:preferences.darkMode')}
          </ToggleButton>
          <ToggleButton
            value="system"
            aria-label={t('settings:preferences.autoMode')}
          >
            <SettingsBrightness sx={{ mr: 1 }} />
            {t('settings:preferences.autoMode')}
          </ToggleButton>
        </ToggleButtonGroup>
      </Box>

      <Divider sx={{ my: 3 }} />

      {/* Language & Timezone Section */}
      <Typography variant="h6" gutterBottom>
        {t('settings:preferences.title')}
      </Typography>
      <Box sx={{ mt: 2 }}>
        <FormControl fullWidth margin="normal">
          <InputLabel id="timezone-label">
            {t('settings:preferences.timezone')}
          </InputLabel>
          <Select
            labelId="timezone-label"
            value={settings.timezone}
            label={t('settings:preferences.timezone')}
            onChange={(e) =>
              setSettings({ ...settings, timezone: e.target.value })
            }
          >
            {TIMEZONES.map((tz) => (
              <MenuItem key={tz} value={tz}>
                {tz}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl fullWidth margin="normal">
          <InputLabel id="language-label">
            {t('settings:preferences.language')}
          </InputLabel>
          <Select
            labelId="language-label"
            value={settings.language}
            label={t('settings:preferences.language')}
            onChange={(e) =>
              setSettings({ ...settings, language: e.target.value })
            }
          >
            <MenuItem value="en">English</MenuItem>
            <MenuItem value="ja">日本語 (Japanese)</MenuItem>
          </Select>
        </FormControl>

        <Box sx={{ mt: 3, mb: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            {t('settings:preferences.notifications')}
          </Typography>
          <FormControlLabel
            control={
              <Switch
                checked={settings.notification_enabled}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    notification_enabled: e.target.checked,
                  })
                }
                color="primary"
              />
            }
            label={t('settings:preferences.enableNotifications')}
          />
        </Box>

        <Alert severity="info" sx={{ mt: 2, mb: 3 }}>
          {t('settings:preferences.timezoneInfo')}
        </Alert>

        <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={submitting}
            sx={{ minWidth: 120 }}
          >
            {submitting ? <CircularProgress size={24} /> : t('common:save')}
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

export default GeneralSettings;
