/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { Trade } from './Trade';
export type PaginatedTradeList = {
  count: number;
  next?: string | null;
  previous?: string | null;
  results: Array<Trade>;
};
