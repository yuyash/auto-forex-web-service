/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { OandaAccounts } from '../models/OandaAccounts';
import type { OandaAccountsRequest } from '../models/OandaAccountsRequest';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class MarketService {
  /**
   * /api/market/accounts/
   * API endpoint for OANDA accounts.
   *
   * GET /api/accounts
   * - List all OANDA accounts for the authenticated user
   *
   * POST /api/accounts
   * - Add a new OANDA account
   * @returns OandaAccounts
   * @throws ApiError
   */
  public static marketAccountsRetrieve(): CancelablePromise<OandaAccounts> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/accounts/',
    });
  }
  /**
   * /api/market/accounts/
   * API endpoint for OANDA accounts.
   *
   * GET /api/accounts
   * - List all OANDA accounts for the authenticated user
   *
   * POST /api/accounts
   * - Add a new OANDA account
   * @param requestBody
   * @returns OandaAccounts
   * @throws ApiError
   */
  public static marketAccountsCreate(
    requestBody: OandaAccountsRequest
  ): CancelablePromise<OandaAccounts> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/market/accounts/',
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * /api/market/accounts/{account_id}/
   * API endpoint for retrieving, updating, and deleting a specific OANDA account.
   *
   * GET /api/accounts/{id}
   * - Retrieve details of a specific OANDA account
   *
   * PUT /api/accounts/{id}
   * - Update a specific OANDA account
   *
   * DELETE /api/accounts/{id}
   * - Delete a specific OANDA account
   * @param accountId
   * @returns OandaAccounts
   * @throws ApiError
   */
  public static marketAccountsRetrieve2(
    accountId: number
  ): CancelablePromise<OandaAccounts> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/accounts/{account_id}/',
      path: {
        account_id: accountId,
      },
    });
  }
  /**
   * /api/market/accounts/{account_id}/
   * API endpoint for retrieving, updating, and deleting a specific OANDA account.
   *
   * GET /api/accounts/{id}
   * - Retrieve details of a specific OANDA account
   *
   * PUT /api/accounts/{id}
   * - Update a specific OANDA account
   *
   * DELETE /api/accounts/{id}
   * - Delete a specific OANDA account
   * @param accountId
   * @param requestBody
   * @returns OandaAccounts
   * @throws ApiError
   */
  public static marketAccountsUpdate(
    accountId: number,
    requestBody: OandaAccountsRequest
  ): CancelablePromise<OandaAccounts> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/market/accounts/{account_id}/',
      path: {
        account_id: accountId,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * /api/market/accounts/{account_id}/
   * API endpoint for retrieving, updating, and deleting a specific OANDA account.
   *
   * GET /api/accounts/{id}
   * - Retrieve details of a specific OANDA account
   *
   * PUT /api/accounts/{id}
   * - Update a specific OANDA account
   *
   * DELETE /api/accounts/{id}
   * - Delete a specific OANDA account
   * @param accountId
   * @returns void
   * @throws ApiError
   */
  public static marketAccountsDestroy(
    accountId: number
  ): CancelablePromise<void> {
    return __request(OpenAPI, {
      method: 'DELETE',
      url: '/api/market/accounts/{account_id}/',
      path: {
        account_id: accountId,
      },
    });
  }
  /**
   * /api/market/candles/
   * Fetch historical candle data from OANDA.
   *
   * Args:
   * request: HTTP request with query parameters
   *
   * Returns:
   * Response with candle data or error message
   * @returns any No response body
   * @throws ApiError
   */
  public static marketCandlesRetrieve(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/candles/',
    });
  }
  /**
   * /api/market/candles/granularities/
   * Retrieve list of supported granularities.
   *
   * Granularities are standardized by OANDA and rarely change.
   *
   * Returns:
   * Response with list of granularity objects
   * @returns any No response body
   * @throws ApiError
   */
  public static marketCandlesGranularitiesRetrieve(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/candles/granularities/',
    });
  }
  /**
   * /api/market/health/oanda/
   * API endpoint for OANDA API health checks.
   *
   * GET /api/market/health/oanda/
   * - Returns latest persisted status for the selected account (or null if none yet)
   *
   * POST /api/market/health/oanda/
   * - Performs a live check against OANDA and persists/returns the result
   * @returns any No response body
   * @throws ApiError
   */
  public static marketHealthOandaRetrieve(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/health/oanda/',
    });
  }
  /**
   * /api/market/health/oanda/
   * API endpoint for OANDA API health checks.
   *
   * GET /api/market/health/oanda/
   * - Returns latest persisted status for the selected account (or null if none yet)
   *
   * POST /api/market/health/oanda/
   * - Performs a live check against OANDA and persists/returns the result
   * @returns any No response body
   * @throws ApiError
   */
  public static marketHealthOandaCreate(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/market/health/oanda/',
    });
  }
  /**
   * /api/market/instruments/
   * Retrieve list of supported instruments from OANDA API.
   *
   * Returns:
   * Response with list of instrument codes
   * @returns any No response body
   * @throws ApiError
   */
  public static marketInstrumentsRetrieve(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/instruments/',
    });
  }
  /**
   * /api/market/instruments/{instrument}/
   * Get detailed information about a specific instrument.
   *
   * Args:
   * request: HTTP request
   * instrument: Currency pair (e.g., EUR_USD)
   *
   * Returns:
   * Response with instrument details
   * @param instrument
   * @returns any No response body
   * @throws ApiError
   */
  public static marketInstrumentsRetrieve2(
    instrument: string
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/instruments/{instrument}/',
      path: {
        instrument: instrument,
      },
    });
  }
  /**
   * /api/market/market/status/
   * Get current forex market status.
   *
   * Returns:
   * Response with market status and active sessions
   * @returns any No response body
   * @throws ApiError
   */
  public static marketMarketStatusRetrieve(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/market/status/',
    });
  }
  /**
   * /api/market/orders/
   * List user's orders directly from OANDA API.
   *
   * Args:
   * request: HTTP request with query parameters
   *
   * Returns:
   * Response with order list from OANDA
   * @returns any No response body
   * @throws ApiError
   */
  public static marketOrdersRetrieve(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/orders/',
    });
  }
  /**
   * /api/market/orders/
   * Submit a new order.
   *
   * Args:
   * request: HTTP request with order data
   *
   * Returns:
   * Response with created order details or error
   * @returns any No response body
   * @throws ApiError
   */
  public static marketOrdersCreate(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/market/orders/',
    });
  }
  /**
   * /api/market/orders/{order_id}/
   * Retrieve order details from OANDA API.
   *
   * Args:
   * request: HTTP request
   * order_id: OANDA Order ID
   *
   * Returns:
   * Response with order details or error
   * @param orderId
   * @returns any No response body
   * @throws ApiError
   */
  public static marketOrdersRetrieve2(orderId: string): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/orders/{order_id}/',
      path: {
        order_id: orderId,
      },
    });
  }
  /**
   * /api/market/orders/{order_id}/
   * Cancel a pending order via OANDA API.
   *
   * Args:
   * request: HTTP request
   * order_id: OANDA Order ID
   *
   * Returns:
   * Response with success message or error
   * @param orderId
   * @returns void
   * @throws ApiError
   */
  public static marketOrdersDestroy(orderId: string): CancelablePromise<void> {
    return __request(OpenAPI, {
      method: 'DELETE',
      url: '/api/market/orders/{order_id}/',
      path: {
        order_id: orderId,
      },
    });
  }
  /**
   * /api/market/positions/
   * Retrieve positions directly from OANDA API.
   *
   * Args:
   * request: HTTP request with query parameters
   *
   * Returns:
   * Response with position data
   * @returns any No response body
   * @throws ApiError
   */
  public static marketPositionsRetrieve(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/positions/',
    });
  }
  /**
   * /api/market/positions/
   * Open a new position via OANDA by submitting a market order.
   *
   * Body:
   * - account_id: OANDA account database ID (required)
   * - instrument: Currency pair (e.g., 'EUR_USD') (required)
   * - direction: 'long' or 'short' (required)
   * - units: number of units (required)
   * - take_profit: optional TP price
   * - stop_loss: optional SL price
   *
   * Returns:
   * Response with created order details
   * @returns any No response body
   * @throws ApiError
   */
  public static marketPositionsUpdate(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/market/positions/',
    });
  }
  /**
   * /api/market/positions/{position_id}/
   * Retrieve position details from OANDA API.
   *
   * Args:
   * request: HTTP request
   * position_id: OANDA Trade ID
   *
   * Returns:
   * Response with position data from OANDA
   * @param positionId
   * @returns any No response body
   * @throws ApiError
   */
  public static marketPositionsRetrieve2(
    positionId: string
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/positions/{position_id}/',
      path: {
        position_id: positionId,
      },
    });
  }
  /**
   * /api/market/positions/{position_id}/
   * Close a position via OANDA API.
   *
   * PATCH /api/positions/{trade_id}
   *
   * Body (optional):
   * - account_id: OANDA account database ID (required)
   * - units: Number of units to close (optional, closes all if not provided)
   * @param positionId
   * @returns any No response body
   * @throws ApiError
   */
  public static marketPositionsPartialUpdate(
    positionId: string
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'PATCH',
      url: '/api/market/positions/{position_id}/',
      path: {
        position_id: positionId,
      },
    });
  }
}
