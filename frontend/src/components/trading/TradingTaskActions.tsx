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
  Pause as PauseIcon,
  PlayCircleOutline as ResumeIcon,
  Stop as StopIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import type { TradingTask } from '../../types/tradingTask';
import { TaskStatus } from '../../types/common';
import { CopyTaskDialog } from '../tasks/actions/CopyTaskDialog';
import { DeleteTaskDialog } from '../tasks/actions/DeleteTaskDialog';
import { ConfirmDialog } from '../tasks/actions/ConfirmDialog';
import {
  useCopyTradingTask,
  useDeleteTradingTask,
  usePauseTradingTask,
  useResumeTradingTask,
  useStopTradingTask,
} from '../../hooks/useTradingTaskMutations';

interface TradingTaskActionsProps {
  task: TradingTask;
  anchorEl: HTMLElement | null;
  onClose: () => void;
}

export default function TradingTaskActions({
  task,
  anchorEl,
  onClose,
}: TradingTaskActionsProps) {
  const navigate = useNavigate();
  const [copyDialogOpen, setCopyDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [pauseDialogOpen, setPauseDialogOpen] = useState(false);
  const [resumeDialogOpen, setResumeDialogOpen] = useState(false);
  const [stopDialogOpen, setStopDialogOpen] = useState(false);

  const copyTask = useCopyTradingTask();
  const deleteTask = useDeleteTradingTask();
  const pauseTask = usePauseTradingTask();
  const resumeTask = useResumeTradingTask();
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
      navigate('/trading-tasks');
    } catch (error) {
      console.error('Failed to delete task:', error);
    }
  };

  const handlePauseClick = () => {
    onClose();
    setPauseDialogOpen(true);
  };

  const handlePauseConfirm = async () => {
    try {
      await pauseTask.mutate(task.id);
      setPauseDialogOpen(false);
    } catch (error) {
      console.error('Failed to pause task:', error);
    }
  };

  const handleResumeClick = () => {
    onClose();
    setResumeDialogOpen(true);
  };

  const handleResumeConfirm = async () => {
    try {
      await resumeTask.mutate(task.id);
      setResumeDialogOpen(false);
    } catch (error) {
      console.error('Failed to resume task:', error);
    }
  };

  const handleStopClick = () => {
    onClose();
    setStopDialogOpen(true);
  };

  const handleStopConfirm = async () => {
    try {
      await stopTask.mutate(task.id);
      setStopDialogOpen(false);
    } catch (error) {
      console.error('Failed to stop task:', error);
    }
  };

  const canEdit =
    task.status !== TaskStatus.RUNNING && task.status !== TaskStatus.PAUSED;
  const canDelete =
    task.status !== TaskStatus.RUNNING && task.status !== TaskStatus.PAUSED;
  const canPause = task.status === TaskStatus.RUNNING;
  const canResume = task.status === TaskStatus.PAUSED;
  const canStop =
    task.status === TaskStatus.RUNNING || task.status === TaskStatus.PAUSED;

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
        {canPause && (
          <MenuItem onClick={handlePauseClick}>
            <ListItemIcon>
              <PauseIcon fontSize="small" color="warning" />
            </ListItemIcon>
            <ListItemText>Pause</ListItemText>
          </MenuItem>
        )}

        {canResume && (
          <MenuItem onClick={handleResumeClick}>
            <ListItemIcon>
              <ResumeIcon fontSize="small" color="primary" />
            </ListItemIcon>
            <ListItemText>Resume</ListItemText>
          </MenuItem>
        )}

        {canStop && (
          <MenuItem onClick={handleStopClick}>
            <ListItemIcon>
              <StopIcon fontSize="small" color="error" />
            </ListItemIcon>
            <ListItemText>Stop</ListItemText>
          </MenuItem>
        )}

        {(canPause || canResume || canStop) && <Divider />}

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

      <ConfirmDialog
        open={pauseDialogOpen}
        title="Pause Trading Task"
        message={`Are you sure you want to pause "${task.name}"? The task will stop executing new trades but existing positions will remain open.`}
        confirmText="Pause"
        confirmColor="warning"
        onCancel={() => setPauseDialogOpen(false)}
        onConfirm={handlePauseConfirm}
        isLoading={pauseTask.isLoading}
        icon={<PauseIcon />}
      />

      <ConfirmDialog
        open={resumeDialogOpen}
        title="Resume Trading Task"
        message={`Are you sure you want to resume "${task.name}"? The task will start executing trades again.`}
        confirmText="Resume"
        confirmColor="primary"
        onCancel={() => setResumeDialogOpen(false)}
        onConfirm={handleResumeConfirm}
        isLoading={resumeTask.isLoading}
        icon={<ResumeIcon />}
      />

      <ConfirmDialog
        open={stopDialogOpen}
        title="Emergency Stop"
        message={`Are you sure you want to stop "${task.name}"? This will immediately halt all trading activity. Existing positions will remain open.`}
        confirmText="Stop"
        confirmColor="error"
        onCancel={() => setStopDialogOpen(false)}
        onConfirm={handleStopConfirm}
        isLoading={stopTask.isLoading}
        icon={<WarningIcon />}
      />
    </>
  );
}
