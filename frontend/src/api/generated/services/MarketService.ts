/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class MarketService {
  /**
   * GET /api/market/candles/
   * Fetch historical candle data from OANDA for charting and analysis
   * @param instrument Currency pair (e.g., EUR_USD, GBP_USD)
   * @param accountId OANDA account ID (uses default if not provided)
   * @param after Unix timestamp for fetching newer data
   * @param before Unix timestamp for fetching older data
   * @param count Number of candles to fetch (1-5000)
   * @param fromTime Start time in RFC3339 format
   * @param granularity Candle granularity (S5, M1, H1, D, etc.)
   * @param toTime End time in RFC3339 format
   * @returns any
   * @throws ApiError
   */
  public static getCandleData(
    instrument: string,
    accountId?: string,
    after?: number,
    before?: number,
    count: number = 100,
    fromTime?: string,
    granularity: string = 'H1',
    toTime?: string
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/candles/',
      query: {
        account_id: accountId,
        after: after,
        before: before,
        count: count,
        from_time: fromTime,
        granularity: granularity,
        instrument: instrument,
        to_time: toTime,
      },
    });
  }
  /**
   * GET /api/market/granularities/
   * Retrieve list of supported OANDA granularities/timeframes
   * @returns any
   * @throws ApiError
   */
  public static listSupportedGranularities(): CancelablePromise<
    Record<string, any>
  > {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/candles/granularities/',
    });
  }
  /**
   * GET /api/market/instruments/
   * Retrieve list of supported currency pairs from OANDA API
   * @returns any
   * @throws ApiError
   */
  public static listSupportedInstruments(): CancelablePromise<
    Record<string, any>
  > {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/instruments/',
    });
  }
  /**
   * GET /api/market/instruments/{instrument}/
   * Fetch detailed information about a specific currency pair
   * @param instrument Currency pair (e.g., EUR_USD)
   * @returns any
   * @throws ApiError
   */
  public static getInstrumentDetail(
    instrument: string
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/instruments/{instrument}/',
      path: {
        instrument: instrument,
      },
    });
  }
  /**
   * GET /api/market/status/
   * Retrieve current forex market open/close status and trading session information
   * @returns any
   * @throws ApiError
   */
  public static getMarketStatus(): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/market/status/',
    });
  }
  /**
   * GET /api/market/ticks/
   * Fetch historical tick data from local DB
   * @param instrument Currency pair (e.g., USD_JPY)
   * @param count Number of ticks to return (1-20000, default: 5000)
   * @param fromTime Start time in RFC3339 format
   * @param toTime End time in RFC3339 format
   * @returns any
   * @throws ApiError
   */
  public static getTickData(
    instrument: string,
    count?: number,
    fromTime?: string,
    toTime?: string
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/ticks/',
      query: {
        count: count,
        from_time: fromTime,
        instrument: instrument,
        to_time: toTime,
      },
    });
  }
}
