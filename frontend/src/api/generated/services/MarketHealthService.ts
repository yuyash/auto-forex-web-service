/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { OandaApiHealthStatus } from '../models/OandaApiHealthStatus';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class MarketHealthService {
  /**
   * GET /api/market/health/oanda/
   * Retrieve the latest health check status for the selected OANDA account
   * @param accountId OANDA account ID (uses default if not provided)
   * @returns OandaApiHealthStatus Health status retrieved successfully
   * @throws ApiError
   */
  public static getOandaHealthStatus(
    accountId?: string
  ): CancelablePromise<OandaApiHealthStatus> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/health/oanda/',
      query: {
        account_id: accountId,
      },
      errors: {
        400: `No OANDA account found`,
      },
    });
  }
  /**
   * POST /api/market/health/oanda/
   * Perform a live health check against OANDA API and persist the result
   * @param accountId OANDA account ID (uses default if not provided)
   * @returns OandaApiHealthStatus Health check performed successfully
   * @throws ApiError
   */
  public static checkOandaHealth(
    accountId?: string
  ): CancelablePromise<OandaApiHealthStatus> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/market/health/oanda/',
      query: {
        account_id: accountId,
      },
      errors: {
        400: `No OANDA account found`,
      },
    });
  }
}
