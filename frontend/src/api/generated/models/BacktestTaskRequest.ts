/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DataSourceEnum } from './DataSourceEnum';
import type { TradingModeEnum } from './TradingModeEnum';
/**
 * Serializer for BacktestTask with execution data.
 */
export type BacktestTaskRequest = {
  /**
   * Human-readable name for this backtest task
   */
  name: string;
  /**
   * Optional description of this backtest task
   */
  description?: string;
  /**
   * Number of times this task has been retried
   */
  retry_count?: number;
  /**
   * Maximum number of retries allowed
   */
  max_retries?: number;
  /**
   * Strategy configuration used by this task
   */
  config: string;
  /**
   * Data source for historical tick data
   *
   * * `postgresql` - PostgreSQL
   * * `athena` - AWS Athena
   * * `s3` - AWS S3
   */
  data_source?: DataSourceEnum;
  /**
   * Start time for backtest period
   */
  start_time: string;
  /**
   * End time for backtest period
   */
  end_time: string;
  /**
   * Initial account balance for backtest
   */
  initial_balance?: string;
  /**
   * Commission to apply per trade
   */
  commission_per_trade?: string;
  /**
   * Trading instrument (e.g., EUR_USD, USD_JPY)
   */
  instrument?: string;
  /**
   * Trading mode: netting (aggregated positions) or hedging (independent trades)
   *
   * * `netting` - Netting Mode
   * * `hedging` - Hedging Mode
   */
  trading_mode?: TradingModeEnum;
};
