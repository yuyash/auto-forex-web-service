import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  CircularProgress,
  Typography,
  Box,
  Alert,
  Checkbox,
  FormControlLabel,
} from '@mui/material';
import {
  RestartAlt as RestartIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { useState } from 'react';

interface RestartOptionsDialogProps {
  open: boolean;
  taskName: string;
  hasOpenPositions: boolean;
  openPositionsCount: number;
  hasStrategyState: boolean;
  onCancel: () => void;
  onConfirm: (clearState: boolean) => void;
  isLoading: boolean;
}

export function RestartOptionsDialog({
  open,
  taskName,
  hasOpenPositions,
  openPositionsCount,
  hasStrategyState,
  onCancel,
  onConfirm,
  isLoading,
}: RestartOptionsDialogProps) {
  const [clearState, setClearState] = useState(true);

  const handleConfirm = () => {
    onConfirm(clearState);
  };

  const handleClose = () => {
    if (!isLoading) {
      setClearState(true);
      onCancel();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <RestartIcon color="warning" />
        Restart Trading Task
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Are you sure you want to restart "{taskName}"?
        </Typography>

        {hasOpenPositions && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2">
              <strong>Warning:</strong> This task has{' '}
              <strong>{openPositionsCount}</strong> open position
              {openPositionsCount > 1 ? 's' : ''}. Restarting will cause the
              strategy to start fresh and may create duplicate positions.
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              Consider stopping with "Close All Positions" first if you want to
              start completely fresh.
            </Typography>
          </Alert>
        )}

        {hasStrategyState && (
          <Alert severity="info" sx={{ mb: 2 }}>
            <Typography variant="body2">
              This task has saved strategy state. The strategy will start fresh
              without remembering previous trading decisions.
            </Typography>
          </Alert>
        )}

        <Box sx={{ mt: 2 }}>
          <FormControlLabel
            control={
              <Checkbox
                checked={clearState}
                onChange={(e) => setClearState(e.target.checked)}
                disabled={isLoading}
              />
            }
            label={
              <Box>
                <Typography variant="body2">Clear strategy state</Typography>
                <Typography variant="caption" color="text.secondary">
                  Start completely fresh without any saved state
                </Typography>
              </Box>
            }
          />
        </Box>

        <Box
          sx={{
            mt: 2,
            p: 2,
            bgcolor: 'grey.50',
            borderRadius: 1,
            border: 1,
            borderColor: 'divider',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <WarningIcon fontSize="small" color="warning" />
            <Typography variant="subtitle2">What will happen:</Typography>
          </Box>
          <Typography variant="body2" component="ul" sx={{ m: 0, pl: 2 }}>
            <li>A new execution will be created</li>
            {clearState && <li>Strategy state will be cleared</li>}
            <li>Strategy will start making trading decisions from scratch</li>
            {hasOpenPositions && (
              <li>
                Existing positions will remain open (close them manually if
                needed)
              </li>
            )}
          </Typography>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={isLoading}>
          Cancel
        </Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          color="warning"
          disabled={isLoading}
          startIcon={
            isLoading ? <CircularProgress size={16} /> : <RestartIcon />
          }
        >
          {isLoading ? 'Restarting...' : 'Restart'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
