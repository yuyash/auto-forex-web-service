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

interface BacktestTaskActionsProps {
  task: BacktestTask;
  anchorEl: HTMLElement | null;
  onClose: () => void;
}

export default function BacktestTaskActions({
  task,
  anchorEl,
  onClose,
}: BacktestTaskActionsProps) {
  const navigate = useNavigate();
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
      setCopyDialogOpen(false);
    } catch (error) {
      console.error('Failed to copy task:', error);
    }
  };

  const handleDeleteClick = () => {
    onClose();
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    try {
      await deleteTask.mutate(task.id);
      setDeleteDialogOpen(false);
      navigate('/backtest-tasks');
    } catch (error) {
      console.error('Failed to delete task:', error);
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
