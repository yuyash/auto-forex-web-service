/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DirectionEnum } from './DirectionEnum';
import type { ExecutionMethodEnum } from './ExecutionMethodEnum';
/**
 * Serializer for trade data from Trades model.
 */
export type Trade = {
  direction: DirectionEnum;
  units: number;
  instrument: string;
  price: string;
  execution_method: ExecutionMethodEnum;
  /**
   * Human-readable display name for the execution method.
   */
  readonly execution_method_display?: string;
  layer_index?: number | null;
  retracement_count?: number | null;
  pnl?: string | null;
  timestamp: string;
  open_price?: string | null;
  open_timestamp?: string | null;
  close_price?: string | null;
  close_timestamp?: string | null;
};
