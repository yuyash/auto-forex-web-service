/**
 * Unit tests for TaskPollingService
 *
 * Tests:
 * - Polling start/stop behavior
 * - Interval adjustments based on task status
 * - Error handling and exponential backoff
 * - Cleanup on unmount
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  TaskPollingService,
  type TaskStatusResponse,
  type TaskDetailsResponse,
  type TaskLogsResponse,
  type PollingCallbacks,
} from '../services/polling/TaskPollingService';
import { TaskStatus } from '../types/common';
import { apiClient } from '../services/api/client';

// Mock the API client
vi.mock('../services/api/client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

describe('TaskPollingService', () => {
  let service: TaskPollingService;
  let callbacks: PollingCallbacks;
  let mockStatusResponse: TaskStatusResponse;
  let mockDetailsResponse: TaskDetailsResponse;
  let mockLogsResponse: TaskLogsResponse;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();

    // Setup mock responses
    mockStatusResponse = {
      task_id: 1,
      task_type: 'backtest',
      status: TaskStatus.RUNNING,
      progress: 50,
      started_at: '2025-01-01T00:00:00Z',
      completed_at: null,
      error_message: null,
    };

    mockDetailsResponse = {
      task: {
        id: 1,
        user_id: 1,
        config_id: 1,
        config_name: 'Test Config',
        strategy_type: 'MA_CROSSOVER',
        name: 'Test Task',
        description: 'Test description',
        data_source: 'postgresql',
        start_time: '2025-01-01T00:00:00Z',
        end_time: '2025-01-03T00:00:00Z',
        initial_balance: '10000.00',
        commission_per_trade: '0.00',
        instrument: 'EUR_USD',
        status: TaskStatus.RUNNING,
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-01T00:00:00Z',
      },
      current_execution: null,
    };

    mockLogsResponse = {
      count: 2,
      next: null,
      previous: null,
      results: [
        {
          timestamp: '2025-01-01T00:00:00Z',
          level: 'INFO',
          message: 'Starting task',
        },
        {
          timestamp: '2025-01-01T00:00:01Z',
          level: 'INFO',
          message: 'Processing data',
        },
      ],
    };

    // Setup callbacks
    callbacks = {
      onStatusUpdate: vi.fn(),
      onDetailsUpdate: vi.fn(),
      onLogsUpdate: vi.fn(),
      onError: vi.fn(),
    };

    // Mock API responses
    vi.mocked(apiClient.get).mockResolvedValue(mockStatusResponse);
  });

  afterEach(() => {
    if (service) {
      service.cleanup();
    }
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  describe('Initialization', () => {
    it('should create service with default options', () => {
      service = new TaskPollingService(1, 'backtest', callbacks);

      expect(service).toBeDefined();
      expect(service.isPolling()).toBe(false);
      expect(service.getCurrentInterval()).toBe(3000); // Default interval
    });

    it('should create service with custom options', () => {
      service = new TaskPollingService(1, 'backtest', callbacks, {
        interval: 5000,
        maxRetries: 10,
        backoffMultiplier: 3,
        maxBackoff: 60000,
      });

      expect(service.getCurrentInterval()).toBe(5000);
    });

    it('should accept empty callbacks', () => {
      service = new TaskPollingService(1, 'backtest');

      expect(service).toBeDefined();
    });
  });

  describe('Polling Start/Stop', () => {
    beforeEach(() => {
      vi.clearAllMocks();
      service = new TaskPollingService(1, 'backtest', callbacks, {
        interval: 1000,
      });
    });

    it('should start polling and fetch immediately', async () => {
      service.startPolling();

      expect(service.isPolling()).toBe(true);

      // Wait for immediate fetch
      await vi.runOnlyPendingTimersAsync();

      expect(apiClient.get).toHaveBeenCalledWith(
        '/trading/backtest-tasks/1/status/'
      );
      expect(callbacks.onStatusUpdate).toHaveBeenCalledWith(mockStatusResponse);
    });

    it('should poll at specified interval', async () => {
      service.startPolling();

      // Initial fetch happens immediately (synchronously in poll())
      // Wait for any promises to resolve
      await Promise.resolve();
      const initialCalls = vi.mocked(apiClient.get).mock.calls.length;
      expect(initialCalls).toBeGreaterThanOrEqual(1);

      // Advance by interval - this will trigger polls
      await vi.advanceTimersByTimeAsync(1000);
      const afterFirstInterval = vi.mocked(apiClient.get).mock.calls.length;
      expect(afterFirstInterval).toBeGreaterThan(initialCalls);

      // Advance again - should trigger more polls
      await vi.advanceTimersByTimeAsync(1000);
      const afterSecondInterval = vi.mocked(apiClient.get).mock.calls.length;
      expect(afterSecondInterval).toBeGreaterThan(afterFirstInterval);

      // Verify polling is still active
      expect(service.isPolling()).toBe(true);
    });

    it('should not start polling if already polling', async () => {
      service.startPolling();
      await vi.runOnlyPendingTimersAsync();

      const callCount = vi.mocked(apiClient.get).mock.calls.length;

      // Try to start again
      service.startPolling();

      // Should not increase call count (no new timers scheduled)
      expect(vi.mocked(apiClient.get).mock.calls.length).toBe(callCount);
    });

    it('should stop polling', async () => {
      service.startPolling();
      await vi.runOnlyPendingTimersAsync();

      const callCount = vi.mocked(apiClient.get).mock.calls.length;

      service.stopPolling();
      expect(service.isPolling()).toBe(false);

      // Advance time - should not poll
      await vi.advanceTimersByTimeAsync(1000);
      expect(apiClient.get).toHaveBeenCalledTimes(callCount);
    });

    it('should cleanup resources', async () => {
      service.startPolling();
      await vi.runOnlyPendingTimersAsync();

      const callCount = vi.mocked(apiClient.get).mock.calls.length;

      service.cleanup();

      expect(service.isPolling()).toBe(false);

      // Advance time - should not poll
      await vi.advanceTimersByTimeAsync(1000);
      expect(apiClient.get).toHaveBeenCalledTimes(callCount);
    });
  });

  describe('Terminal Status Handling', () => {
    beforeEach(() => {
      service = new TaskPollingService(1, 'backtest', callbacks, {
        interval: 1000,
      });
    });

    it('should stop polling when task completes', async () => {
      // First poll returns running
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        ...mockStatusResponse,
        status: TaskStatus.RUNNING,
      });

      service.startPolling();
      await vi.runOnlyPendingTimersAsync();

      expect(service.isPolling()).toBe(true);

      // Second poll returns completed
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        ...mockStatusResponse,
        status: TaskStatus.COMPLETED,
        completed_at: '2025-01-01T01:00:00Z',
      });

      await vi.advanceTimersByTimeAsync(1000);

      expect(service.isPolling()).toBe(false);
    });

    it('should stop polling when task fails', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        ...mockStatusResponse,
        status: TaskStatus.FAILED,
        error_message: 'Task failed',
      });

      service.startPolling();
      await vi.runOnlyPendingTimersAsync();

      expect(service.isPolling()).toBe(false);
    });

    it('should stop polling when task is stopped', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        ...mockStatusResponse,
        status: TaskStatus.STOPPED,
      });

      service.startPolling();
      await vi.runOnlyPendingTimersAsync();

      expect(service.isPolling()).toBe(false);
    });

    it('should continue polling for pending status', async () => {
      vi.mocked(apiClient.get).mockResolvedValue({
        ...mockStatusResponse,
        status: TaskStatus.CREATED,
      });

      service.startPolling();
      await vi.runOnlyPendingTimersAsync();

      expect(service.isPolling()).toBe(true);

      await vi.advanceTimersByTimeAsync(1000);
      expect(service.isPolling()).toBe(true);
    });
  });

  describe('Error Handling and Backoff', () => {
    beforeEach(() => {
      vi.clearAllMocks();
      service = new TaskPollingService(1, 'backtest', callbacks, {
        interval: 1000,
        maxRetries: 3,
        backoffMultiplier: 2,
        maxBackoff: 10000,
      });
    });

    it('should handle API errors', async () => {
      const error = new Error('Network error');
      vi.mocked(apiClient.get).mockRejectedValueOnce(error);

      service.startPolling();
      await vi.runOnlyPendingTimersAsync();

      expect(callbacks.onError).toHaveBeenCalledWith(error);
      expect(service.isPolling()).toBe(true); // Should continue polling
    });

    it('should apply exponential backoff on errors', async () => {
      const error = new Error('Network error');
      vi.mocked(apiClient.get).mockRejectedValue(error);

      service.startPolling();

      // First error happens immediately, then schedules next poll with doubled interval
      // runAllTimersAsync will run all pending timers recursively until max retries
      await vi.runAllTimersAsync();

      // After running all timers until max retries (5), polling should have stopped
      // and interval should have been backed off multiple times
      const finalInterval = service.getCurrentInterval();

      // Verify that backoff was applied (interval increased from initial 1000)
      expect(finalInterval).toBeGreaterThan(1000);
      // Verify max backoff was respected (30000 is the max)
      expect(finalInterval).toBeLessThanOrEqual(30000);
      // Verify polling stopped after max retries
      expect(service.isPolling()).toBe(false);
    });

    it('should respect max backoff limit', async () => {
      const error = new Error('Network error');
      vi.mocked(apiClient.get).mockRejectedValue(error);

      service.startPolling();

      // Keep failing until we hit max backoff
      await vi.runOnlyPendingTimersAsync();
      await vi.advanceTimersByTimeAsync(2000);
      await vi.advanceTimersByTimeAsync(4000);
      await vi.advanceTimersByTimeAsync(8000);

      // Should not exceed maxBackoff of 10000
      expect(service.getCurrentInterval()).toBeLessThanOrEqual(10000);
    });

    it('should stop polling after max retries', async () => {
      const error = new Error('Network error');
      vi.mocked(apiClient.get).mockRejectedValue(error);

      const consoleSpy = vi
        .spyOn(console, 'error')
        .mockImplementation(() => {});

      service.startPolling();

      // Fail 3 times (maxRetries)
      await vi.runOnlyPendingTimersAsync();
      await vi.advanceTimersByTimeAsync(2000);
      await vi.advanceTimersByTimeAsync(4000);

      expect(service.isPolling()).toBe(false);
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('Max retries (3) exceeded')
      );

      consoleSpy.mockRestore();
    });

    it('should reset retry count on successful poll', async () => {
      const error = new Error('Network error');

      // First poll fails
      vi.mocked(apiClient.get).mockRejectedValueOnce(error);

      service.startPolling();
      await vi.advanceTimersByTimeAsync(0);

      const backoffInterval = service.getCurrentInterval();
      expect(backoffInterval).toBe(2000); // Backoff applied

      // Second poll succeeds
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockStatusResponse);

      await vi.advanceTimersByTimeAsync(backoffInterval);

      // Interval should reset to original
      expect(service.getCurrentInterval()).toBe(1000);
    });
  });

  describe('Callback Invocation', () => {
    beforeEach(() => {
      service = new TaskPollingService(1, 'backtest', callbacks, {
        interval: 1000,
      });
    });

    it('should call onStatusUpdate callback', async () => {
      service.startPolling();
      await vi.runOnlyPendingTimersAsync();

      expect(callbacks.onStatusUpdate).toHaveBeenCalledWith(mockStatusResponse);
    });

    it('should call onDetailsUpdate callback when provided', async () => {
      vi.mocked(apiClient.get)
        .mockResolvedValueOnce(mockStatusResponse)
        .mockResolvedValueOnce(mockDetailsResponse.task);

      service.startPolling();
      await vi.runOnlyPendingTimersAsync();

      expect(callbacks.onDetailsUpdate).toHaveBeenCalledWith(
        expect.objectContaining({
          task: mockDetailsResponse.task,
        })
      );
    });

    it('should call onLogsUpdate callback when provided', async () => {
      vi.mocked(apiClient.get)
        .mockResolvedValueOnce(mockStatusResponse)
        .mockResolvedValueOnce(mockDetailsResponse.task)
        .mockResolvedValueOnce(mockLogsResponse);

      service.startPolling();
      await vi.runOnlyPendingTimersAsync();

      expect(callbacks.onLogsUpdate).toHaveBeenCalledWith(mockLogsResponse);
    });

    it('should not call callbacks if not provided', async () => {
      const minimalCallbacks = {
        onStatusUpdate: vi.fn(),
      };

      service = new TaskPollingService(1, 'backtest', minimalCallbacks, {
        interval: 1000,
      });

      service.startPolling();
      await vi.runOnlyPendingTimersAsync();

      expect(minimalCallbacks.onStatusUpdate).toHaveBeenCalled();
      // Should not throw errors for missing callbacks
    });
  });

  describe('Dynamic Updates', () => {
    beforeEach(() => {
      vi.clearAllMocks();
      service = new TaskPollingService(1, 'backtest', callbacks, {
        interval: 1000,
      });
    });

    it('should update callbacks dynamically', async () => {
      const newCallback = vi.fn();

      service.startPolling();
      await vi.runOnlyPendingTimersAsync();

      const oldCallbackCount = callbacks.onStatusUpdate.mock.calls.length;

      // Update callbacks
      service.updateCallbacks({
        onStatusUpdate: newCallback,
      });

      await vi.advanceTimersByTimeAsync(1000);

      expect(newCallback).toHaveBeenCalledTimes(1);
      expect(callbacks.onStatusUpdate).toHaveBeenCalledTimes(oldCallbackCount); // Old callback not called again
    });

    it('should update polling options dynamically', async () => {
      service.startPolling();
      await vi.runOnlyPendingTimersAsync();

      expect(service.getCurrentInterval()).toBe(1000);

      // Update interval
      service.updateOptions({ interval: 2000 });

      expect(service.getCurrentInterval()).toBe(2000);
    });
  });

  describe('API Endpoint Construction', () => {
    it('should use correct endpoint for backtest tasks', async () => {
      service = new TaskPollingService(123, 'backtest', callbacks);

      service.startPolling();
      await vi.runOnlyPendingTimersAsync();

      expect(apiClient.get).toHaveBeenCalledWith(
        '/trading/backtest-tasks/123/status/'
      );
    });

    it('should use correct endpoint for trading tasks', async () => {
      service = new TaskPollingService(456, 'trading', callbacks);

      service.startPolling();
      await vi.runOnlyPendingTimersAsync();

      expect(apiClient.get).toHaveBeenCalledWith(
        '/trading/trading-tasks/456/status/'
      );
    });
  });
});
