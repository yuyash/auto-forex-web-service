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
} from '@mui/material';
import {
  Stop as StopIcon,
  ExitToApp as ClosePositionsIcon,
  TrendingFlat as KeepPositionsIcon,
  WaterDrop as DrainIcon,
} from '@mui/icons-material';
import { useState } from 'react';

export type StopOption = 'graceful' | 'graceful_close' | 'drain';

interface StopOptionsDialogProps {
  open: boolean;
  taskName: string;
  onCancel: () => void;
  onConfirm: (option: StopOption) => void;
  isLoading: boolean;
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
  drainAvailable = true,
}: StopOptionsDialogProps) {
  const [selectedOption, setSelectedOption] = useState<StopOption | null>(null);

  const handleConfirm = () => {
    if (selectedOption) {
      onConfirm(selectedOption);
    }
  };

  const handleClose = () => {
    if (!isLoading) {
      setSelectedOption(null);
      onCancel();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <StopIcon color="error" />
        Stop Trading Task
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Choose how to stop "{taskName}":
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
              primary="Stop (Keep Positions)"
              secondary="Stop trading but keep all open positions. You can manage them manually later."
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
              primary="Stop (Close All Positions)"
              secondary="Stop trading and close all open positions at current market prices."
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
                primary="Drain (Close at breakeven or profit)"
                secondary="Keep running but stop opening new positions. Existing positions are closed as soon as unrealised PnL is non-negative; the task stops once all positions are closed. Optionally bounded by the task's drain duration; issuing another stop while draining terminates the task immediately."
              />
            </ListItemButton>
          )}
        </List>
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
              Warning: This will close all positions at current market prices.
              This action cannot be undone.
            </Typography>
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={isLoading}>
          Cancel
        </Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          color="error"
          disabled={!selectedOption || isLoading}
          startIcon={isLoading ? <CircularProgress size={16} /> : <StopIcon />}
        >
          {isLoading ? 'Stopping...' : 'Stop Task'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
