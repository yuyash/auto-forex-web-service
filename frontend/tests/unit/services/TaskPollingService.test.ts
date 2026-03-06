/**
 * Unit tests for TaskPollingService.
 *
 * Verifies polling lifecycle, callback dispatch, error handling,
 * backoff, and max-retry stop.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { TaskPollingService } from '../../../src/services/polling/TaskPollingService';
import { TaskStatus } from '../../../src/types/common';

// Mock the api module
vi.mock('../../../src/api/apiClient', () => ({
  api: {
    get: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(url: string, status: number, statusText: string) {
      super(`API Error: ${status} ${statusText}`);
      this.status = status;
    }
  },
}));

import { api } from '../../../src/api/apiClient';

const mockGet = vi.mocked(api.get);

const TASK_RESPONSE = {
  id: '42',
  status: TaskStatus.RUNNING,
  started_at: '2024-01-01T00:00:00Z',
  completed_at: null,
  error_message: null,
  name: 'Test Task',
};

describe('TaskPollingService', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockGet.mockReset();
    mockGet.mockResolvedValue(TASK_RESPONSE);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('calls onStatusUpdate with extracted status fields', async () => {
    const onStatusUpdate = vi.fn();
    const service = new TaskPollingService('42', 'backtest', {
      onStatusUpdate,
    });

    service.startPolling();
    // Let the initial poll resolve
    await vi.advanceTimersByTimeAsync(0);

    expect(onStatusUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        task_id: '42',
        task_type: 'backtest',
        status: TaskStatus.RUNNING,
      })
    );

    service.cleanup();
  });

  it('calls onDetailsUpdate with task data', async () => {
    const onDetailsUpdate = vi.fn();
    const service = new TaskPollingService('42', 'backtest', {
      onDetailsUpdate,
    });

    service.startPolling();
    await vi.advanceTimersByTimeAsync(0);

    expect(onDetailsUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        task: TASK_RESPONSE,
        current_execution: null,
      })
    );

    service.cleanup();
  });

  it('uses correct API URL for backtest tasks', async () => {
    const service = new TaskPollingService('42', 'backtest', {});
    service.startPolling();
    await vi.advanceTimersByTimeAsync(0);

    expect(mockGet).toHaveBeenCalledWith('/api/trading/tasks/backtest/42/');
    service.cleanup();
  });

  it('uses correct API URL for trading tasks', async () => {
    const service = new TaskPollingService('99', 'trading', {});
    service.startPolling();
    await vi.advanceTimersByTimeAsync(0);

    expect(mockGet).toHaveBeenCalledWith('/api/trading/tasks/trading/99/');
    service.cleanup();
  });

  it('polls at the configured interval', async () => {
    const onStatusUpdate = vi.fn();
    const service = new TaskPollingService(
      '42',
      'backtest',
      { onStatusUpdate },
      { interval: 5000 }
    );

    service.startPolling();
    await vi.advanceTimersByTimeAsync(0); // initial poll
    expect(onStatusUpdate).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(5000); // second poll
    expect(onStatusUpdate).toHaveBeenCalledTimes(2);

    await vi.advanceTimersByTimeAsync(5000); // third poll
    expect(onStatusUpdate).toHaveBeenCalledTimes(3);

    service.cleanup();
  });

  it('stops polling when stopPolling is called', async () => {
    const onStatusUpdate = vi.fn();
    const service = new TaskPollingService(
      '42',
      'backtest',
      { onStatusUpdate },
      { interval: 1000 }
    );

    service.startPolling();
    await vi.advanceTimersByTimeAsync(0);
    expect(onStatusUpdate).toHaveBeenCalledTimes(1);

    service.stopPolling();
    expect(service.isPolling()).toBe(false);

    await vi.advanceTimersByTimeAsync(5000);
    // No additional calls after stop
    expect(onStatusUpdate).toHaveBeenCalledTimes(1);
  });

  it('does not start polling twice', async () => {
    const service = new TaskPollingService('42', 'backtest', {});
    service.startPolling();
    service.startPolling(); // second call should be no-op
    await vi.advanceTimersByTimeAsync(0);

    expect(mockGet).toHaveBeenCalledTimes(1);
    service.cleanup();
  });

  it('calls onError and applies backoff on failure', async () => {
    const onError = vi.fn();
    mockGet.mockRejectedValue(new Error('Network error'));

    const service = new TaskPollingService(
      '42',
      'backtest',
      { onError },
      { interval: 1000, backoffMultiplier: 2, maxBackoff: 10000, maxRetries: 3 }
    );

    service.startPolling();
    await vi.advanceTimersByTimeAsync(0); // initial poll fails

    expect(onError).toHaveBeenCalledTimes(1);
    // Interval should have doubled
    expect(service.getCurrentInterval()).toBe(2000);

    service.cleanup();
  });

  it('stops polling after maxRetries consecutive errors', async () => {
    const onError = vi.fn();
    mockGet.mockRejectedValue(new Error('Network error'));

    const service = new TaskPollingService(
      '42',
      'backtest',
      { onError },
      { interval: 100, maxRetries: 2, backoffMultiplier: 1, maxBackoff: 100 }
    );

    service.startPolling();
    // Initial poll
    await vi.advanceTimersByTimeAsync(0);
    // Second poll
    await vi.advanceTimersByTimeAsync(100);

    expect(service.isPolling()).toBe(false);
    expect(onError).toHaveBeenCalledTimes(2);
  });

  it('resets retry count on successful poll', async () => {
    const onError = vi.fn();
    let callCount = 0;
    mockGet.mockImplementation(async () => {
      callCount++;
      if (callCount === 1) throw new Error('Temporary error');
      return TASK_RESPONSE;
    });

    const service = new TaskPollingService(
      '42',
      'backtest',
      { onError },
      { interval: 100, maxRetries: 3, backoffMultiplier: 2, maxBackoff: 1000 }
    );

    service.startPolling();
    await vi.advanceTimersByTimeAsync(0); // fails
    expect(service.getCurrentInterval()).toBe(200); // backed off

    await vi.advanceTimersByTimeAsync(200); // succeeds
    expect(service.getCurrentInterval()).toBe(100); // reset to base

    service.cleanup();
  });

  it('caps backoff at maxBackoff', async () => {
    mockGet.mockRejectedValue(new Error('fail'));

    const service = new TaskPollingService(
      '42',
      'backtest',
      {},
      {
        interval: 1000,
        maxRetries: 10,
        backoffMultiplier: 10,
        maxBackoff: 5000,
      }
    );

    service.startPolling();
    await vi.advanceTimersByTimeAsync(0); // first failure

    // After first failure: 1000 * 10 = 10000, capped at 5000
    expect(service.getCurrentInterval()).toBe(5000);

    service.cleanup();
  });

  it('updateCallbacks replaces callbacks', async () => {
    const onStatusUpdate1 = vi.fn();
    const onStatusUpdate2 = vi.fn();

    const service = new TaskPollingService('42', 'backtest', {
      onStatusUpdate: onStatusUpdate1,
    });
    service.startPolling();
    await vi.advanceTimersByTimeAsync(0);
    expect(onStatusUpdate1).toHaveBeenCalledTimes(1);

    service.updateCallbacks({ onStatusUpdate: onStatusUpdate2 });
    await vi.advanceTimersByTimeAsync(3000); // next poll
    expect(onStatusUpdate2).toHaveBeenCalledTimes(1);

    service.cleanup();
  });

  it('updateOptions changes polling interval', async () => {
    const onStatusUpdate = vi.fn();
    const service = new TaskPollingService(
      '42',
      'backtest',
      { onStatusUpdate },
      { interval: 1000 }
    );

    service.startPolling();
    await vi.advanceTimersByTimeAsync(0);

    service.updateOptions({ interval: 5000 });

    // Old interval (1000ms) should not trigger
    await vi.advanceTimersByTimeAsync(1000);
    // But the scheduled timeout was already set at 1000ms, so it fires
    // After that, the next schedule uses 5000ms
    const callsAfterUpdate = onStatusUpdate.mock.calls.length;

    await vi.advanceTimersByTimeAsync(5000);
    expect(onStatusUpdate.mock.calls.length).toBeGreaterThan(callsAfterUpdate);

    service.cleanup();
  });
});
