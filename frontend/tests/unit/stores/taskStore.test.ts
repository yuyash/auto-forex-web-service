/**
 * Unit tests for TaskStore — optimistic updates, rollback, polling.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { TaskStore } from '../../../src/stores/taskStore';
import { TaskStatus } from '../../../src/types/common';
import type { BacktestTask } from '../../../src/types';

function makeTask(overrides: Partial<BacktestTask> = {}): BacktestTask {
  return {
    id: 1,
    name: 'Test Task',
    status: TaskStatus.CREATED,
    config_name: 'cfg',
    config_id: 1,
    strategy_type: 'floor',
    instrument: 'EUR_USD',
    pip_size: '0.0001',
    data_source: 'oanda',
    initial_balance: '10000',
    commission_per_trade: '0',
    start_time: '2024-01-01T00:00:00Z',
    end_time: '2024-01-02T00:00:00Z',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    latest_execution: null,
    celery_task_id: null,
    progress: 0,
    ...overrides,
  } as BacktestTask;
}

describe('TaskStore', () => {
  let store: TaskStore;

  beforeEach(() => {
    store = new TaskStore();
    vi.useFakeTimers();
  });

  afterEach(() => {
    store.reset();
    vi.useRealTimers();
  });

  it('sets and retrieves task', () => {
    const task = makeTask();
    store.setTask(task);
    expect(store.getTask()?.name).toBe('Test Task');
  });

  it('notifies listeners on state change', () => {
    const listener = vi.fn();
    store.subscribe(listener);
    store.setTask(makeTask());
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('unsubscribes listeners', () => {
    const listener = vi.fn();
    const unsub = store.subscribe(listener);
    unsub();
    store.setTask(makeTask());
    expect(listener).not.toHaveBeenCalled();
  });

  describe('optimistic updates', () => {
    it('applies optimistic status update', () => {
      store.setTask(makeTask());
      store.optimisticUpdateStatus(TaskStatus.RUNNING);
      expect(store.getTask()?.status).toBe(TaskStatus.RUNNING);
      expect(store.isUpdating()).toBe(true);
    });

    it('confirms status update', () => {
      store.setTask(makeTask());
      store.optimisticUpdateStatus(TaskStatus.RUNNING);
      store.confirmStatusUpdate(TaskStatus.RUNNING);
      expect(store.getTask()?.status).toBe(TaskStatus.RUNNING);
      expect(store.isUpdating()).toBe(false);
    });

    it('rolls back on error', () => {
      store.setTask(makeTask({ status: TaskStatus.CREATED }));
      store.optimisticUpdateStatus(TaskStatus.RUNNING);
      store.rollbackStatusUpdate(new Error('API failed'));

      expect(store.getTask()?.status).toBe(TaskStatus.CREATED);
      expect(store.isUpdating()).toBe(false);
      expect(store.getError()?.message).toBe('API failed');
    });

    it('handles rollback without previous state', () => {
      store.setTask(makeTask());
      store.rollbackStatusUpdate(new Error('No previous'));
      expect(store.getError()?.message).toBe('No previous');
    });
  });

  describe('progress', () => {
    it('updates progress for running tasks', () => {
      store.setTask(
        makeTask({
          status: TaskStatus.RUNNING,
          latest_execution: { id: '1', progress: 0 } as never,
        })
      );
      store.updateProgress(50);
      expect(store.getTask()?.latest_execution?.progress).toBe(50);
    });

    it('clamps progress to 0-100', () => {
      store.setTask(
        makeTask({
          status: TaskStatus.RUNNING,
          latest_execution: { id: '1', progress: 0 } as never,
        })
      );
      store.updateProgress(150);
      expect(store.getTask()?.latest_execution?.progress).toBe(100);
    });

    it('ignores progress for non-running tasks', () => {
      store.setTask(
        makeTask({
          status: TaskStatus.COMPLETED,
          latest_execution: { id: '1', progress: 100 } as never,
        })
      );
      store.updateProgress(50);
      expect(store.getTask()?.latest_execution?.progress).toBe(100);
    });
  });

  describe('polling', () => {
    it('starts and stops polling', () => {
      const fetchFn = vi.fn().mockResolvedValue(makeTask());
      store.startPolling('1', fetchFn, 1000);

      // Advance one interval tick
      vi.advanceTimersByTime(1000);

      store.stopPolling();
      expect(fetchFn).toHaveBeenCalled();
    });

    it('stops previous polling when starting new one', () => {
      const fetchFn1 = vi.fn().mockResolvedValue(makeTask());
      const fetchFn2 = vi.fn().mockResolvedValue(makeTask());

      store.startPolling('1', fetchFn1, 1000);
      store.startPolling('2', fetchFn2, 1000);

      vi.advanceTimersByTime(1000);
      store.stopPolling();

      // Only the second fetch should have been called
      expect(fetchFn2).toHaveBeenCalled();
    });
  });

  it('resets all state', () => {
    store.setTask(makeTask());
    store.reset();
    expect(store.getTask()).toBeNull();
    expect(store.isUpdating()).toBe(false);
    expect(store.getError()).toBeNull();
  });
});
