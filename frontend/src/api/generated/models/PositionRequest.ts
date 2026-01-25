/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Direction530Enum } from './Direction530Enum';
/**
 * Serializer for opening a position via a market order.
 */
export type PositionRequest = {
  instrument: string;
  direction: Direction530Enum;
  units: string;
  take_profit?: string | null;
  stop_loss?: string | null;
};
