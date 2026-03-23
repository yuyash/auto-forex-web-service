import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  Divider,
  TextField,
  Alert,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAppSettings } from '../../hooks/useAppSettings';
import {
  useSupportedGranularities,
  useSupportedInstruments,
} from '../../hooks/useMarketConfig';
import type { Granularity } from '../../types/chart';

const DisplaySettings = () => {
  const { t } = useTranslation(['settings', 'common']);
  const { settings, updateSetting } = useAppSettings();
  const { instruments, usingFallback: usingInstrumentFallback } =
    useSupportedInstruments();
  const { granularities, usingFallback: usingGranularityFallback } =
    useSupportedGranularities();
  const instrumentOptions = Array.from(
    new Set([settings.defaultInstrument, ...instruments].filter(Boolean))
  );
  const granularityOptions = Array.from(
    new Map(
      [
        {
          value: settings.defaultGranularity,
          label: settings.defaultGranularity,
        },
        ...granularities,
      ].map((granularity) => [granularity.value, granularity])
    ).values()
  );

  return (
    <Box>
      {/* Date & Number Format */}
      <Typography variant="h6" gutterBottom>
        {t('settings:display.dateNumberFormat')}
      </Typography>

      <Box sx={{ mt: 2 }}>
        <FormControl fullWidth margin="normal">
          <InputLabel id="date-format-label">
            {t('settings:display.dateFormat')}
          </InputLabel>
          <Select
            labelId="date-format-label"
            value={settings.dateFormat}
            label={t('settings:display.dateFormat')}
            onChange={(e) =>
              updateSetting(
                'dateFormat',
                e.target.value as 'MM/DD/YYYY' | 'DD/MM/YYYY' | 'YYYY-MM-DD'
              )
            }
          >
            <MenuItem value="YYYY-MM-DD">YYYY-MM-DD (2026-03-07)</MenuItem>
            <MenuItem value="MM/DD/YYYY">MM/DD/YYYY (03/07/2026)</MenuItem>
            <MenuItem value="DD/MM/YYYY">DD/MM/YYYY (07/03/2026)</MenuItem>
          </Select>
        </FormControl>

        <FormControl fullWidth margin="normal">
          <InputLabel id="decimal-separator-label">
            {t('settings:display.decimalSeparator')}
          </InputLabel>
          <Select
            labelId="decimal-separator-label"
            value={settings.decimalSeparator}
            label={t('settings:display.decimalSeparator')}
            onChange={(e) =>
              updateSetting('decimalSeparator', e.target.value as '.' | ',')
            }
          >
            <MenuItem value=".">. (1,234.56)</MenuItem>
            <MenuItem value=",">, (1.234,56)</MenuItem>
          </Select>
        </FormControl>

        <FormControl fullWidth margin="normal">
          <InputLabel id="thousands-separator-label">
            {t('settings:display.thousandsSeparator')}
          </InputLabel>
          <Select
            labelId="thousands-separator-label"
            value={settings.thousandsSeparator}
            label={t('settings:display.thousandsSeparator')}
            onChange={(e) =>
              updateSetting(
                'thousandsSeparator',
                e.target.value as ',' | '.' | ' ' | ''
              )
            }
          >
            <MenuItem value=",">, (1,234)</MenuItem>
            <MenuItem value=".">. (1.234)</MenuItem>
            <MenuItem value=" ">{t('settings:display.space')} (1 234)</MenuItem>
            <MenuItem value="">{t('settings:display.none')} (1234)</MenuItem>
          </Select>
        </FormControl>
      </Box>

      <Divider sx={{ my: 3 }} />

      {/* Default Instrument */}
      <Typography variant="h6" gutterBottom>
        {t('settings:display.defaultInstrument')}
      </Typography>
      <Box sx={{ mt: 2 }}>
        {usingInstrumentFallback && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {t('common:tables.trend.instrumentFallbackWarning')}
          </Alert>
        )}
        <FormControl fullWidth margin="normal">
          <InputLabel id="default-instrument-label">
            {t('settings:display.currencyPair')}
          </InputLabel>
          <Select
            labelId="default-instrument-label"
            value={settings.defaultInstrument}
            label={t('settings:display.currencyPair')}
            onChange={(e) => updateSetting('defaultInstrument', e.target.value)}
          >
            {instrumentOptions.map((inst) => (
              <MenuItem key={inst} value={inst}>
                {inst.replace('_', '/')}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {usingGranularityFallback && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            {t('common:tables.trend.granularityFallbackWarning')}
          </Alert>
        )}
        <FormControl fullWidth margin="normal">
          <InputLabel id="default-granularity-label">
            {t('settings:display.defaultGranularity')}
          </InputLabel>
          <Select
            labelId="default-granularity-label"
            value={settings.defaultGranularity}
            label={t('settings:display.defaultGranularity')}
            onChange={(e) =>
              updateSetting('defaultGranularity', e.target.value as Granularity)
            }
          >
            {granularityOptions.map((g) => (
              <MenuItem key={g.value} value={g.value}>
                {g.value} - {g.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      <Divider sx={{ my: 3 }} />

      {/* Candle Colors */}
      <Typography variant="h6" gutterBottom>
        {t('settings:display.chartAppearance')}
      </Typography>
      <Box sx={{ mt: 2, display: 'flex', gap: 3, flexWrap: 'wrap' }}>
        <TextField
          label={t('settings:display.candleUpColor')}
          type="color"
          value={settings.candleUpColor}
          onChange={(e) => updateSetting('candleUpColor', e.target.value)}
          sx={{ width: { xs: '100%', sm: 200 } }}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          label={t('settings:display.candleDownColor')}
          type="color"
          value={settings.candleDownColor}
          onChange={(e) => updateSetting('candleDownColor', e.target.value)}
          sx={{ width: { xs: '100%', sm: 200 } }}
          slotProps={{ inputLabel: { shrink: true } }}
        />
      </Box>

      <Alert severity="info" sx={{ mt: 3 }}>
        {t('settings:display.info')}
      </Alert>
    </Box>
  );
};

export default DisplaySettings;
