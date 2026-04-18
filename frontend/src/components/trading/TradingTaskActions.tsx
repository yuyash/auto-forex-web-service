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
import type { TradingTask } from '../../types/tradingTask';
import { TaskStatus } from '../../types/common';
import { CopyTaskDialog } from '../tasks/actions/CopyTaskDialog';
import { DeleteTaskDialog } from '../tasks/actions/DeleteTaskDialog';
import {
  StopOptionsDialog,
  type StopOption,
} from '../tasks/actions/StopOptionsDialog';
import {
  useCopyTradingTask,
  useDeleteTradingTask,
  useStopTradingTask,
} from '../../hooks/useTradingTaskMutations';
import { useToast } from '../common';
import { logger } from '../../utils/logger';

interface TradingTaskActionsProps {
  task: TradingTask;
  anchorEl: HTMLElement | null;
  onClose: () => void;
  onRefresh?: () => void;
}

export default function TradingTaskActions({
  task,
  anchorEl,
  onClose,
  onRefresh,
}: TradingTaskActionsProps) {
  const { t } = useTranslation(['trading', 'common']);
  const navigate = useNavigate();
  const { showError } = useToast();
  const [copyDialogOpen, setCopyDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [stopDialogOpen, setStopDialogOpen] = useState(false);

  const copyTask = useCopyTradingTask();
  const deleteTask = useDeleteTradingTask();
  const stopTask = useStopTradingTask();

  const handleEdit = () => {
    onClose();
    navigate(`/trading-tasks/${task.id}/edit`);
  };

  const handleCopyClick = () => {
    onClose();
    setCopyDialogOpen(true);
  };

  const handleCopyConfirm = async (newName: string) => {
    try {
      await copyTask.mutate({ id: task.id, data: { new_name: newName } });
      setCopyDialogOpen(false);
      // Trigger refresh after successful copy
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to copy trading task', {
        taskId: task.id,
        error: error instanceof Error ? error.message : String(error),
      });
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to copy task';
      showError(errorMessage);
    }
  };

  const handleDeleteClick = () => {
    // Check if task is running or paused before opening dialog
    if (
      task.status === TaskStatus.RUNNING ||
      task.status === TaskStatus.PAUSED
    ) {
      showError(t('trading:warnings.cannotDeleteRunning'));
      onClose();
      return;
    }
    onClose();
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    try {
      await deleteTask.mutate(task.id);
      setDeleteDialogOpen(false);
      // Trigger refresh after successful delete
      onRefresh?.();
      navigate('/trading-tasks', { state: { deleted: true } });
    } catch (error) {
      logger.error('Failed to delete trading task from actions menu', {
        taskId: task.id,
        error: error instanceof Error ? error.message : String(error),
      });
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to delete task';

      // Check if error is about running task
      if (
        errorMessage.includes('running') ||
        errorMessage.includes('paused') ||
        errorMessage.includes('409')
      ) {
        showError(t('trading:warnings.cannotDeleteRunning'));
      } else {
        showError(errorMessage);
      }
      setDeleteDialogOpen(false);
    }
  };

  const handleStopClick = () => {
    onClose();
    setStopDialogOpen(true);
  };

  const handleStopConfirm = async (option: StopOption) => {
    try {
      await stopTask.mutate({ id: task.id, mode: option });
      setStopDialogOpen(false);
      // Trigger refresh after successful stop
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to stop trading task from actions menu', {
        taskId: task.id,
        error: error instanceof Error ? error.message : String(error),
      });
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to stop task';
      showError(errorMessage);
      setStopDialogOpen(false);
    }
  };

  const canEdit =
    task.status !== TaskStatus.RUNNING &&
    task.status !== TaskStatus.PAUSED &&
    task.status !== TaskStatus.IDLE &&
    task.status !== TaskStatus.DRAINING;
  const canDelete =
    task.status !== TaskStatus.RUNNING &&
    task.status !== TaskStatus.PAUSED &&
    task.status !== TaskStatus.IDLE &&
    task.status !== TaskStatus.DRAINING;
  const canStop =
    task.status === TaskStatus.RUNNING ||
    task.status === TaskStatus.PAUSED ||
    task.status === TaskStatus.IDLE ||
    task.status === TaskStatus.DRAINING;

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
        onCancel={() => setStopDialogOpen(false)}
        onConfirm={handleStopConfirm}
        isLoading={stopTask.isLoading}
      />
    </>
  );
}
