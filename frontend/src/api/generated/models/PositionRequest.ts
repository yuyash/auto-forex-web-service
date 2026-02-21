/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DirectionEnum } from './DirectionEnum';
/**
 * Serializer for opening a position via a market order.
 */
export type PositionRequest = {
  instrument: string;
  direction: DirectionEnum;
  units: string;
  take_profit?: string | null;
  stop_loss?: string | null;
};
