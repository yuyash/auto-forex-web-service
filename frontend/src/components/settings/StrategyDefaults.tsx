import { useState, useEffect } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Button,
  CircularProgress,
  Alert,
  Typography,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../common/useToast';

interface StrategyDefaultSettings {
  default_lot_size: number;
  default_scaling_mode: string;
  default_retracement_pips: number;
  default_take_profit_pips: number;
}

const StrategyDefaults = () => {
  const { t } = useTranslation(['settings', 'common']);
  const { token } = useAuth();
  const { showSuccess, showError } = useToast();

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [settings, setSettings] = useState<StrategyDefaultSettings>({
    default_lot_size: 1.0,
    default_scaling_mode: 'additive',
    default_retracement_pips: 30,
    default_take_profit_pips: 25,
  });
  const [errors, setErrors] = useState<
    Partial<Record<keyof StrategyDefaultSettings, string>>
  >({});

  // Fetch current settings
  const fetchSettings = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/settings', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch settings');
      }

      const data = await response.json();
      setSettings({
        default_lot_size: data.default_lot_size ?? 1.0,
        default_scaling_mode: data.default_scaling_mode ?? 'additive',
        default_retracement_pips: data.default_retracement_pips ?? 30,
        default_take_profit_pips: data.default_take_profit_pips ?? 25,
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

  // Validate form fields
  const validateForm = (): boolean => {
    const newErrors: Partial<Record<keyof StrategyDefaultSettings, string>> =
      {};

    if (settings.default_lot_size <= 0) {
      newErrors.default_lot_size = t(
        'common:errors.mustBePositive',
        'Must be a positive number'
      );
    }

    if (settings.default_retracement_pips <= 0) {
      newErrors.default_retracement_pips = t(
        'common:errors.mustBePositive',
        'Must be a positive number'
      );
    }

    if (settings.default_take_profit_pips <= 0) {
      newErrors.default_take_profit_pips = t(
        'common:errors.mustBePositive',
        'Must be a positive number'
      );
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setSubmitting(true);

    try {
      const response = await fetch('/api/settings', {
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

  // Handle lot size change
  const handleLotSizeChange = (value: string) => {
    const numValue = parseFloat(value);
    if (!isNaN(numValue)) {
      setSettings({ ...settings, default_lot_size: numValue });
      if (errors.default_lot_size) {
        setErrors({ ...errors, default_lot_size: undefined });
      }
    }
  };

  // Handle retracement mode change
  const handleScalingModeChange = (value: string) => {
    setSettings({ ...settings, default_scaling_mode: value });
  };

  // Handle retracement pips change
  const handleRetracementPipsChange = (value: string) => {
    const numValue = parseInt(value, 10);
    if (!isNaN(numValue)) {
      setSettings({ ...settings, default_retracement_pips: numValue });
      if (errors.default_retracement_pips) {
        setErrors({ ...errors, default_retracement_pips: undefined });
      }
    }
  };

  // Handle take profit pips change
  const handleTakeProfitPipsChange = (value: string) => {
    const numValue = parseInt(value, 10);
    if (!isNaN(numValue)) {
      setSettings({ ...settings, default_take_profit_pips: numValue });
      if (errors.default_take_profit_pips) {
        setErrors({ ...errors, default_take_profit_pips: undefined });
      }
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
      <Typography variant="h6" gutterBottom>
        {t('settings:strategyDefaults.title', 'Strategy Defaults')}
      </Typography>

      <Box sx={{ mt: 3 }}>
        {/* Default Lot Size */}
        <TextField
          fullWidth
          margin="normal"
          label={t(
            'settings:strategyDefaults.defaultLotSize',
            'Default Lot Size'
          )}
          type="number"
          value={settings.default_lot_size}
          onChange={(e) => handleLotSizeChange(e.target.value)}
          error={!!errors.default_lot_size}
          helperText={errors.default_lot_size}
          inputProps={{
            step: 0.01,
            min: 0.01,
          }}
        />

        {/* Default Retracement Mode */}
        <FormControl fullWidth margin="normal">
          <InputLabel id="scaling-mode-label">
            {t(
              'settings:strategyDefaults.defaultScalingMode',
              'Default Retracement Mode'
            )}
          </InputLabel>
          <Select
            labelId="scaling-mode-label"
            value={settings.default_scaling_mode}
            label={t(
              'settings:strategyDefaults.defaultScalingMode',
              'Default Retracement Mode'
            )}
            onChange={(e) => handleScalingModeChange(e.target.value)}
          >
            <MenuItem value="additive">Additive</MenuItem>
            <MenuItem value="multiplicative">Multiplicative</MenuItem>
          </Select>
        </FormControl>

        {/* Default Retracement Pips */}
        <TextField
          fullWidth
          margin="normal"
          label={t(
            'settings:strategyDefaults.defaultRetracementPips',
            'Default Retracement (Pips)'
          )}
          type="number"
          value={settings.default_retracement_pips}
          onChange={(e) => handleRetracementPipsChange(e.target.value)}
          error={!!errors.default_retracement_pips}
          helperText={errors.default_retracement_pips}
          inputProps={{
            step: 1,
            min: 1,
          }}
        />

        {/* Default Take Profit Pips */}
        <TextField
          fullWidth
          margin="normal"
          label={t(
            'settings:strategyDefaults.defaultTakeProfitPips',
            'Default Take Profit (Pips)'
          )}
          type="number"
          value={settings.default_take_profit_pips}
          onChange={(e) => handleTakeProfitPipsChange(e.target.value)}
          error={!!errors.default_take_profit_pips}
          helperText={errors.default_take_profit_pips}
          inputProps={{
            step: 1,
            min: 1,
          }}
        />

        {/* Info Alert */}
        <Alert severity="info" sx={{ mt: 2, mb: 3 }}>
          {t(
            'settings:strategyDefaults.info',
            'These default values will be used when creating new trading strategies. You can override them for individual strategies.'
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

export default StrategyDefaults;
