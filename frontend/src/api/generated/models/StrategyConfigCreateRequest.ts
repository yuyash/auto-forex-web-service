/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Serializer for creating and updating strategy configurations.
 *
 * Includes validation against strategy registry.
 */
export type StrategyConfigCreateRequest = {
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
};
