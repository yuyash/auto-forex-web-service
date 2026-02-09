import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Alert,
  Box,
  List,
  ListItem,
  ListItemText,
  Checkbox,
  FormControlLabel,
  CircularProgress,
  Chip,
} from '@mui/material';
import WarningIcon from '@mui/icons-material/Warning';
import { useConfigurationMutations } from '../../hooks/useConfigurationMutations';
import { TaskStatus } from '../../types/common';
import { StatusBadge } from '../tasks/display/StatusBadge';
import type {
  StrategyConfig,
  ConfigurationTask,
} from '../../types/configuration';
import { configurationsApi } from '../../services/api/configurations';

interface ConfigurationDeleteDialogProps {
  open: boolean;
  configuration: StrategyConfig;
  onClose: () => void;
}

const ConfigurationDeleteDialog = ({
  open,
  configuration,
  onClose,
}: ConfigurationDeleteDialogProps) => {
  const [confirmed, setConfirmed] = useState(false);
  const [tasks, setTasks] = useState<ConfigurationTask[]>([]);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const { deleteConfiguration, isDeleting } = useConfigurationMutations();

  // Fetch tasks using this configuration when dialog opens
  useEffect(() => {
    const fetchTasks = async () => {
      if (open && configuration.is_in_use) {
        setLoadingTasks(true);
        try {
          const tasks = await configurationsApi.getTasks(configuration.id);
          setTasks(tasks || []);
        } catch (error) {
          console.error('Failed to fetch tasks:', error);
          setTasks([]);
        } finally {
          setLoadingTasks(false);
        }
      } else if (!open) {
        // Reset state when dialog closes
        setConfirmed(false);
        setTasks([]);
      }
    };

    fetchTasks();
  }, [open, configuration.id, configuration.is_in_use]);

  const handleDelete = async () => {
    try {
      await deleteConfiguration(configuration.id);
      onClose();
    } catch (error) {
      console.error('Failed to delete configuration:', error);
    }
  };

  const activeTasks = tasks.filter(
    (task) =>
      task.status === TaskStatus.RUNNING || task.status === TaskStatus.PENDING
  );
  const hasActiveTasks = activeTasks.length > 0;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <WarningIcon color="warning" />
          Delete Configuration
        </Box>
      </DialogTitle>

      <DialogContent>
        <Typography variant="body1" gutterBottom>
          Are you sure you want to delete the configuration "
          {configuration.name}"?
        </Typography>

        {/* Warning if configuration is in use */}
        {configuration.is_in_use && (
          <Alert severity="warning" sx={{ mt: 2, mb: 2 }}>
            <Typography variant="body2" gutterBottom>
              This configuration is currently being used by {tasks.length}{' '}
              task(s).
            </Typography>
          </Alert>
        )}

        {/* Show active tasks warning */}
        {hasActiveTasks && (
          <Alert severity="error" sx={{ mt: 2, mb: 2 }}>
            <Typography variant="body2" gutterBottom>
              <strong>Cannot delete:</strong> This configuration is being used
              by {activeTasks.length} active task(s). Please stop or complete
              these tasks first.
            </Typography>
          </Alert>
        )}

        {/* Loading tasks */}
        {loadingTasks && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
            <CircularProgress size={24} />
          </Box>
        )}

        {/* List of tasks using this configuration */}
        {!loadingTasks && tasks.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Tasks using this configuration:
            </Typography>
            <List dense sx={{ maxHeight: 200, overflow: 'auto' }}>
              {tasks.map((task) => (
                <ListItem
                  key={`${task.task_type}-${task.id}`}
                  sx={{
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 1,
                    mb: 1,
                  }}
                >
                  <ListItemText
                    primary={task.name}
                    secondary={
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          mt: 0.5,
                        }}
                      >
                        <Chip
                          label={task.task_type}
                          size="small"
                          variant="outlined"
                          sx={{ fontSize: '0.7rem' }}
                        />
                        <StatusBadge
                          status={task.status}
                          size="small"
                          showIcon={false}
                          sx={{ fontSize: '0.7rem' }}
                        />
                      </Box>
                    }
                  />
                </ListItem>
              ))}
            </List>
          </Box>
        )}

        {/* Confirmation checkbox (only if no active tasks) */}
        {!hasActiveTasks && configuration.is_in_use && (
          <Box sx={{ mt: 2 }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                  color="error"
                />
              }
              label={
                <Typography variant="body2">
                  I understand that deleting this configuration will affect{' '}
                  {tasks.length} task(s)
                </Typography>
              }
            />
          </Box>
        )}

        {/* Simple confirmation for unused configurations */}
        {!configuration.is_in_use && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            This action cannot be undone.
          </Typography>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose} disabled={isDeleting}>
          Cancel
        </Button>
        <Button
          onClick={handleDelete}
          color="error"
          variant="contained"
          disabled={
            isDeleting ||
            hasActiveTasks ||
            (configuration.is_in_use && !confirmed)
          }
          startIcon={isDeleting ? <CircularProgress size={20} /> : null}
        >
          {isDeleting ? 'Deleting...' : 'Delete'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ConfigurationDeleteDialog;
