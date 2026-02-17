/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DirectionEnum } from './DirectionEnum';
/**
 * Serializer for trade data from Trades model.
 */
export type Trade = {
  direction: DirectionEnum;
  units: number;
  instrument: string;
  price: string;
  execution_method: string;
  layer_index?: number | null;
  pnl?: string | null;
  timestamp: string;
};
