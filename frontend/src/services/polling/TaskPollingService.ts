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
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  pending_new_execution?: boolean;
}

export interface TaskDetailsResponse {
  task: BacktestTask | TradingTask;
  current_execution: ExecutionSummary | null;
}

export interface TaskLogsResponse {
  logs: Array<{
    id?: string;
    timestamp: string;
    level: string;
    message: string;
  }>;
}

export interface PollingCallbacks {
  onStatusUpdate?: (status: TaskStatusResponse) => void;
  onDetailsUpdate?: (details: TaskDetailsResponse) => void;
  onLogsUpdate?: (logs: TaskLogsResponse) => void;
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
  lastLogTimestamp: string | null;
  cachedLogs: TaskLogsResponse['logs'];
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
      lastLogTimestamp: null,
      cachedLogs: [],
    };
  }

  public startPolling(): void {
    if (this.state.isPolling) return;
    this.state.isPolling = true;
    this.state.retryCount = 0;
    this.state.currentInterval = this.options.interval;
    void this.pollAndSchedule(false);
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
      if (this.state.intervalId !== null) {
        window.clearTimeout(this.state.intervalId);
        this.scheduleNextPoll();
      }
    }
  }

  // ── private ──────────────────────────────────────────────

  private scheduleNextPoll(): void {
    if (!this.state.isPolling) return;
    this.state.intervalId = window.setTimeout(() => {
      this.state.intervalId = null;
      void this.pollAndSchedule(true);
    }, this.state.currentInterval);
  }

  private async pollAndSchedule(fromTimer: boolean): Promise<void> {
    if (!this.state.isPolling) {
      return;
    }

    if (!fromTimer && this.state.intervalId !== null) {
      window.clearTimeout(this.state.intervalId);
      this.state.intervalId = null;
    }

    await this.poll();

    if (this.state.isPolling) {
      this.scheduleNextPoll();
    }
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

      if (this.callbacks.onLogsUpdate) {
        const logsUrl =
          this.taskType === 'backtest'
            ? `/api/trading/tasks/backtest/${this.taskId}/logs/`
            : `/api/trading/tasks/trading/${this.taskId}/logs/`;

        const logsResponse = await api.get<{
          results?: TaskLogsResponse['logs'];
        }>(logsUrl, {
          page: 1,
          page_size: 100,
          since: this.state.lastLogTimestamp ?? undefined,
        });

        const incomingLogs = logsResponse.results ?? [];
        if (incomingLogs.length > 0) {
          const mergedLogs = new Map<
            string,
            TaskLogsResponse['logs'][number]
          >();
          for (const log of this.state.cachedLogs) {
            mergedLogs.set(
              log.id ?? `${log.timestamp}:${log.level}:${log.message}`,
              log
            );
          }
          for (const log of incomingLogs) {
            mergedLogs.set(
              log.id ?? `${log.timestamp}:${log.level}:${log.message}`,
              log
            );
          }
          this.state.cachedLogs = Array.from(mergedLogs.values())
            .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
            .slice(0, 200);

          const latestLogTimestamp = incomingLogs
            .map((log) => log.timestamp)
            .sort()
            .at(-1);
          if (latestLogTimestamp) {
            this.state.lastLogTimestamp = latestLogTimestamp;
          }
        }

        this.callbacks.onLogsUpdate({
          logs: this.state.cachedLogs,
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
