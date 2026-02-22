/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LevelEnum } from './LevelEnum';
import type { TaskTypeEnum } from './TaskTypeEnum';
/**
 * Serializer for TaskLog model.
 *
 * Provides access to task execution logs with timestamp, level, and message.
 */
export type TaskLog = {
  /**
   * Unique identifier for this log entry
   */
  readonly id?: string;
  /**
   * Type of task (backtest or trading)
   *
   * * `backtest` - Backtest
   * * `trading` - Trading
   */
  task_type: TaskTypeEnum;
  /**
   * UUID of the task this log entry belongs to
   */
  task_id: string;
  /**
   * Celery task ID for this execution
   */
  celery_task_id?: string | null;
  /**
   * When this log entry was created
   */
  readonly timestamp?: string;
  /**
   * Log severity level
   *
   * * `DEBUG` - Debug
   * * `INFO` - Info
   * * `WARNING` - Warning
   * * `ERROR` - Error
   * * `CRITICAL` - Critical
   */
  level?: LevelEnum;
  /**
   * Component/logger name that emitted this log
   */
  component?: string;
  /**
   * Log message content
   */
  message: string;
  /**
   * Additional structured log details
   */
  details?: any;
};
