/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Serializer for strategy configuration full details.
 */
export type StrategyConfigDetail = {
  /**
   * Unique identifier for this record
   */
  readonly id?: string;
  readonly user_id?: number;
  /**
   * Human-readable name for this configuration
   */
  name: string;
  /**
   * Type of strategy (e.g., 'floor', 'ma_crossover', 'rsi')
   */
  strategy_type: string;
  /**
   * Strategy-specific configuration parameters
   */
  parameters?: any;
  /**
   * Optional description of this configuration
   */
  description?: string;
  /**
   * Get whether configuration is in use by active tasks.
   */
  readonly is_in_use?: boolean;
  /**
   * Timestamp when this record was created
   */
  readonly created_at?: string;
  /**
   * Timestamp when this record was last updated
   */
  readonly updated_at?: string;
};
