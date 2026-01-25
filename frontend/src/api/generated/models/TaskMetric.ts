/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Serializer for TaskMetric model.
 *
 * Provides access to task execution metrics with name, value, timestamp,
 * and optional metadata.
 */
export type TaskMetric = {
  /**
   * Unique identifier for this metric entry
   */
  readonly id: string;
  /**
   * Task this metric belongs to
   */
  task: number;
  /**
   * Name of the metric (e.g., 'equity', 'drawdown', 'trades_count')
   */
  metric_name: string;
  /**
   * Numeric value of the metric
   */
  metric_value: number;
  /**
   * When this metric was recorded
   */
  readonly timestamp: string;
  /**
   * Optional additional metadata for this metric
   */
  metadata?: any;
};
