import { useQueryClient } from '@tanstack/react-query';
import { useTaskStatusWebSocket } from '../../hooks/useTaskStatusWebSocket';
import { useToast } from '../common';

/**
 * Global component that listens to task status updates via WebSocket
 * and automatically updates the UI and shows notifications.
 *
 * Should be mounted once at the app level.
 */
export function TaskStatusListener() {
  const queryClient = useQueryClient();
  const toast = useToast();

  useTaskStatusWebSocket({
    onStatusUpdate: (update) => {
      console.log('[TaskStatusListener] Received update:', update);

      // Force refetch relevant queries to refresh the UI immediately
      if (update.task_type === 'backtest') {
        // Refetch backtest task queries
        queryClient.refetchQueries({ queryKey: ['backtest-tasks'] });
        queryClient.refetchQueries({
          queryKey: ['backtest-task', update.task_id],
        });

        if (update.execution_id) {
          queryClient.refetchQueries({
            queryKey: ['backtest-task-executions', update.task_id],
          });
        }
      } else if (update.task_type === 'trading') {
        // Refetch trading task queries
        queryClient.refetchQueries({ queryKey: ['trading-tasks'] });
        queryClient.refetchQueries({
          queryKey: ['trading-task', update.task_id],
        });

        if (update.execution_id) {
          queryClient.refetchQueries({
            queryKey: ['trading-task-executions', update.task_id],
          });
        }
      }

      console.log(
        '[TaskStatusListener] Triggered refetch for task',
        update.task_id
      );
    },

    onProgressUpdate: (update) => {
      console.log('[TaskStatusListener] Progress update:', update);

      // Update execution progress in cache without full refetch
      const taskType = update.task_type === 'backtest' ? 'backtest' : 'trading';
      queryClient.setQueryData(
        [`${taskType}-task-executions`, update.task_id],
        (oldData: unknown) => {
          if (
            !oldData ||
            typeof oldData !== 'object' ||
            !('results' in oldData)
          ) {
            return oldData;
          }

          const data = oldData as {
            results: Array<{ id: number; progress: number }>;
          };

          return {
            ...data,
            results: data.results.map((execution) =>
              execution.id === update.execution_id
                ? { ...execution, progress: update.progress }
                : execution
            ),
          };
        }
      );
    },

    onComplete: (update) => {
      toast.showSuccess(`Task "${update.task_name}" completed successfully!`);
    },

    onFailed: (update) => {
      const message = update.error_message
        ? `Task "${update.task_name}" failed: ${update.error_message}`
        : `Task "${update.task_name}" failed`;

      toast.showError(message);
    },

    onStopped: (update) => {
      toast.showInfo(`Task "${update.task_name}" was stopped`);
    },
  });

  // This component doesn't render anything
  return null;
}
