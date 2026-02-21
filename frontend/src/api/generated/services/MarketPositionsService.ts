/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PositionRequest } from '../models/PositionRequest';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class MarketPositionsService {
  /**
   * GET /api/market/positions/
   * Retrieve positions directly from OANDA API
   * @param accountId OANDA account database ID
   * @param instrument Currency pair filter
   * @param status Position status (open/closed/all)
   * @returns any
   * @throws ApiError
   */
  public static listPositions(
    accountId?: number,
    instrument?: string,
    status: string = 'open'
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/positions/',
      query: {
        account_id: accountId,
        instrument: instrument,
        status: status,
      },
    });
  }
  /**
   * PUT /api/market/positions/
   * Open a new position by submitting a market order via OANDA
   * @param requestBody
   * @returns any
   * @throws ApiError
   */
  public static openPosition(
    requestBody: PositionRequest
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/market/positions/',
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * GET /api/market/positions/{position_id}/
   * Retrieve detailed information for a specific trade/position from OANDA
   * @param accountId OANDA account database ID
   * @param positionId OANDA Trade ID
   * @returns any
   * @throws ApiError
   */
  public static getPositionDetail(
    accountId: number,
    positionId: string
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/positions/{position_id}/',
      path: {
        position_id: positionId,
      },
      query: {
        account_id: accountId,
      },
    });
  }
  /**
   * PATCH /api/market/positions/{position_id}/
   * Close a position via OANDA API
   * @param positionId OANDA Trade ID
   * @param requestBody
   * @returns any
   * @throws ApiError
   */
  public static closePosition(
    positionId: string,
    requestBody?: Record<string, any>
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'PATCH',
      url: '/api/market/positions/{position_id}/',
      path: {
        position_id: positionId,
      },
      body: requestBody,
      mediaType: 'application/json',
    });
  }
}
