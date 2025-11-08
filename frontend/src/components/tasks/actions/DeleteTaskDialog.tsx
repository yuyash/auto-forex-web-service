import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Alert,
  Checkbox,
  FormControlLabel,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import WarningIcon from '@mui/icons-material/Warning';
import { TaskStatus } from '../../../types/common';

interface DeleteTaskDialogProps {
  open: boolean;
  taskName: string;
  taskStatus: TaskStatus;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
  warnings?: string[];
  hasExecutionHistory?: boolean;
  isConfigurationInUse?: boolean;
}

export const DeleteTaskDialog: React.FC<DeleteTaskDialogProps> = ({
  open,
  taskName,
  taskStatus,
  onConfirm,
  onCancel,
  isLoading = false,
  warnings = [],
  hasExecutionHistory = false,
  isConfigurationInUse = false,
}) => {
  const [confirmed, setConfirmed] = React.useState(false);

  // Reset confirmation when dialog opens
  React.useEffect(() => {
    if (open) {
      setConfirmed(false);
    }
  }, [open]);

  // Check if deletion is blocked
  const isBlocked = taskStatus === TaskStatus.RUNNING;

  // Build warning messages
  const allWarnings = [...warnings];
  if (hasExecutionHistory) {
    allWarnings.push('All execution history will be permanently deleted');
  }
  if (isConfigurationInUse) {
    allWarnings.push(
      'This task uses a shared configuration that is also used by other tasks'
    );
  }

  const requiresConfirmation = allWarnings.length > 0 || hasExecutionHistory;

  const handleConfirm = () => {
    if (requiresConfirmation && !confirmed) {
      return;
    }
    onConfirm();
  };

  return (
    <Dialog
      open={open}
      onClose={onCancel}
      maxWidth="sm"
      fullWidth
      aria-labelledby="delete-task-dialog-title"
    >
      <DialogTitle id="delete-task-dialog-title">
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <DeleteIcon color="error" />
          Delete Task
        </Box>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ pt: 1 }}>
          {isBlocked ? (
            <Alert severity="error" sx={{ mb: 2 }}>
              <Typography variant="body2">
                Cannot delete a running task. Please stop the task first.
              </Typography>
            </Alert>
          ) : (
            <>
              <Typography variant="body1" sx={{ mb: 2 }}>
                Are you sure you want to delete "{taskName}"?
              </Typography>

              {allWarnings.length > 0 && (
                <Alert severity="warning" icon={<WarningIcon />} sx={{ mb: 2 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
                    Warning: This action cannot be undone
                  </Typography>
                  <List dense disablePadding>
                    {allWarnings.map((warning, index) => (
                      <ListItem key={index} disablePadding>
                        <ListItemText
                          primary={`• ${warning}`}
                          primaryTypographyProps={{
                            variant: 'body2',
                          }}
                        />
                      </ListItem>
                    ))}
                  </List>
                </Alert>
              )}

              {requiresConfirmation && (
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={confirmed}
                      onChange={(e) => setConfirmed(e.target.checked)}
                      disabled={isLoading}
                    />
                  }
                  label={
                    <Typography variant="body2">
                      I understand that this action is permanent and cannot be
                      undone
                    </Typography>
                  }
                />
              )}
            </>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel} disabled={isLoading}>
          Cancel
        </Button>
        {!isBlocked && (
          <Button
            onClick={handleConfirm}
            variant="contained"
            color="error"
            disabled={isLoading || (requiresConfirmation && !confirmed)}
            startIcon={<DeleteIcon />}
          >
            {isLoading ? 'Deleting...' : 'Delete Task'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};
