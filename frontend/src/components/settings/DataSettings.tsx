import { useEffect, useState } from 'react';
import {
  Box,
  Button,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  Divider,
  Alert,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAppSettings } from '../../hooks/useAppSettings';
import { useToast } from '../common';

const DataSettings = () => {
  const { t } = useTranslation(['settings', 'common']);
  const { showError, showSuccess } = useToast();
  const { settings, updateSettings, DEFAULT_APP_SETTINGS } = useAppSettings();
  const [draft, setDraft] = useState(settings);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDraft(settings);
  }, [settings]);

  const handleSave = async () => {
    setSaving(true);
    try {
      updateSettings({
        sessionTimeoutMinutes: draft.sessionTimeoutMinutes,
        healthCheckIntervalSeconds: draft.healthCheckIntervalSeconds,
        taskPollingIntervalSeconds: draft.taskPollingIntervalSeconds,
      });
      showSuccess(t('settings:messages.saveSuccess'));
    } catch (error) {
      showError(
        error instanceof Error
          ? error.message
          : t('settings:messages.saveError')
      );
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    const dataDefaults = {
      sessionTimeoutMinutes: DEFAULT_APP_SETTINGS.sessionTimeoutMinutes,
      healthCheckIntervalSeconds:
        DEFAULT_APP_SETTINGS.healthCheckIntervalSeconds,
      taskPollingIntervalSeconds:
        DEFAULT_APP_SETTINGS.taskPollingIntervalSeconds,
    };
    updateSettings(dataDefaults);
    setDraft((prev) => ({ ...prev, ...dataDefaults }));
    showSuccess(t('common:reset'));
  };

  return (
    <Box>
      {/* Session Timeout */}
      <Typography variant="h6" gutterBottom>
        {t('settings:data.sessionTimeout')}
      </Typography>
      <Box sx={{ mt: 2 }}>
        <FormControl fullWidth margin="normal">
          <InputLabel id="session-timeout-label">
            {t('settings:data.timeoutDuration')}
          </InputLabel>
          <Select
            labelId="session-timeout-label"
            value={draft.sessionTimeoutMinutes}
            label={t('settings:data.timeoutDuration')}
            onChange={(e) =>
              setDraft((prev) => ({
                ...prev,
                sessionTimeoutMinutes: e.target.value as number,
              }))
            }
          >
            <MenuItem value={15}>15 {t('settings:data.minutes')}</MenuItem>
            <MenuItem value={30}>30 {t('settings:data.minutes')}</MenuItem>
            <MenuItem value={60}>60 {t('settings:data.minutes')}</MenuItem>
            <MenuItem value={120}>120 {t('settings:data.minutes')}</MenuItem>
            <MenuItem value={0}>{t('settings:data.never')}</MenuItem>
          </Select>
        </FormControl>
        <Alert severity="info" sx={{ mt: 1 }}>
          {t('settings:data.sessionTimeoutInfo')}
        </Alert>
      </Box>

      <Divider sx={{ my: 3 }} />

      {/* Health Check Interval */}
      <Typography variant="h6" gutterBottom>
        {t('settings:data.dataRefresh')}
      </Typography>
      <Box sx={{ mt: 2 }}>
        <FormControl fullWidth margin="normal">
          <InputLabel id="health-check-interval-label">
            {t('settings:data.healthCheckInterval')}
          </InputLabel>
          <Select
            labelId="health-check-interval-label"
            value={draft.healthCheckIntervalSeconds}
            label={t('settings:data.healthCheckInterval')}
            onChange={(e) =>
              setDraft((prev) => ({
                ...prev,
                healthCheckIntervalSeconds: e.target.value as number,
              }))
            }
          >
            <MenuItem value={10}>10 {t('settings:data.seconds')}</MenuItem>
            <MenuItem value={15}>15 {t('settings:data.seconds')}</MenuItem>
            <MenuItem value={30}>30 {t('settings:data.seconds')}</MenuItem>
            <MenuItem value={60}>60 {t('settings:data.seconds')}</MenuItem>
            <MenuItem value={120}>120 {t('settings:data.seconds')}</MenuItem>
          </Select>
        </FormControl>
        <Alert severity="info" sx={{ mt: 1 }}>
          {t('settings:data.healthCheckInfo')}
        </Alert>
      </Box>

      <Divider sx={{ my: 3 }} />

      {/* Task Polling Interval */}
      <Typography variant="h6" gutterBottom>
        {t('settings:data.taskPolling')}
      </Typography>
      <Box sx={{ mt: 2 }}>
        <FormControl fullWidth margin="normal">
          <InputLabel id="task-polling-interval-label">
            {t('settings:data.taskPollingInterval')}
          </InputLabel>
          <Select
            labelId="task-polling-interval-label"
            value={draft.taskPollingIntervalSeconds}
            label={t('settings:data.taskPollingInterval')}
            onChange={(e) =>
              setDraft((prev) => ({
                ...prev,
                taskPollingIntervalSeconds: e.target.value as number,
              }))
            }
          >
            <MenuItem value={5}>5 {t('settings:data.seconds')}</MenuItem>
            <MenuItem value={10}>10 {t('settings:data.seconds')}</MenuItem>
            <MenuItem value={15}>15 {t('settings:data.seconds')}</MenuItem>
            <MenuItem value={30}>30 {t('settings:data.seconds')}</MenuItem>
            <MenuItem value={60}>60 {t('settings:data.seconds')}</MenuItem>
          </Select>
        </FormControl>
        <Alert severity="info" sx={{ mt: 1 }}>
          {t('settings:data.taskPollingInfo')}
        </Alert>
      </Box>

      <Box
        sx={{
          mt: 3,
          display: 'flex',
          justifyContent: 'flex-end',
          gap: 1.5,
          flexWrap: 'wrap',
        }}
      >
        <Button variant="outlined" onClick={handleReset} disabled={saving}>
          {t('common:reset')}
        </Button>
        <Button variant="contained" onClick={handleSave} disabled={saving}>
          {saving ? <CircularProgress size={20} /> : t('common:save')}
        </Button>
      </Box>
    </Box>
  );
};

export default DataSettings;
