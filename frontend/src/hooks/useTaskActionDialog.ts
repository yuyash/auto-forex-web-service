/**
 * useTaskActionDialog — manages confirmation dialog state for task actions.
 *
 * Provides a pending action state and helpers to request confirmation
 * before executing start, pause, resume, or restart operations.
 */
import { useState, useCallback } from 'react';
import type { TaskActionType } from '../components/tasks/actions/TaskActionConfirmDialog';

interface PendingAction {
  type: TaskActionType;
  taskId: string;
}

interface UseTaskActionDialogResult {
  /** The action awaiting confirmation, or null when the dialog is closed. */
  pendingAction: PendingAction | null;
  /** Open the confirmation dialog for the given action and task. */
  requestConfirm: (type: TaskActionType, taskId: string) => void;
  /** Close the dialog without executing. */
  cancelAction: () => void;
}

export function useTaskActionDialog(): UseTaskActionDialogResult {
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(
    null
  );

  const requestConfirm = useCallback((type: TaskActionType, taskId: string) => {
    setPendingAction({ type, taskId });
  }, []);

  const cancelAction = useCallback(() => {
    setPendingAction(null);
  }, []);

  return { pendingAction, requestConfirm, cancelAction };
}
