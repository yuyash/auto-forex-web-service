/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LevelEnum } from './LevelEnum';
/**
 * Serializer for TaskLog model.
 *
 * Provides access to task execution logs with timestamp, level, and message.
 */
export type TaskLog = {
  /**
   * Unique identifier for this log entry
   */
  readonly id: string;
  /**
   * Task this log entry belongs to
   */
  task: number;
  /**
   * When this log entry was created
   */
  readonly timestamp: string;
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
   * Log message content
   */
  message: string;
};
