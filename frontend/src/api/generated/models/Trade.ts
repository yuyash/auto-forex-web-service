/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { TradeDirectionEnum } from './TradeDirectionEnum';
/**
 * Serializer for trade data from Trades model.
 */
export type Trade = {
  direction: TradeDirectionEnum;
  units: number;
  instrument: string;
  price: string;
  execution_method: string;
  pnl?: string | null;
  timestamp: string;
};
