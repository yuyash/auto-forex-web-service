import React from 'react';
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
import {
  PlayArrow as StartIcon,
  Pause as PauseIcon,
  PlayCircleOutline as ResumeIcon,
  Replay as RestartIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';

export type TaskActionType = 'start' | 'pause' | 'resume' | 'restart';

interface TaskActionConfirmDialogProps {
  open: boolean;
  action: TaskActionType;
  taskName: string;
  isLoading?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

const actionConfig: Record<
  TaskActionType,
  {
    icon: React.ReactElement;
    color: 'success' | 'warning' | 'primary' | 'info';
  }
> = {
  start: { icon: <StartIcon />, color: 'success' },
  pause: { icon: <PauseIcon />, color: 'warning' },
  resume: { icon: <ResumeIcon />, color: 'primary' },
  restart: { icon: <RestartIcon />, color: 'info' },
};

export function TaskActionConfirmDialog({
  open,
  action,
  taskName,
  isLoading = false,
  onCancel,
  onConfirm,
}: TaskActionConfirmDialogProps) {
  const { t } = useTranslation('common');
  const config = actionConfig[action];

  return (
    <Dialog
      open={open}
      onClose={isLoading ? undefined : onCancel}
      maxWidth="sm"
      fullWidth
      aria-labelledby="task-action-confirm-dialog-title"
    >
      <DialogTitle id="task-action-confirm-dialog-title">
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {React.cloneElement(config.icon, {
            color: config.color,
          } as React.Attributes & Record<string, unknown>)}
          {t(`taskActionDialog.${action}.title`)}
        </Box>
      </DialogTitle>
      <DialogContent>
        <Typography variant="body1" sx={{ pt: 1 }}>
          {t(`taskActionDialog.${action}.message`, { taskName })}
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel} disabled={isLoading}>
          {t('actions.cancel')}
        </Button>
        <Button
          onClick={onConfirm}
          variant="contained"
          color={config.color}
          disabled={isLoading}
          startIcon={
            isLoading ? (
              <CircularProgress size={16} />
            ) : (
              React.cloneElement(config.icon)
            )
          }
        >
          {isLoading
            ? t(`taskActionDialog.${action}.loading`)
            : t(`taskActionDialog.${action}.confirm`)}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
