/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { OandaAccounts } from '../models/OandaAccounts';
import type { OandaAccountsRequest } from '../models/OandaAccountsRequest';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class MarketAccountsService {
  /**
   * GET /api/market/accounts/
   * Retrieve all OANDA accounts for the authenticated user
   * @returns OandaAccounts List of OANDA accounts
   * @throws ApiError
   */
  public static listOandaAccounts(): CancelablePromise<Array<OandaAccounts>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/accounts/',
      errors: {
        401: `Authentication required`,
      },
    });
  }
  /**
   * POST /api/market/accounts/
   * Add a new OANDA account for the authenticated user
   * @param requestBody
   * @returns OandaAccounts Account created successfully
   * @throws ApiError
   */
  public static createOandaAccount(
    requestBody: OandaAccountsRequest
  ): CancelablePromise<OandaAccounts> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/market/accounts/',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        400: `Invalid data`,
        401: `Authentication required`,
      },
    });
  }
  /**
   * GET /api/market/accounts/{account_id}/
   * Retrieve detailed information about a specific OANDA account including live data from OANDA API
   * @param accountId OANDA account database ID
   * @returns OandaAccounts Account details retrieved successfully
   * @throws ApiError
   */
  public static getOandaAccountDetail(
    accountId: number
  ): CancelablePromise<OandaAccounts> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/accounts/{account_id}/',
      path: {
        account_id: accountId,
      },
      errors: {
        401: `Authentication required`,
        404: `Account not found`,
      },
    });
  }
  /**
   * PUT /api/market/accounts/{account_id}/
   * Update a specific OANDA account
   * @param accountId OANDA account database ID
   * @param requestBody
   * @returns OandaAccounts Account updated successfully
   * @throws ApiError
   */
  public static updateOandaAccount(
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
      errors: {
        400: `Invalid data`,
        401: `Authentication required`,
        404: `Account not found`,
      },
    });
  }
  /**
   * DELETE /api/market/accounts/{account_id}/
   * Delete a specific OANDA account
   * @param accountId OANDA account database ID
   * @returns any Account deleted successfully
   * @throws ApiError
   */
  public static deleteOandaAccount(accountId: number): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'DELETE',
      url: '/api/market/accounts/{account_id}/',
      path: {
        account_id: accountId,
      },
      errors: {
        400: `Account is in use`,
        401: `Authentication required`,
        404: `Account not found`,
      },
    });
  }
}
