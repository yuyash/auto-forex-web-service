import {
  Box,
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

const DataSettings = () => {
  const { t } = useTranslation(['settings', 'common']);
  const { settings, updateSetting } = useAppSettings();

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
            value={settings.sessionTimeoutMinutes}
            label={t('settings:data.timeoutDuration')}
            onChange={(e) =>
              updateSetting('sessionTimeoutMinutes', e.target.value as number)
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
            value={settings.healthCheckIntervalSeconds}
            label={t('settings:data.healthCheckInterval')}
            onChange={(e) =>
              updateSetting(
                'healthCheckIntervalSeconds',
                e.target.value as number
              )
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
    </Box>
  );
};

export default DataSettings;
