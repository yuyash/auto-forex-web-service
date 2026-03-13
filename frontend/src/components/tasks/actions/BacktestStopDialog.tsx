import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  CircularProgress,
} from '@mui/material';
import { Stop as StopIcon } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';

interface BacktestStopDialogProps {
  open: boolean;
  taskName: string;
  isLoading?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function BacktestStopDialog({
  open,
  taskName,
  isLoading = false,
  onCancel,
  onConfirm,
}: BacktestStopDialogProps) {
  const { t } = useTranslation('backtest');

  return (
    <Dialog
      open={open}
      onClose={isLoading ? undefined : onCancel}
      maxWidth="sm"
      fullWidth
      aria-labelledby="backtest-stop-dialog-title"
    >
      <DialogTitle id="backtest-stop-dialog-title">
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <StopIcon color="error" />
          {t('stopDialog.title')}
        </Box>
      </DialogTitle>
      <DialogContent>
        <Typography variant="body1" sx={{ pt: 1 }}>
          {t('stopDialog.message', { taskName })}
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel} disabled={isLoading}>
          {t('stopDialog.cancel')}
        </Button>
        <Button
          onClick={onConfirm}
          variant="contained"
          color="error"
          disabled={isLoading}
          startIcon={isLoading ? <CircularProgress size={16} /> : <StopIcon />}
        >
          {isLoading ? t('stopDialog.stopping') : t('stopDialog.confirm')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
