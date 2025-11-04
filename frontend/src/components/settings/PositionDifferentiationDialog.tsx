import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControlLabel,
  Switch,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Typography,
  Alert,
  CircularProgress,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../common/useToast';
import type {
  Account,
  PositionDifferentiationSettings,
} from '../../types/strategy';

interface PositionDifferentiationDialogProps {
  open: boolean;
  account: Account;
  onClose: () => void;
  onSave: () => void;
}

const PositionDifferentiationDialog = ({
  open,
  account,
  onClose,
  onSave,
}: PositionDifferentiationDialogProps) => {
  const { t } = useTranslation(['settings', 'common']);
  const { token } = useAuth();
  const { showSuccess, showError } = useToast();

  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [settings, setSettings] = useState<PositionDifferentiationSettings>({
    enable_position_differentiation: false,
    position_diff_increment: 1,
    position_diff_pattern: 'increment',
  });
  const [baseSize] = useState(5000); // Example base size for preview

  // Fetch current settings
  useEffect(() => {
    if (open && account.id) {
      fetchSettings();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, account.id]);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `/api/accounts/${account.id}/position-diff`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to fetch position differentiation settings');
      }

      const data = await response.json();
      setSettings({
        enable_position_differentiation:
          data.enable_position_differentiation || false,
        position_diff_increment: data.position_diff_increment || 1,
        position_diff_pattern: data.position_diff_pattern || 'increment',
      });
    } catch (error) {
      console.error('Error fetching settings:', error);
      // Use default values if fetch fails
      setSettings({
        enable_position_differentiation:
          account.enable_position_differentiation || false,
        position_diff_increment: account.position_diff_increment || 1,
        position_diff_pattern: account.position_diff_pattern || 'increment',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSubmitting(true);
      const response = await fetch(
        `/api/accounts/${account.id}/position-diff`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(settings),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Failed to save settings');
      }

      showSuccess(
        t('settings:messages.saveSuccess', 'Settings saved successfully')
      );
      onSave();
      onClose();
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

  // Calculate next order size preview
  const getNextOrderSize = (): number => {
    if (!settings.enable_position_differentiation) {
      return baseSize;
    }

    const increment = settings.position_diff_increment;
    switch (settings.position_diff_pattern) {
      case 'increment':
        return baseSize + increment;
      case 'decrement':
        return baseSize - increment;
      case 'alternating':
        return baseSize + increment; // First alternation
      default:
        return baseSize;
    }
  };

  // Get pattern description
  const getPatternDescription = (): string => {
    const increment = settings.position_diff_increment;
    switch (settings.position_diff_pattern) {
      case 'increment':
        return `${baseSize}, ${baseSize + increment}, ${baseSize + increment * 2}, ${baseSize + increment * 3}...`;
      case 'decrement':
        return `${baseSize}, ${baseSize - increment}, ${baseSize - increment * 2}, ${baseSize - increment * 3}...`;
      case 'alternating':
        return `${baseSize}, ${baseSize + increment}, ${baseSize - increment}, ${baseSize + increment * 2}...`;
      default:
        return '';
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {t(
          'settings:accounts.positionDifferentiation',
          'Position Differentiation'
        )}
      </DialogTitle>
      <DialogContent>
        {loading ? (
          <Box display="flex" justifyContent="center" py={4}>
            <CircularProgress />
          </Box>
        ) : (
          <Box sx={{ pt: 2 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.enable_position_differentiation}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      enable_position_differentiation: e.target.checked,
                    })
                  }
                />
              }
              label={t(
                'settings:accounts.enablePositionDiff',
                'Enable Position Differentiation'
              )}
            />

            <Alert severity="info" sx={{ mt: 2, mb: 2 }}>
              {t(
                'settings:accounts.positionDiffExplanation',
                'Makes each position unique to allow selective closing'
              )}
            </Alert>

            {account.jurisdiction === 'US' && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                {t(
                  'settings:accounts.positionDiffWarningUS',
                  'Recommended for FIFO compliance flexibility'
                )}
              </Alert>
            )}

            {settings.enable_position_differentiation && (
              <>
                <TextField
                  fullWidth
                  type="number"
                  label={t(
                    'settings:accounts.incrementAmount',
                    'Increment Amount'
                  )}
                  value={settings.position_diff_increment}
                  onChange={(e) => {
                    const value = parseInt(e.target.value, 10);
                    if (value >= 1 && value <= 100) {
                      setSettings({
                        ...settings,
                        position_diff_increment: value,
                      });
                    }
                  }}
                  helperText={t(
                    'settings:accounts.incrementAmountHelper',
                    'Units to add/subtract (1-100)'
                  )}
                  margin="normal"
                  inputProps={{ min: 1, max: 100 }}
                />

                <FormControl fullWidth margin="normal">
                  <InputLabel id="pattern-label">
                    {t('settings:accounts.pattern', 'Pattern')}
                  </InputLabel>
                  <Select
                    labelId="pattern-label"
                    value={settings.position_diff_pattern}
                    label={t('settings:accounts.pattern', 'Pattern')}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        position_diff_pattern: e.target.value as
                          | 'increment'
                          | 'decrement'
                          | 'alternating',
                      })
                    }
                  >
                    <MenuItem value="increment">
                      {t('settings:accounts.patternIncrement', 'Increment')}
                    </MenuItem>
                    <MenuItem value="decrement">
                      {t('settings:accounts.patternDecrement', 'Decrement')}
                    </MenuItem>
                    <MenuItem value="alternating">
                      {t('settings:accounts.patternAlternating', 'Alternating')}
                    </MenuItem>
                  </Select>
                </FormControl>

                <Box
                  sx={{
                    mt: 3,
                    p: 2,
                    bgcolor: 'background.default',
                    borderRadius: 1,
                  }}
                >
                  <Typography variant="subtitle2" gutterBottom>
                    {t('settings:accounts.currentPattern', 'Current Pattern')}:
                  </Typography>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mb: 2 }}
                  >
                    {getPatternDescription()}
                  </Typography>

                  <Typography variant="subtitle2" gutterBottom>
                    {t('settings:accounts.baseSize', 'Base Size')}: {baseSize}
                  </Typography>
                  <Typography variant="subtitle2">
                    {t('settings:accounts.nextOrderSize', 'Next Order Size')}:{' '}
                    {getNextOrderSize()}
                  </Typography>
                </Box>
              </>
            )}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={submitting}>
          {t('common:cancel', 'Cancel')}
        </Button>
        <Button
          onClick={handleSave}
          variant="contained"
          color="primary"
          disabled={submitting || loading}
        >
          {submitting ? (
            <CircularProgress size={24} />
          ) : (
            t('common:save', 'Save')
          )}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default PositionDifferentiationDialog;
