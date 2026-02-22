import { useState } from 'react';
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
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import type { BacktestTask } from '../../types/backtestTask';
import { TaskStatus } from '../../types/common';
import { CopyTaskDialog } from '../tasks/actions/CopyTaskDialog';
import { DeleteTaskDialog } from '../tasks/actions/DeleteTaskDialog';
import {
  useCopyBacktestTask,
  useDeleteBacktestTask,
} from '../../hooks/useBacktestTaskMutations';
import { invalidateBacktestTasksCache } from '../../hooks/useBacktestTasks';
import { useToast } from '../common';

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
  const navigate = useNavigate();
  const { showError } = useToast();
  const [copyDialogOpen, setCopyDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const copyTask = useCopyBacktestTask();
  const deleteTask = useDeleteBacktestTask();

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
      invalidateBacktestTasksCache(); // Refresh task list
      setCopyDialogOpen(false);
      // Trigger refresh after successful copy
      onRefresh?.();
    } catch (error) {
      console.error('Failed to copy task:', error);
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to copy task';
      showError(errorMessage);
    }
  };

  const handleDeleteClick = () => {
    // Check if task is running before opening dialog
    if (task.status === TaskStatus.RUNNING) {
      showError('Cannot delete running task. Stop it first.');
      onClose();
      return;
    }
    onClose();
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    try {
      await deleteTask.mutate(task.id);
      invalidateBacktestTasksCache(); // Refresh task list
      setDeleteDialogOpen(false);
      // Trigger refresh after successful delete
      onRefresh?.();
      navigate('/backtest-tasks', { state: { deleted: true } });
    } catch (error) {
      console.error('Failed to delete task:', error);
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to delete task';

      // Check if error is about running task
      if (errorMessage.includes('running') || errorMessage.includes('409')) {
        showError('Cannot delete running task. Stop it first.');
      } else {
        showError(errorMessage);
      }
      setDeleteDialogOpen(false);
    }
  };

  const canEdit = task.status !== TaskStatus.RUNNING;
  const canDelete = task.status !== TaskStatus.RUNNING;

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
        <MenuItem onClick={handleCopyClick}>
          <ListItemIcon>
            <CopyIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Copy</ListItemText>
        </MenuItem>

        <MenuItem onClick={handleEdit} disabled={!canEdit}>
          <ListItemIcon>
            <EditIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Edit</ListItemText>
        </MenuItem>

        <Divider />

        <MenuItem onClick={handleDeleteClick} disabled={!canDelete}>
          <ListItemIcon>
            <DeleteIcon
              fontSize="small"
              color={canDelete ? 'error' : 'disabled'}
            />
          </ListItemIcon>
          <ListItemText>Delete</ListItemText>
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
    </>
  );
}
