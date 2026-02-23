// TickPollingService - lightweight polling for the current-tick endpoint
//
// Designed for high-frequency chart updates. Hits only the
// /current-tick/ endpoint which returns a minimal payload
// instead of the full task object.

import { api } from '../../api/apiClient';
import type { TaskType } from './TaskPollingService';

export interface CurrentTickResponse {
  task_id: string;
  task_type: TaskType;
  status: string;
  current_tick: {
    timestamp: string;
    price: string | null;
  };
  ticks_processed: number;
}

export interface TickPollingCallbacks {
  onTick?: (tick: CurrentTickResponse) => void;
  onError?: (error: Error) => void;
}

export interface TickPollingOptions {
  interval?: number;
  maxRetries?: number;
  backoffMultiplier?: number;
  maxBackoff?: number;
}

interface TickPollingState {
  intervalId: number | null;
  isPolling: boolean;
  retryCount: number;
  currentInterval: number;
}

export class TickPollingService {
  private taskId: string;
  private taskType: TaskType;
  private callbacks: TickPollingCallbacks;
  private options: Required<TickPollingOptions>;
  private state: TickPollingState;

  constructor(
    taskId: string,
    taskType: TaskType,
    callbacks: TickPollingCallbacks = {},
    options: TickPollingOptions = {}
  ) {
    this.taskId = taskId;
    this.taskType = taskType;
    this.callbacks = callbacks;
    this.options = {
      interval: options.interval ?? 2000,
      maxRetries: options.maxRetries ?? 5,
      backoffMultiplier: options.backoffMultiplier ?? 2,
      maxBackoff: options.maxBackoff ?? 30000,
    };
    this.state = {
      intervalId: null,
      isPolling: false,
      retryCount: 0,
      currentInterval: this.options.interval,
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

  public isActive(): boolean {
    return this.state.isPolling;
  }

  public updateCallbacks(callbacks: TickPollingCallbacks): void {
    this.callbacks = { ...this.callbacks, ...callbacks };
  }

  public updateOptions(options: TickPollingOptions): void {
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

  private async poll(): Promise<void> {
    try {
      const url =
        this.taskType === 'backtest'
          ? `/api/trading/tasks/backtest/${this.taskId}/current-tick/`
          : `/api/trading/tasks/trading/${this.taskId}/current-tick/`;

      const data = await api.get<CurrentTickResponse>(url);

      if (this.callbacks.onTick) {
        this.callbacks.onTick(data);
      }

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
        `[TickPolling] Max retries (${this.options.maxRetries}) exceeded. Stopping.`
      );
      this.stopPolling();
      return;
    }
    this.state.currentInterval = Math.min(
      this.state.currentInterval * this.options.backoffMultiplier,
      this.options.maxBackoff
    );
  }
}
