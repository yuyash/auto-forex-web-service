// Task Polling Service - HTTP polling for task status updates
//
// Polls the task detail endpoint once per cycle and dispatches
// both status and detail callbacks from the single response,
// eliminating the duplicate GET that existed previously.

import { api } from '../../api/apiClient';
import type { BacktestTask, TradingTask } from '../../types';
import type { ExecutionSummary } from '../../types/execution';
import { TaskStatus } from '../../types/common';

export type TaskType = 'backtest' | 'trading';

export interface TaskStatusResponse {
  task_id: string;
  task_type: TaskType;
  status: TaskStatus;
  progress: number;
  current_tick?: {
    timestamp: string;
    price: string | null;
  } | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  pending_new_execution?: boolean;
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
  interval?: number;
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
 * TaskPollingService manages HTTP polling for task updates.
 *
 * Key improvement: a single GET per cycle feeds both the status
 * and details callbacks, so we never duplicate the request.
 */
export class TaskPollingService {
  private taskId: string;
  private taskType: TaskType;
  private callbacks: PollingCallbacks;
  private options: Required<PollingOptions>;
  private state: PollingState;

  constructor(
    taskId: string,
    taskType: TaskType,
    callbacks: PollingCallbacks = {},
    options: PollingOptions = {}
  ) {
    this.taskId = taskId;
    this.taskType = taskType;
    this.callbacks = callbacks;
    this.options = {
      interval: options.interval ?? 3000,
      maxRetries: options.maxRetries ?? 5,
      backoffMultiplier: options.backoffMultiplier ?? 2,
      maxBackoff: options.maxBackoff ?? 30000,
    };
    this.state = {
      intervalId: null,
      isPolling: false,
      retryCount: 0,
      currentInterval: this.options.interval,
      lastStatus: null,
    };
  }

  public startPolling(): void {
    if (this.state.isPolling) return;
    this.state.isPolling = true;
    this.state.retryCount = 0;
    this.state.currentInterval = this.options.interval;
    this.poll();
    this.scheduleNextPoll();
  }

  public stopPolling(): void {
    if (this.state.intervalId !== null) {
      window.clearTimeout(this.state.intervalId);
      this.state.intervalId = null;
    }
    this.state.isPolling = false;
  }

  public cleanup(): void {
    this.stopPolling();
  }

  public isPolling(): boolean {
    return this.state.isPolling;
  }

  public getCurrentInterval(): number {
    return this.state.currentInterval;
  }

  public updateCallbacks(callbacks: PollingCallbacks): void {
    this.callbacks = { ...this.callbacks, ...callbacks };
  }

  public updateOptions(options: PollingOptions): void {
    this.options = { ...this.options, ...options };
    if (options.interval && this.state.isPolling) {
      this.state.currentInterval = options.interval;
    }
  }

  // ── private ──────────────────────────────────────────────

  private scheduleNextPoll(): void {
    if (!this.state.isPolling) return;
    this.state.intervalId = window.setTimeout(() => {
      this.poll();
      this.scheduleNextPoll();
    }, this.state.currentInterval);
  }

  /**
   * Single GET per cycle — extract status fields and forward the
   * full task object to both callbacks.
   */
  private async poll(): Promise<void> {
    try {
      const url =
        this.taskType === 'backtest'
          ? `/api/trading/tasks/backtest/${this.taskId}/`
          : `/api/trading/tasks/trading/${this.taskId}/`;

      const task = await api.get<Record<string, unknown>>(url);

      // Build status response from the task payload
      if (this.callbacks.onStatusUpdate) {
        const statusResponse: TaskStatusResponse = {
          task_id: (task as { id?: string }).id ?? '',
          task_type: this.taskType,
          status: task.status as TaskStatus,
          progress:
            ('progress' in task
              ? (task as { progress?: number }).progress
              : undefined) || 0,
          current_tick:
            'current_tick' in task
              ? ((
                  task as {
                    current_tick?: {
                      timestamp: string;
                      price: string | null;
                    } | null;
                  }
                ).current_tick ?? null)
              : null,
          started_at: task.started_at as string | null,
          completed_at: task.completed_at as string | null,
          error_message: task.error_message as string | null,
        };
        this.callbacks.onStatusUpdate(statusResponse);
      }

      // Forward the same object as details (no second request)
      if (this.callbacks.onDetailsUpdate) {
        this.callbacks.onDetailsUpdate({
          task: task as unknown as BacktestTask | TradingTask,
          current_execution: null,
        });
      }

      this.state.lastStatus = task.status as TaskStatus;
      this.state.retryCount = 0;
      this.state.currentInterval = this.options.interval;
    } catch (error) {
      this.handleError(error as Error);
    }
  }

  private handleError(error: Error): void {
    this.state.retryCount++;
    if (this.callbacks.onError) {
      this.callbacks.onError(error);
    }
    if (this.state.retryCount >= this.options.maxRetries) {
      console.error(
        `Max retries (${this.options.maxRetries}) exceeded. Stopping polling.`
      );
      this.stopPolling();
      return;
    }
    this.state.currentInterval = Math.min(
      this.state.currentInterval * this.options.backoffMultiplier,
      this.options.maxBackoff
    );
    console.warn(
      `Polling error (retry ${this.state.retryCount}/${this.options.maxRetries}). ` +
        `Next attempt in ${this.state.currentInterval}ms`
    );
  }
}
