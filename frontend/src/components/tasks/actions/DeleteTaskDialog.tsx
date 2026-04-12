import React from 'react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation('common');
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
    allWarnings.push(t('deleteTask.warnings.executionHistory'));
  }
  if (isConfigurationInUse) {
    allWarnings.push(t('deleteTask.warnings.sharedConfiguration'));
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
          {t('deleteTask.title')}
        </Box>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ pt: 1 }}>
          {isBlocked ? (
            <Alert severity="error" sx={{ mb: 2 }}>
              <Typography variant="body2">
                {t('deleteTask.blockedRunning')}
              </Typography>
            </Alert>
          ) : (
            <>
              <Typography variant="body1" sx={{ mb: 2 }}>
                {t('deleteTask.confirmation', { taskName })}
              </Typography>

              {allWarnings.length > 0 && (
                <Alert severity="warning" icon={<WarningIcon />} sx={{ mb: 2 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
                    {t('deleteTask.warningTitle')}
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
                      {t('deleteTask.acknowledge')}
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
          {t('actions.cancel')}
        </Button>
        {!isBlocked && (
          <Button
            onClick={handleConfirm}
            variant="contained"
            color="error"
            disabled={isLoading || (requiresConfirmation && !confirmed)}
            startIcon={<DeleteIcon />}
          >
            {isLoading ? t('actions.deleting') : t('deleteTask.title')}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};
