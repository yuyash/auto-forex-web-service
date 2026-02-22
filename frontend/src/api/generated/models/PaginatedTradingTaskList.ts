/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TradingTask } from './TradingTask';
export type PaginatedTradingTaskList = {
  count: number;
  next?: string | null;
  previous?: string | null;
  results: Array<TradingTask>;
};
