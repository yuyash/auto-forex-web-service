/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Serializer for strategy configuration list view (summary only).
 */
export type StrategyConfigList = {
  readonly id: number;
  readonly user_id: number;
  /**
   * Human-readable name for this configuration
   */
  readonly name: string;
  /**
   * Type of strategy (e.g., 'floor', 'ma_crossover', 'rsi')
   */
  readonly strategy_type: string;
  /**
   * Optional description of this configuration
   */
  readonly description: string;
  /**
   * Get whether configuration is in use by active tasks.
   */
  readonly is_in_use: boolean;
  /**
   * Timestamp when the configuration was created
   */
  readonly created_at: string;
  /**
   * Timestamp when the configuration was last updated
   */
  readonly updated_at: string;
};
