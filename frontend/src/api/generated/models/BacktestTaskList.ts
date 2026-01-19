/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DataSourceEnum } from './DataSourceEnum';
import type { StatusEnum } from './StatusEnum';
import type { TradingModeEnum } from './TradingModeEnum';
/**
 * Serializer for BacktestTask list view (summary only).
 */
export type BacktestTaskList = {
  readonly id: number;
  readonly user_id: number;
  readonly config_id: number;
  readonly config_name: string;
  readonly strategy_type: string;
  /**
   * Human-readable name for this backtest task
   */
  readonly name: string;
  /**
   * Optional description of this backtest task
   */
  readonly description: string;
  /**
   * Data source for historical tick data
   *
   * * `postgresql` - PostgreSQL
   * * `athena` - AWS Athena
   * * `s3` - AWS S3
   */
  readonly data_source: DataSourceEnum;
  /**
   * Start time for backtest period
   */
  readonly start_time: string;
  /**
   * End time for backtest period
   */
  readonly end_time: string;
  /**
   * Initial account balance for backtest
   */
  readonly initial_balance: string;
  /**
   * Get pip_size as Decimal with default value.
   *
   * Returns:
   * Decimal: Pip size for the instrument, defaults to 0.01 if not set
   *
   * Example:
   * >>> task = BacktestTask.objects.get(id=1)
   * >>> pip_size = task.pip_size  # Always returns Decimal
   */
  readonly pip_size: number;
  /**
   * Trading instrument (e.g., EUR_USD, USD_JPY)
   */
  readonly instrument: string;
  /**
   * Trading mode: netting (aggregated positions) or hedging (independent trades)
   *
   * * `netting` - Netting Mode
   * * `hedging` - Hedging Mode
   */
  readonly trading_mode: TradingModeEnum;
  /**
   * Current task status
   *
   * * `created` - Created
   * * `running` - Running
   * * `stopped` - Stopped
   * * `completed` - Completed
   * * `failed` - Failed
   */
  readonly status: StatusEnum;
  /**
   * Timestamp when the task was created
   */
  readonly created_at: string;
  /**
   * Timestamp when the task was last updated
   */
  readonly updated_at: string;
};
