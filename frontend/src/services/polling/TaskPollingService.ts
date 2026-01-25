// Task Polling Service - HTTP polling for task status and details

import { TradingService } from '../../api/generated/services/TradingService';
import type { BacktestTask, TradingTask } from '../../types';
import type { ExecutionSummary } from '../../types/execution';
import { TaskStatus } from '../../types/common';

export type TaskType = 'backtest' | 'trading';

export interface TaskStatusResponse {
  task_id: number;
  task_type: TaskType;
  status: TaskStatus;
  progress: number;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  pending_new_execution?: boolean; // True when task is RUNNING but new execution hasn't started
}

export interface TaskDetailsResponse {
  task: BacktestTask | TradingTask;
  current_execution: ExecutionSummary | null;
}

export interface PollingCallbacks {
  onStatusUpdate?: (status: TaskStatusResponse) => void;
  onDetailsUpdate?: (details: TaskDetailsResponse) => void;
  onError?: (error: Error) => void;
}

export interface PollingOptions {
  interval?: number; // milliseconds
  maxRetries?: number;
  backoffMultiplier?: number;
  maxBackoff?: number;
}

interface PollingState {
  intervalId: number | null;
  isPolling: boolean;
  retryCount: number;
  currentInterval: number;
  lastStatus: TaskStatus | null;
}

/**
 * TaskPollingService manages HTTP polling for task updates
 *
 * Features:
 * - Configurable polling intervals (2-5 seconds for active tasks)
 * - Exponential backoff on errors
 * - Automatic cleanup on component unmount
 * - Stops polling when task completes or fails
 */
export class TaskPollingService {
  private taskId: number;
  private taskType: TaskType;
  private callbacks: PollingCallbacks;
  private options: Required<PollingOptions>;
  private state: PollingState;

  constructor(
    taskId: number,
    taskType: TaskType,
    callbacks: PollingCallbacks = {},
    options: PollingOptions = {}
  ) {
    this.taskId = taskId;
    this.taskType = taskType;
    this.callbacks = callbacks;
    this.options = {
      interval: options.interval ?? 3000, // Default 3 seconds
      maxRetries: options.maxRetries ?? 5,
      backoffMultiplier: options.backoffMultiplier ?? 2,
      maxBackoff: options.maxBackoff ?? 30000, // Max 30 seconds
    };
    this.state = {
      intervalId: null,
      isPolling: false,
      retryCount: 0,
      currentInterval: this.options.interval,
      lastStatus: null,
    };
  }

  /**
   * Start polling for task updates
   */
  public startPolling(): void {
    if (this.state.isPolling) {
      return;
    }

    this.state.isPolling = true;
    this.state.retryCount = 0;
    this.state.currentInterval = this.options.interval;

    // Fetch immediately
    this.poll();

    // Then set up interval
    this.scheduleNextPoll();
  }

  /**
   * Stop polling
   */
  public stopPolling(): void {
    if (this.state.intervalId !== null) {
      window.clearTimeout(this.state.intervalId);
      this.state.intervalId = null;
    }
    this.state.isPolling = false;
  }

  /**
   * Cleanup resources
   */
  public cleanup(): void {
    this.stopPolling();
  }

  /**
   * Check if currently polling
   */
  public isPolling(): boolean {
    return this.state.isPolling;
  }

  /**
   * Get current polling interval
   */
  public getCurrentInterval(): number {
    return this.state.currentInterval;
  }

  /**
   * Schedule the next poll
   */
  private scheduleNextPoll(): void {
    if (!this.state.isPolling) {
      return;
    }

    this.state.intervalId = window.setTimeout(() => {
      this.poll();
      this.scheduleNextPoll();
    }, this.state.currentInterval);
  }

  /**
   * Perform a single poll operation
   */
  private async poll(): Promise<void> {
    try {
      // Fetch status
      const status = await this.fetchStatus();

      if (this.callbacks.onStatusUpdate) {
        this.callbacks.onStatusUpdate(status);
      }

      // Update last known status
      this.state.lastStatus = status.status;

      // Reset retry count on success
      this.state.retryCount = 0;
      this.state.currentInterval = this.options.interval;

      // Stop polling if task is in terminal state
      if (this.isTerminalStatus(status.status)) {
        this.stopPolling();
      }

      // Optionally fetch details
      if (this.callbacks.onDetailsUpdate) {
        const details = await this.fetchDetails();
        this.callbacks.onDetailsUpdate(details);
      }
    } catch (error) {
      this.handleError(error as Error);
    }
  }

  /**
   * Fetch task status
   */
  private async fetchStatus(): Promise<TaskStatusResponse> {
    const task =
      this.taskType === 'backtest'
        ? await TradingService.tradingTasksBacktestRetrieve(this.taskId)
        : await TradingService.tradingTasksTradingRetrieve(this.taskId);

    return {
      task_id: task.id,
      task_type: this.taskType,
      status: task.status as TaskStatus,
      progress: 0,
      started_at: task.started_at || null,
      completed_at: task.completed_at || null,
      error_message: task.error_message || null,
    };
  }

  /**
   * Fetch task details
   */
  private async fetchDetails(): Promise<TaskDetailsResponse> {
    const task =
      this.taskType === 'backtest'
        ? await TradingService.tradingTasksBacktestRetrieve(this.taskId)
        : await TradingService.tradingTasksTradingRetrieve(this.taskId);

    return {
      task: task as BacktestTask | TradingTask,
      current_execution: null,
    };
  }

  /**
   * Handle polling errors with exponential backoff
   */
  private handleError(error: Error): void {
    this.state.retryCount++;

    if (this.callbacks.onError) {
      this.callbacks.onError(error);
    }

    // Stop polling if max retries exceeded
    if (this.state.retryCount >= this.options.maxRetries) {
      console.error(
        `Max retries (${this.options.maxRetries}) exceeded. Stopping polling.`
      );
      this.stopPolling();
      return;
    }

    // Apply exponential backoff
    this.state.currentInterval = Math.min(
      this.state.currentInterval * this.options.backoffMultiplier,
      this.options.maxBackoff
    );

    console.warn(
      `Polling error (retry ${this.state.retryCount}/${this.options.maxRetries}). ` +
        `Next attempt in ${this.state.currentInterval}ms`
    );
  }

  /**
   * Check if status is terminal (completed, failed, stopped)
   */
  private isTerminalStatus(status: TaskStatus): boolean {
    return (
      status === TaskStatus.COMPLETED ||
      status === TaskStatus.FAILED ||
      status === TaskStatus.STOPPED
    );
  }

  /**
   * Update callbacks
   */
  public updateCallbacks(callbacks: PollingCallbacks): void {
    this.callbacks = { ...this.callbacks, ...callbacks };
  }

  /**
   * Update polling options
   */
  public updateOptions(options: PollingOptions): void {
    this.options = { ...this.options, ...options };

    // If interval changed and currently polling, restart with new interval
    if (options.interval && this.state.isPolling) {
      this.state.currentInterval = options.interval;
    }
  }
}
