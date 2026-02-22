/**
 * TaskStore - State management for task operations with optimistic updates
 *
 * Provides:
 * - Optimistic status updates for immediate UI feedback
 * - Server confirmation and rollback on errors
 * - Progress tracking for running tasks
 * - Polling fallback when WebSocket fails
 */

import type { BacktestTask } from '../types';
import { TaskStatus } from '../types/common';

interface TaskState {
  // Current task data
  task: BacktestTask | null;
  // Previous state for rollback
  previousTask: BacktestTask | null;
  // Loading state for operations
  isUpdating: boolean;
  // Error state
  error: Error | null;
  // Polling interval ID
  pollingIntervalId: number | null;
}

type TaskUpdateListener = (task: BacktestTask | null) => void;

/**
 * TaskStore manages task state with optimistic updates and synchronization
 */
export class TaskStore {
  private state: TaskState = {
    task: null,
    previousTask: null,
    isUpdating: false,
    error: null,
    pollingIntervalId: null,
  };

  private listeners: Set<TaskUpdateListener> = new Set();

  /**
   * Subscribe to task state changes
   */
  subscribe(listener: TaskUpdateListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /**
   * Notify all listeners of state change
   */
  private notify(): void {
    this.listeners.forEach((listener) => listener(this.state.task));
  }

  /**
   * Get current task state
   */
  getTask(): BacktestTask | null {
    return this.state.task;
  }

  /**
   * Get current updating state
   */
  isUpdating(): boolean {
    return this.state.isUpdating;
  }

  /**
   * Get current error state
   */
  getError(): Error | null {
    return this.state.error;
  }

  /**
   * Set initial task data
   */
  setTask(task: BacktestTask | null): void {
    this.state.task = task;
    this.state.error = null;
    this.notify();
  }

  /**
   * Optimistically update task status for immediate UI feedback
   * Stores previous state for potential rollback
   *
   * @param status - New status to apply
   */
  optimisticUpdateStatus(status: TaskStatus): void {
    if (!this.state.task) {
      console.warn('[TaskStore] Cannot update status: no task loaded');
      return;
    }

    // Store previous state for rollback
    this.state.previousTask = { ...this.state.task };

    // Apply optimistic update
    this.state.task = {
      ...this.state.task,
      status,
      updated_at: new Date().toISOString(),
    };

    this.state.isUpdating = true;
    this.state.error = null;

    this.notify();
  }

  /**
   * Confirm status update from server
   * Clears the updating state and previous task backup
   *
   * @param status - Confirmed status from server
   * @param execution_id - Optional execution ID for running tasks
   */
  confirmStatusUpdate(status: TaskStatus, execution_id?: string): void {
    if (!this.state.task) {
      console.warn('[TaskStore] Cannot confirm status: no task loaded');
      return;
    }

    // Update with confirmed server state
    this.state.task = {
      ...this.state.task,
      status,
      updated_at: new Date().toISOString(),
    };

    // Update execution_id if provided (for running tasks)
    if (execution_id !== undefined && this.state.task.latest_execution) {
      this.state.task.latest_execution.id = execution_id;
    }

    // Clear optimistic state
    this.state.previousTask = null;
    this.state.isUpdating = false;
    this.state.error = null;

    this.notify();
  }

  /**
   * Rollback to previous state on error
   * Restores the task state before optimistic update
   *
   * @param error - Error that caused the rollback
   */
  rollbackStatusUpdate(error: Error): void {
    if (!this.state.previousTask) {
      console.warn('[TaskStore] Cannot rollback: no previous state');
      this.state.error = error;
      this.state.isUpdating = false;
      this.notify();
      return;
    }

    // Restore previous state
    this.state.task = this.state.previousTask;
    this.state.previousTask = null;
    this.state.isUpdating = false;
    this.state.error = error;

    this.notify();
  }

  /**
   * Update task progress
   * Used for real-time progress updates during execution
   *
   * @param progress - Progress percentage (0-100)
   */
  updateProgress(progress: number): void {
    if (!this.state.task) {
      console.warn('[TaskStore] Cannot update progress: no task loaded');
      return;
    }

    // Only update progress if task is running
    if (this.state.task.status !== TaskStatus.RUNNING) {
      return;
    }

    // Update progress in latest_execution if it exists
    if (this.state.task.latest_execution) {
      this.state.task = {
        ...this.state.task,
        latest_execution: {
          ...this.state.task.latest_execution,
          progress: Math.min(100, Math.max(0, progress)),
        },
      };

      this.notify();
    }
  }

  /**
   * Start polling for task status updates
   * Used as fallback when WebSocket connection fails
   *
   * @param taskId - ID of task to poll
   * @param fetchFn - Function to fetch task data
   * @param interval - Polling interval in milliseconds (default: 3000)
   */
  startPolling(
    taskId: string,
    fetchFn: (id: string) => Promise<BacktestTask>,
    interval: number = 3000
  ): void {
    // Stop any existing polling
    this.stopPolling();

    // Start new polling interval
    const intervalId = window.setInterval(async () => {
      try {
        const task = await fetchFn(taskId);
        this.setTask(task);
      } catch (error) {
        console.error('[TaskStore] Polling error:', error);
        this.state.error = error as Error;
        this.notify();
      }
    }, interval);

    this.state.pollingIntervalId = intervalId;
  }

  /**
   * Stop polling for task status updates
   * Cleans up the polling interval
   */
  stopPolling(): void {
    if (this.state.pollingIntervalId !== null) {
      window.clearInterval(this.state.pollingIntervalId);
      this.state.pollingIntervalId = null;
    }
  }

  /**
   * Clear all state and stop polling
   * Used when unmounting or switching tasks
   */
  reset(): void {
    this.stopPolling();
    this.state = {
      task: null,
      previousTask: null,
      isUpdating: false,
      error: null,
      pollingIntervalId: null,
    };
    this.notify();
  }
}

/**
 * Create a new TaskStore instance
 */
export function createTaskStore(): TaskStore {
  return new TaskStore();
}
