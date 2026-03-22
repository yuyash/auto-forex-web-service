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
import {
  useUpdateUserSettings,
  useUserSettings,
} from '../../hooks/useUserSettings';
import { logger } from '../../utils/logger';

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
  const { user, token, login } = useAuth();
  const { themeMode, setThemeMode } = useAccessibility();
  const { showSuccess, showError } = useToast();
  const {
    data,
    error: settingsError,
    isLoading: settingsLoading,
  } = useUserSettings({
    enabled: Boolean(token),
  });
  const updateUserSettings = useUpdateUserSettings();

  const [submitting, setSubmitting] = useState(false);
  const [settings, setSettings] = useState<UserSettings>({
    timezone: user?.timezone || 'UTC',
    language: user?.language || 'en',
    notification_enabled: true,
  });

  useEffect(() => {
    if (!data) {
      return;
    }

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
  }, [data, user?.language, user?.timezone]);

  useEffect(() => {
    if (!token || settingsLoading || !settingsError) {
      return;
    }

    logger.error('Error fetching settings', {
      error:
        settingsError instanceof Error
          ? settingsError.message
          : 'Failed to load user settings',
    });
    showError(t('common:errors.fetchFailed'));
  }, [settingsError, settingsLoading, showError, t, token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const data = await updateUserSettings.mutate(settings);
      if (data.user && user && token) {
        login(token, data.user);
      }
      if (settings.language !== i18n.language) {
        await i18n.changeLanguage(settings.language);
      }
      showSuccess(t('settings:messages.saveSuccess'));
    } catch (error) {
      logger.error('Error saving settings', {
        error: error instanceof Error ? error.message : String(error),
      });
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

  if (settingsLoading) {
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
