import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Divider,
} from '@mui/material';
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  FileCopy as CopyIcon,
  Stop as StopIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import type { BacktestTask } from '../../types/backtestTask';
import { TaskStatus } from '../../types/common';
import { CopyTaskDialog } from '../tasks/actions/CopyTaskDialog';
import { DeleteTaskDialog } from '../tasks/actions/DeleteTaskDialog';
import {
  StopOptionsDialog,
  type StopOption,
} from '../tasks/actions/StopOptionsDialog';
import {
  useCopyBacktestTask,
  useDeleteBacktestTask,
  useStopBacktestTask,
} from '../../hooks/useBacktestTaskMutations';
import { useToast } from '../common';
import { logger } from '../../utils/logger';

interface BacktestTaskActionsProps {
  task: BacktestTask;
  anchorEl: HTMLElement | null;
  onClose: () => void;
  onRefresh?: () => void;
}

export default function BacktestTaskActions({
  task,
  anchorEl,
  onClose,
  onRefresh,
}: BacktestTaskActionsProps) {
  const { t } = useTranslation(['backtest', 'common']);
  const navigate = useNavigate();
  const { showError } = useToast();
  const [copyDialogOpen, setCopyDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [stopDialogOpen, setStopDialogOpen] = useState(false);

  const copyTask = useCopyBacktestTask();
  const deleteTask = useDeleteBacktestTask();
  const stopTask = useStopBacktestTask();

  const handleEdit = () => {
    onClose();
    navigate(`/backtest-tasks/${task.id}/edit`);
  };

  const handleCopyClick = () => {
    onClose();
    setCopyDialogOpen(true);
  };

  const handleCopyConfirm = async (newName: string) => {
    try {
      await copyTask.mutate({ id: task.id, data: { new_name: newName } });
      setCopyDialogOpen(false);
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to copy backtest task', {
        taskId: task.id,
        error: error instanceof Error ? error.message : String(error),
      });
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to copy task';
      showError(errorMessage);
    }
  };

  const handleDeleteClick = () => {
    // Check if task is running before opening dialog
    if (task.status === TaskStatus.RUNNING) {
      showError(t('backtest:toast.cannotDeleteRunning'));
      onClose();
      return;
    }
    onClose();
    setDeleteDialogOpen(true);
  };

  const handleStopClick = () => {
    onClose();
    setStopDialogOpen(true);
  };

  const handleStopConfirm = async ({
    option,
    drainDurationMinutes,
  }: {
    option: StopOption;
    drainDurationMinutes?: number;
  }) => {
    try {
      await stopTask.mutate({
        id: task.id,
        mode: option,
        ...(drainDurationMinutes !== undefined ? { drainDurationMinutes } : {}),
      });
      setStopDialogOpen(false);
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to stop backtest task', {
        taskId: task.id,
        error: error instanceof Error ? error.message : String(error),
      });
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to stop task';
      showError(errorMessage);
      setStopDialogOpen(false);
    }
  };

  const handleDeleteConfirm = async () => {
    try {
      await deleteTask.mutate(task.id);
      setDeleteDialogOpen(false);
      onRefresh?.();
      navigate('/backtest-tasks', { state: { deleted: true } });
    } catch (error) {
      logger.error('Failed to delete backtest task from actions menu', {
        taskId: task.id,
        error: error instanceof Error ? error.message : String(error),
      });
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to delete task';

      // Check if error is about running task
      if (errorMessage.includes('running') || errorMessage.includes('409')) {
        showError(t('backtest:toast.cannotDeleteRunning'));
      } else {
        showError(errorMessage);
      }
      setDeleteDialogOpen(false);
    }
  };

  const canEdit = task.action_policy?.can_edit_metadata ?? false;
  const canDelete = task.action_policy?.can_delete ?? false;
  const canStop =
    task.action_policy?.can_stop ??
    (task.status === TaskStatus.RUNNING ||
      task.status === TaskStatus.PAUSED ||
      task.status === TaskStatus.DRAINING);

  return (
    <>
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={onClose}
        disableRestoreFocus
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
      >
        {canStop && (
          <MenuItem onClick={handleStopClick}>
            <ListItemIcon>
              <StopIcon fontSize="small" color="error" />
            </ListItemIcon>
            <ListItemText>{t('common:actions.stop')}</ListItemText>
          </MenuItem>
        )}

        {canStop && <Divider />}

        <MenuItem onClick={handleCopyClick}>
          <ListItemIcon>
            <CopyIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>{t('common:actions.copy')}</ListItemText>
        </MenuItem>

        <MenuItem onClick={handleEdit} disabled={!canEdit}>
          <ListItemIcon>
            <EditIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>{t('common:actions.edit')}</ListItemText>
        </MenuItem>

        <Divider />

        <MenuItem onClick={handleDeleteClick} disabled={!canDelete}>
          <ListItemIcon>
            <DeleteIcon
              fontSize="small"
              color={canDelete ? 'error' : 'disabled'}
            />
          </ListItemIcon>
          <ListItemText>{t('common:actions.delete')}</ListItemText>
        </MenuItem>
      </Menu>

      <CopyTaskDialog
        open={copyDialogOpen}
        taskName={task.name}
        onCancel={() => setCopyDialogOpen(false)}
        onConfirm={handleCopyConfirm}
        isLoading={copyTask.isLoading}
      />

      <DeleteTaskDialog
        open={deleteDialogOpen}
        taskName={task.name}
        taskStatus={task.status}
        onCancel={() => setDeleteDialogOpen(false)}
        onConfirm={handleDeleteConfirm}
        isLoading={deleteTask.isLoading}
        hasExecutionHistory={true}
      />

      <StopOptionsDialog
        open={stopDialogOpen}
        taskName={task.name}
        taskType="backtest"
        onCancel={() => setStopDialogOpen(false)}
        onConfirm={handleStopConfirm}
        isLoading={stopTask.isLoading}
      />
    </>
  );
}
