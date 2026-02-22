/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TradingEvent } from './TradingEvent';
export type PaginatedTradingEventList = {
  count: number;
  next?: string | null;
  previous?: string | null;
  results: Array<TradingEvent>;
};
