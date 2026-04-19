import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  CircularProgress,
  Typography,
  Box,
  TextField,
} from '@mui/material';
import {
  Stop as StopIcon,
  ExitToApp as ClosePositionsIcon,
  TrendingFlat as KeepPositionsIcon,
  WaterDrop as DrainIcon,
} from '@mui/icons-material';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

export type StopOption = 'graceful' | 'graceful_close' | 'drain';

/** Default drain duration (minutes) shown in the dialog. */
export const DEFAULT_DRAIN_DURATION_MINUTES = 60;

export interface StopOptionsConfirm {
  option: StopOption;
  /** Only populated when ``option === 'drain'``. */
  drainDurationMinutes?: number;
}

interface StopOptionsDialogProps {
  open: boolean;
  taskName: string;
  onCancel: () => void;
  onConfirm: (payload: StopOptionsConfirm) => void;
  isLoading: boolean;
  /**
   * Dialog heading.  Explicit override takes precedence over the
   * ``taskType``-derived localised title so callers can still force a
   * specific label if needed.
   */
  title?: string;
  /**
   * Task type used to pick the localised title
   * ("Stop Trading Task" / "Stop Backtest Task").  When omitted the
   * generic "Stop Task" heading is used.
   */
  taskType?: 'trading' | 'backtest';
  // When true, DRAIN is disabled because the caller has determined the task
  // cannot drain (for example, backtests tied to a finite tick stream may
  // still support it, but some task types must not offer the option).
  drainAvailable?: boolean;
}

export function StopOptionsDialog({
  open,
  taskName,
  onCancel,
  onConfirm,
  isLoading,
  title,
  taskType,
  drainAvailable = true,
}: StopOptionsDialogProps) {
  const { t } = useTranslation(['common']);
  const [selectedOption, setSelectedOption] = useState<StopOption | null>(null);
  const [drainDurationMinutes, setDrainDurationMinutes] = useState<number>(
    DEFAULT_DRAIN_DURATION_MINUTES
  );
  const [drainDurationInput, setDrainDurationInput] = useState<string>(
    String(DEFAULT_DRAIN_DURATION_MINUTES)
  );
  const drainDurationInvalid =
    selectedOption === 'drain' &&
    (!Number.isFinite(drainDurationMinutes) || drainDurationMinutes < 1);

  const resolvedTitle =
    title ??
    (taskType === 'trading'
      ? t('common:stopOptions.tradingTitle')
      : taskType === 'backtest'
        ? t('common:stopOptions.backtestTitle')
        : t('common:stopOptions.title'));

  const handleConfirm = () => {
    if (!selectedOption) return;
    if (selectedOption === 'drain') {
      if (drainDurationInvalid) return;
      onConfirm({ option: selectedOption, drainDurationMinutes });
    } else {
      onConfirm({ option: selectedOption });
    }
  };

  const handleClose = () => {
    if (!isLoading) {
      setSelectedOption(null);
      setDrainDurationMinutes(DEFAULT_DRAIN_DURATION_MINUTES);
      setDrainDurationInput(String(DEFAULT_DRAIN_DURATION_MINUTES));
      onCancel();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <StopIcon color="error" />
        {resolvedTitle}
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('common:stopOptions.chooseHowToStop', { taskName })}
        </Typography>
        <List sx={{ bgcolor: 'background.paper' }}>
          <ListItemButton
            selected={selectedOption === 'graceful'}
            onClick={() => setSelectedOption('graceful')}
            disabled={isLoading}
            sx={{
              border: 1,
              borderColor:
                selectedOption === 'graceful' ? 'primary.main' : 'divider',
              borderRadius: 1,
              mb: 1,
            }}
          >
            <ListItemIcon>
              <KeepPositionsIcon color="primary" />
            </ListItemIcon>
            <ListItemText
              primary={t('common:stopOptions.graceful.primary')}
              secondary={t('common:stopOptions.graceful.secondary')}
            />
          </ListItemButton>
          <ListItemButton
            selected={selectedOption === 'graceful_close'}
            onClick={() => setSelectedOption('graceful_close')}
            disabled={isLoading}
            sx={{
              border: 1,
              borderColor:
                selectedOption === 'graceful_close' ? 'error.main' : 'divider',
              borderRadius: 1,
              mb: 1,
            }}
          >
            <ListItemIcon>
              <ClosePositionsIcon color="error" />
            </ListItemIcon>
            <ListItemText
              primary={t('common:stopOptions.gracefulClose.primary')}
              secondary={t('common:stopOptions.gracefulClose.secondary')}
            />
          </ListItemButton>
          {drainAvailable && (
            <ListItemButton
              selected={selectedOption === 'drain'}
              onClick={() => setSelectedOption('drain')}
              disabled={isLoading}
              sx={{
                border: 1,
                borderColor:
                  selectedOption === 'drain' ? 'warning.main' : 'divider',
                borderRadius: 1,
              }}
            >
              <ListItemIcon>
                <DrainIcon color="warning" />
              </ListItemIcon>
              <ListItemText
                primary={t('common:stopOptions.drain.primary')}
                secondary={t('common:stopOptions.drain.secondary')}
              />
            </ListItemButton>
          )}
        </List>
        {selectedOption === 'drain' && (
          <Box sx={{ mt: 2 }}>
            <TextField
              fullWidth
              type="number"
              label={t(
                'common:stopOptions.drainDurationMinutesLabel',
                'Drain duration (minutes)'
              )}
              helperText={
                drainDurationInvalid
                  ? t(
                      'common:stopOptions.drainDurationMinutesError',
                      'Enter a positive integer (minutes).'
                    )
                  : t(
                      'common:stopOptions.drainDurationMinutesHelp',
                      'How long to keep draining before giving up. Defaults to 60 minutes.'
                    )
              }
              value={drainDurationInput}
              onChange={(event) => {
                const raw = event.target.value;
                setDrainDurationInput(raw);
                const parsed = Number.parseInt(raw, 10);
                setDrainDurationMinutes(Number.isFinite(parsed) ? parsed : NaN);
              }}
              disabled={isLoading}
              inputProps={{ min: 1, step: 1 }}
              error={drainDurationInvalid}
              size="small"
            />
          </Box>
        )}
        {selectedOption === 'graceful_close' && (
          <Box
            sx={{
              mt: 2,
              p: 1.5,
              bgcolor: 'warning.light',
              borderRadius: 1,
              opacity: 0.9,
            }}
          >
            <Typography variant="body2" color="warning.contrastText">
              {t('common:stopOptions.closeWarning')}
            </Typography>
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={isLoading}>
          {t('common:stopOptions.cancel')}
        </Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          color="error"
          disabled={!selectedOption || isLoading || drainDurationInvalid}
          startIcon={isLoading ? <CircularProgress size={16} /> : <StopIcon />}
        >
          {isLoading
            ? t('common:stopOptions.loading')
            : t('common:stopOptions.confirm')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
