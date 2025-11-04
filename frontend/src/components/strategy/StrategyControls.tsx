import { useState } from 'react';
import {
  Box,
  Button,
  Stack,
  CircularProgress,
  Alert,
  Typography,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import { useTranslation } from 'react-i18next';
import ConfirmDialog from '../common/ConfirmDialog';
import type { StrategyStatus } from '../../types/strategy';

interface StrategyControlsProps {
  strategyStatus: StrategyStatus | null;
  onStart: () => void | Promise<void>;
  onStop: () => void | Promise<void>;
  disabled?: boolean;
  loading?: boolean;
  canStart?: boolean;
  canStop?: boolean;
}

const StrategyControls = ({
  strategyStatus,
  onStart,
  onStop,
  disabled = false,
  loading = false,
  canStart = true,
  canStop = true,
}: StrategyControlsProps) => {
  const { t } = useTranslation('strategy');
  const [showStartConfirm, setShowStartConfirm] = useState(false);
  const [showStopConfirm, setShowStopConfirm] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const isActive = strategyStatus?.is_active ?? false;
  const isStartDisabled =
    disabled || loading || actionLoading || !canStart || isActive;
  const isStopDisabled =
    disabled || loading || actionLoading || !canStop || !isActive;

  const handleStartClick = () => {
    setShowStartConfirm(true);
  };

  const handleStopClick = () => {
    setShowStopConfirm(true);
  };

  const handleConfirmStart = async () => {
    setShowStartConfirm(false);
    setActionLoading(true);
    try {
      await onStart();
    } finally {
      setActionLoading(false);
    }
  };

  const handleConfirmStop = async () => {
    setShowStopConfirm(false);
    setActionLoading(true);
    try {
      await onStop();
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancelStart = () => {
    setShowStartConfirm(false);
  };

  const handleCancelStop = () => {
    setShowStopConfirm(false);
  };

  return (
    <Box>
      {/* Status Alert */}
      {strategyStatus && (
        <Alert severity={isActive ? 'success' : 'info'} sx={{ mb: 2 }}>
          <Typography variant="body2">
            {isActive
              ? t('status.active', {
                  defaultValue: 'Strategy is currently active',
                })
              : t('status.inactive', {
                  defaultValue: 'Strategy is not active',
                })}
          </Typography>
          {isActive && strategyStatus.strategy_type && (
            <Typography variant="caption" color="text.secondary">
              {t('status.type', {
                defaultValue: 'Type: {{type}}',
                type: strategyStatus.strategy_type,
              })}
            </Typography>
          )}
        </Alert>
      )}

      {/* Control Buttons */}
      <Stack direction="row" spacing={2}>
        <Button
          variant="contained"
          color="success"
          startIcon={
            actionLoading && !isActive ? (
              <CircularProgress size={20} color="inherit" />
            ) : (
              <PlayArrowIcon />
            )
          }
          onClick={handleStartClick}
          disabled={isStartDisabled}
          fullWidth
        >
          {t('controls.start', { defaultValue: 'Start Strategy' })}
        </Button>

        <Button
          variant="contained"
          color="error"
          startIcon={
            actionLoading && isActive ? (
              <CircularProgress size={20} color="inherit" />
            ) : (
              <StopIcon />
            )
          }
          onClick={handleStopClick}
          disabled={isStopDisabled}
          fullWidth
        >
          {t('controls.stop', { defaultValue: 'Stop Strategy' })}
        </Button>
      </Stack>

      {/* Start Confirmation Dialog */}
      <ConfirmDialog
        open={showStartConfirm}
        title={t('confirm.startTitle', {
          defaultValue: 'Start Strategy',
        })}
        message={t('confirm.startMessage', {
          defaultValue:
            'Are you sure you want to start this strategy? It will begin executing trades based on the configured parameters.',
        })}
        confirmText={t('confirm.start', { defaultValue: 'Start' })}
        cancelText={t('confirm.cancel', { defaultValue: 'Cancel' })}
        confirmColor="success"
        onConfirm={handleConfirmStart}
        onCancel={handleCancelStart}
      />

      {/* Stop Confirmation Dialog */}
      <ConfirmDialog
        open={showStopConfirm}
        title={t('confirm.stopTitle', {
          defaultValue: 'Stop Strategy',
        })}
        message={t('confirm.stopMessage', {
          defaultValue:
            'Are you sure you want to stop this strategy? All open positions will remain open but no new trades will be executed.',
        })}
        confirmText={t('confirm.stop', { defaultValue: 'Stop' })}
        cancelText={t('confirm.cancel', { defaultValue: 'Cancel' })}
        confirmColor="error"
        onConfirm={handleConfirmStop}
        onCancel={handleCancelStop}
      />
    </Box>
  );
};

export default StrategyControls;
