/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TradeDirectionEnum } from './TradeDirectionEnum';
/**
 * Serializer for trade data from execution state.
 */
export type Trade = {
  sequence: number;
  timestamp: string;
  instrument: string;
  direction: TradeDirectionEnum;
  units: string;
  price: string;
  pnl?: string | null;
  commission?: string | null;
  details?: any;
};
