/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Direction530Enum } from './Direction530Enum';
import type { OrderTypeEnum } from './OrderTypeEnum';
/**
 * Serializer for creating orders.
 */
export type OrderRequest = {
  /**
   * Currency pair (e.g., 'EUR_USD')
   */
  instrument: string;
  /**
   * Type of order
   *
   * * `market` - market
   * * `limit` - limit
   * * `stop` - stop
   * * `oco` - oco
   */
  order_type: OrderTypeEnum;
  /**
   * Trade direction
   *
   * * `long` - long
   * * `short` - short
   */
  direction: Direction530Enum;
  /**
   * Number of units to trade
   */
  units: string;
  /**
   * Order price (required for limit/stop orders)
   */
  price?: string | null;
  /**
   * Take-profit price
   */
  take_profit?: string | null;
  /**
   * Stop-loss price
   */
  stop_loss?: string | null;
  /**
   * Limit price (for OCO orders)
   */
  limit_price?: string | null;
  /**
   * Stop price (for OCO orders)
   */
  stop_price?: string | null;
};
