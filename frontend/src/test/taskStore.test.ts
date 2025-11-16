/**
 * Unit tests for TaskStore
 *
 * Tests:
 * - Optimistic updates
 * - Server confirmation
 * - Rollback on error
 * - Progress updates
 * - Polling fallback mechanism
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TaskStore, createTaskStore } from '../stores/taskStore';
import { TaskStatus, DataSource } from '../types/common';
import type { BacktestTask } from '../types';

describe('TaskStore', () => {
  let store: TaskStore;
  let mockTask: BacktestTask;

  beforeEach(() => {
    store = createTaskStore();

    // Create mock task
    mockTask = {
      id: 1,
      user_id: 1,
      config_id: 1,
      config_name: 'Test Config',
      strategy_type: 'MA_CROSSOVER',
      name: 'Test Task',
      description: 'Test description',
      data_source: DataSource.POSTGRESQL,
      start_time: '2025-01-01T00:00:00Z',
      end_time: '2025-01-03T00:00:00Z',
      initial_balance: '10000.00',
      commission_per_trade: '0.00',
      instrument: 'EUR_USD',
      status: TaskStatus.CREATED,
      latest_execution: {
        id: 1,
        execution_number: 1,
        status: TaskStatus.CREATED,
        progress: 0,
        started_at: '2025-01-01T00:00:00Z',
        completed_at: undefined,
        total_return: undefined,
        total_pnl: '0.00',
        total_trades: 0,
        win_rate: '0.00',
      },
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    };

    vi.useFakeTimers();
  });

  afterEach(() => {
    store.reset();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  describe('Basic State Management', () => {
    it('should initialize with null task', () => {
      expect(store.getTask()).toBeNull();
      expect(store.isUpdating()).toBe(false);
      expect(store.getError()).toBeNull();
    });

    it('should set task data', () => {
      store.setTask(mockTask);

      expect(store.getTask()).toEqual(mockTask);
      expect(store.getError()).toBeNull();
    });

    it('should clear error when setting task', () => {
      store.rollbackStatusUpdate(new Error('Test error'));
      expect(store.getError()).not.toBeNull();

      store.setTask(mockTask);
      expect(store.getError()).toBeNull();
    });

    it('should reset all state', () => {
      store.setTask(mockTask);
      store.optimisticUpdateStatus(TaskStatus.RUNNING);

      store.reset();

      expect(store.getTask()).toBeNull();
      expect(store.isUpdating()).toBe(false);
      expect(store.getError()).toBeNull();
    });
  });

  describe('Subscription and Notifications', () => {
    it('should notify subscribers on state change', () => {
      const listener = vi.fn();
      store.subscribe(listener);

      store.setTask(mockTask);

      expect(listener).toHaveBeenCalledWith(mockTask);
      expect(listener).toHaveBeenCalledTimes(1);
    });

    it('should support multiple subscribers', () => {
      const listener1 = vi.fn();
      const listener2 = vi.fn();

      store.subscribe(listener1);
      store.subscribe(listener2);

      store.setTask(mockTask);

      expect(listener1).toHaveBeenCalledWith(mockTask);
      expect(listener2).toHaveBeenCalledWith(mockTask);
    });

    it('should unsubscribe correctly', () => {
      const listener = vi.fn();
      const unsubscribe = store.subscribe(listener);

      store.setTask(mockTask);
      expect(listener).toHaveBeenCalledTimes(1);

      unsubscribe();
      store.setTask({ ...mockTask, name: 'Updated' });

      // Should not be called again after unsubscribe
      expect(listener).toHaveBeenCalledTimes(1);
    });
  });

  describe('Optimistic Updates', () => {
    beforeEach(() => {
      store.setTask(mockTask);
    });

    it('should optimistically update status', () => {
      store.optimisticUpdateStatus(TaskStatus.RUNNING);

      const task = store.getTask();
      expect(task?.status).toBe(TaskStatus.RUNNING);
      expect(store.isUpdating()).toBe(true);
      expect(store.getError()).toBeNull();
    });

    it('should store previous state for rollback', () => {
      const originalStatus = mockTask.status;

      store.optimisticUpdateStatus(TaskStatus.RUNNING);

      // Rollback should restore original status
      store.rollbackStatusUpdate(new Error('Test error'));

      const task = store.getTask();
      expect(task?.status).toBe(originalStatus);
    });

    it('should update timestamp on optimistic update', () => {
      const originalTimestamp = mockTask.updated_at;

      // Advance time
      vi.advanceTimersByTime(1000);

      store.optimisticUpdateStatus(TaskStatus.RUNNING);

      const task = store.getTask();
      expect(task?.updated_at).not.toBe(originalTimestamp);
    });

    it('should handle optimistic update without task', () => {
      const emptyStore = createTaskStore();
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      emptyStore.optimisticUpdateStatus(TaskStatus.RUNNING);

      expect(consoleSpy).toHaveBeenCalledWith(
        '[TaskStore] Cannot update status: no task loaded'
      );
      expect(emptyStore.getTask()).toBeNull();

      consoleSpy.mockRestore();
    });
  });

  describe('Server Confirmation', () => {
    beforeEach(() => {
      store.setTask(mockTask);
      store.optimisticUpdateStatus(TaskStatus.RUNNING);
    });

    it('should confirm status update from server', () => {
      store.confirmStatusUpdate(TaskStatus.RUNNING, 123);

      const task = store.getTask();
      expect(task?.status).toBe(TaskStatus.RUNNING);
      expect(task?.latest_execution?.id).toBe(123);
      expect(store.isUpdating()).toBe(false);
      expect(store.getError()).toBeNull();
    });

    it('should clear previous state on confirmation', () => {
      store.confirmStatusUpdate(TaskStatus.RUNNING);

      // Try to rollback - should not work since previous state is cleared
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      store.rollbackStatusUpdate(new Error('Test'));

      expect(consoleSpy).toHaveBeenCalledWith(
        '[TaskStore] Cannot rollback: no previous state'
      );

      consoleSpy.mockRestore();
    });

    it('should update execution_id when provided', () => {
      const executionId = 456;

      store.confirmStatusUpdate(TaskStatus.RUNNING, executionId);

      const task = store.getTask();
      expect(task?.latest_execution?.id).toBe(executionId);
    });

    it('should handle confirmation without execution_id', () => {
      const originalExecutionId = mockTask.latest_execution?.id;

      store.confirmStatusUpdate(TaskStatus.RUNNING);

      const task = store.getTask();
      expect(task?.latest_execution?.id).toBe(originalExecutionId);
    });

    it('should handle confirmation without task', () => {
      const emptyStore = createTaskStore();
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      emptyStore.confirmStatusUpdate(TaskStatus.RUNNING);

      expect(consoleSpy).toHaveBeenCalledWith(
        '[TaskStore] Cannot confirm status: no task loaded'
      );

      consoleSpy.mockRestore();
    });
  });

  describe('Rollback on Error', () => {
    beforeEach(() => {
      store.setTask(mockTask);
    });

    it('should rollback to previous state on error', () => {
      const originalStatus = mockTask.status;

      store.optimisticUpdateStatus(TaskStatus.RUNNING);
      expect(store.getTask()?.status).toBe(TaskStatus.RUNNING);

      const error = new Error('Failed to start task');
      store.rollbackStatusUpdate(error);

      const task = store.getTask();
      expect(task?.status).toBe(originalStatus);
      expect(store.isUpdating()).toBe(false);
      expect(store.getError()).toBe(error);
    });

    it('should clear previous state after rollback', () => {
      store.optimisticUpdateStatus(TaskStatus.RUNNING);
      store.rollbackStatusUpdate(new Error('Test error'));

      // Try to rollback again - should not work
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      store.rollbackStatusUpdate(new Error('Another error'));

      expect(consoleSpy).toHaveBeenCalledWith(
        '[TaskStore] Cannot rollback: no previous state'
      );

      consoleSpy.mockRestore();
    });

    it('should handle rollback without previous state', () => {
      const error = new Error('Test error');
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      store.rollbackStatusUpdate(error);

      expect(consoleSpy).toHaveBeenCalledWith(
        '[TaskStore] Cannot rollback: no previous state'
      );
      expect(store.getError()).toBe(error);
      expect(store.isUpdating()).toBe(false);

      consoleSpy.mockRestore();
    });
  });

  describe('Progress Updates', () => {
    beforeEach(() => {
      store.setTask({
        ...mockTask,
        status: TaskStatus.RUNNING,
      });
    });

    it('should update progress for running task', () => {
      store.updateProgress(50);

      const task = store.getTask();
      expect(task?.latest_execution?.progress).toBe(50);
    });

    it('should clamp progress to 0-100 range', () => {
      store.updateProgress(150);
      expect(store.getTask()?.latest_execution?.progress).toBe(100);

      store.updateProgress(-10);
      expect(store.getTask()?.latest_execution?.progress).toBe(0);
    });

    it('should not update progress for non-running task', () => {
      store.setTask({
        ...mockTask,
        status: TaskStatus.COMPLETED,
      });

      const originalProgress = mockTask.latest_execution?.progress;

      store.updateProgress(75);

      const task = store.getTask();
      expect(task?.latest_execution?.progress).toBe(originalProgress);
    });

    it('should handle progress update without task', () => {
      const emptyStore = createTaskStore();
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      emptyStore.updateProgress(50);

      expect(consoleSpy).toHaveBeenCalledWith(
        '[TaskStore] Cannot update progress: no task loaded'
      );

      consoleSpy.mockRestore();
    });

    it('should handle progress update without latest_execution', () => {
      store.setTask({
        ...mockTask,
        status: TaskStatus.RUNNING,
        latest_execution: undefined,
      });

      // Should not throw error
      store.updateProgress(50);

      const task = store.getTask();
      expect(task?.latest_execution).toBeUndefined();
    });

    it('should notify subscribers on progress update', () => {
      const listener = vi.fn();
      store.subscribe(listener);

      store.updateProgress(25);
      store.updateProgress(50);
      store.updateProgress(75);

      expect(listener).toHaveBeenCalledTimes(3);
    });
  });

  describe('Polling Fallback', () => {
    it('should start polling with custom interval', async () => {
      const fetchFn = vi.fn().mockResolvedValue(mockTask);

      store.startPolling(1, fetchFn, 1000);

      // Should not call immediately
      expect(fetchFn).not.toHaveBeenCalled();

      // Advance time by interval
      await vi.advanceTimersByTimeAsync(1000);

      expect(fetchFn).toHaveBeenCalledWith(1);
      expect(fetchFn).toHaveBeenCalledTimes(1);

      // Advance again
      await vi.advanceTimersByTimeAsync(1000);

      expect(fetchFn).toHaveBeenCalledTimes(2);
    });

    it('should use default interval of 3000ms', async () => {
      const fetchFn = vi.fn().mockResolvedValue(mockTask);

      store.startPolling(1, fetchFn);

      await vi.advanceTimersByTimeAsync(3000);

      expect(fetchFn).toHaveBeenCalledTimes(1);
    });

    it('should update task on successful poll', async () => {
      const updatedTask = { ...mockTask, status: TaskStatus.RUNNING };
      const fetchFn = vi.fn().mockResolvedValue(updatedTask);

      store.startPolling(1, fetchFn, 1000);

      await vi.advanceTimersByTimeAsync(1000);

      expect(store.getTask()).toEqual(updatedTask);
    });

    it('should handle polling errors', async () => {
      const error = new Error('Network error');
      const fetchFn = vi.fn().mockRejectedValue(error);
      const consoleSpy = vi
        .spyOn(console, 'error')
        .mockImplementation(() => {});

      store.startPolling(1, fetchFn, 1000);

      await vi.advanceTimersByTimeAsync(1000);

      expect(consoleSpy).toHaveBeenCalledWith(
        '[TaskStore] Polling error:',
        error
      );
      expect(store.getError()).toBe(error);

      consoleSpy.mockRestore();
    });

    it('should stop existing polling when starting new poll', async () => {
      const fetchFn1 = vi.fn().mockResolvedValue(mockTask);
      const fetchFn2 = vi.fn().mockResolvedValue(mockTask);

      store.startPolling(1, fetchFn1, 1000);
      await vi.advanceTimersByTimeAsync(1000);

      expect(fetchFn1).toHaveBeenCalledTimes(1);

      // Start new polling
      store.startPolling(2, fetchFn2, 1000);
      await vi.advanceTimersByTimeAsync(1000);

      // First polling should be stopped
      expect(fetchFn1).toHaveBeenCalledTimes(1);
      expect(fetchFn2).toHaveBeenCalledTimes(1);
    });

    it('should stop polling', async () => {
      const fetchFn = vi.fn().mockResolvedValue(mockTask);

      store.startPolling(1, fetchFn, 1000);

      await vi.advanceTimersByTimeAsync(1000);
      expect(fetchFn).toHaveBeenCalledTimes(1);

      store.stopPolling();

      await vi.advanceTimersByTimeAsync(1000);
      // Should not be called again
      expect(fetchFn).toHaveBeenCalledTimes(1);
    });

    it('should stop polling on reset', async () => {
      const fetchFn = vi.fn().mockResolvedValue(mockTask);

      store.startPolling(1, fetchFn, 1000);

      await vi.advanceTimersByTimeAsync(1000);
      expect(fetchFn).toHaveBeenCalledTimes(1);

      store.reset();

      await vi.advanceTimersByTimeAsync(1000);
      // Should not be called again
      expect(fetchFn).toHaveBeenCalledTimes(1);
    });

    it('should handle stopPolling when not polling', () => {
      // Should not throw error
      expect(() => store.stopPolling()).not.toThrow();
    });
  });

  describe('Integration Scenarios', () => {
    it('should handle complete optimistic update flow', () => {
      // 1. Set initial task
      store.setTask(mockTask);
      expect(store.getTask()?.status).toBe(TaskStatus.CREATED);

      // 2. Optimistic update to running
      store.optimisticUpdateStatus(TaskStatus.RUNNING);
      expect(store.getTask()?.status).toBe(TaskStatus.RUNNING);
      expect(store.isUpdating()).toBe(true);

      // 3. Confirm from server
      store.confirmStatusUpdate(TaskStatus.RUNNING, 123);
      expect(store.getTask()?.status).toBe(TaskStatus.RUNNING);
      expect(store.getTask()?.latest_execution?.id).toBe(123);
      expect(store.isUpdating()).toBe(false);

      // 4. Update progress
      store.updateProgress(50);
      expect(store.getTask()?.latest_execution?.progress).toBe(50);
    });

    it('should handle failed optimistic update with rollback', () => {
      // 1. Set initial task
      store.setTask(mockTask);
      const originalStatus = mockTask.status;

      // 2. Optimistic update to running
      store.optimisticUpdateStatus(TaskStatus.RUNNING);
      expect(store.getTask()?.status).toBe(TaskStatus.RUNNING);

      // 3. Server returns error - rollback
      const error = new Error('Failed to start');
      store.rollbackStatusUpdate(error);

      expect(store.getTask()?.status).toBe(originalStatus);
      expect(store.isUpdating()).toBe(false);
      expect(store.getError()).toBe(error);
    });

    it('should handle WebSocket failure with polling fallback', async () => {
      const fetchFn = vi.fn().mockResolvedValue({
        ...mockTask,
        status: TaskStatus.RUNNING,
      });

      // Start polling as fallback
      store.startPolling(1, fetchFn, 1000);

      // Simulate multiple polls
      await vi.advanceTimersByTimeAsync(3000);

      expect(fetchFn).toHaveBeenCalledTimes(3);
      expect(store.getTask()?.status).toBe(TaskStatus.RUNNING);
    });
  });
});
