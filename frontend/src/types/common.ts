// Common types and enums for task-based strategy configuration

export enum TaskStatus {
  CREATED = 'created',
  STARTING = 'starting',
  RUNNING = 'running',
  PAUSED = 'paused',
  IDLE = 'idle',
  DRAINING = 'draining',
  STOPPING = 'stopping',
  STOPPED = 'stopped',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export enum DataSource {
  POSTGRESQL = 'postgresql',
  ATHENA = 'athena',
  S3 = 's3',
}

export enum TaskType {
  BACKTEST = 'backtest',
  TRADING = 'trading',
}

export interface TaskActionPolicy {
  can_start: boolean;
  can_stop: boolean;
  can_pause: boolean;
  can_resume: boolean;
  can_restart: boolean;
  can_delete: boolean;
  can_edit_metadata: boolean;
  can_edit_execution_settings: boolean;
  restart_required_for_execution_edits: boolean;
}

export const WORKER_OWNED_TASK_STATUSES = new Set<TaskStatus>([
  TaskStatus.STARTING,
  TaskStatus.RUNNING,
  TaskStatus.IDLE,
  TaskStatus.DRAINING,
  TaskStatus.STOPPING,
]);

export function isWorkerOwnedTaskStatus(status?: TaskStatus): boolean {
  return status ? WORKER_OWNED_TASK_STATUSES.has(status) : false;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ApiError {
  error?: string;
  error_code?: string;
  message?: string;
  detail?: string;
  retry_after?: number;
  [key: string]: unknown;
}

export interface ListParams {
  page?: number;
  page_size?: number;
  search?: string;
  ordering?: string;
}
