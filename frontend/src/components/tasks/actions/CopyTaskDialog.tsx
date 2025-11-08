import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';

interface CopyTaskDialogProps {
  open: boolean;
  taskName: string;
  onConfirm: (newName: string) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export const CopyTaskDialog: React.FC<CopyTaskDialogProps> = ({
  open,
  taskName,
  onConfirm,
  onCancel,
  isLoading = false,
}) => {
  const [newName, setNewName] = React.useState('');
  const [error, setError] = React.useState('');

  // Reset state when dialog opens
  React.useEffect(() => {
    if (open) {
      setNewName(`${taskName} (Copy)`);
      setError('');
    }
  }, [open, taskName]);

  const handleConfirm = () => {
    // Validate name
    if (!newName.trim()) {
      setError('Name is required');
      return;
    }

    if (newName.trim() === taskName) {
      setError('New name must be different from original');
      return;
    }

    if (newName.length > 255) {
      setError('Name must be less than 255 characters');
      return;
    }

    onConfirm(newName.trim());
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !isLoading) {
      handleConfirm();
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onCancel}
      maxWidth="sm"
      fullWidth
      aria-labelledby="copy-task-dialog-title"
    >
      <DialogTitle id="copy-task-dialog-title">
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <ContentCopyIcon />
          Copy Task
        </Box>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ pt: 1 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Create a copy of "{taskName}" with a new name. All settings and
            configuration will be duplicated.
          </Typography>
          <TextField
            autoFocus
            fullWidth
            label="New Task Name"
            value={newName}
            onChange={(e) => {
              setNewName(e.target.value);
              setError('');
            }}
            onKeyPress={handleKeyPress}
            error={!!error}
            helperText={error || `${newName.length}/255 characters`}
            disabled={isLoading}
            required
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel} disabled={isLoading}>
          Cancel
        </Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          disabled={isLoading || !newName.trim()}
          startIcon={<ContentCopyIcon />}
        >
          {isLoading ? 'Copying...' : 'Copy Task'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
