/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { OrderRequest } from '../models/OrderRequest';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class MarketOrdersService {
  /**
   * GET /api/market/orders/
   * List user's orders directly from OANDA API
   * @param accountId Filter by OANDA account ID
   * @param instrument Filter by currency pair
   * @param page Page number
   * @param pageSize Number of results per page (default: 50, max: 200)
   * @param status Filter by order status (pending/all)
   * @returns any
   * @throws ApiError
   */
  public static listOrders(
    accountId?: number,
    instrument?: string,
    page?: number,
    pageSize?: number,
    status: string = 'all'
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/orders/',
      query: {
        account_id: accountId,
        instrument: instrument,
        page: page,
        page_size: pageSize,
        status: status,
      },
    });
  }
  /**
   * POST /api/market/orders/
   * Submit new order (market, limit, stop, OCO)
   * @param requestBody
   * @returns any
   * @throws ApiError
   */
  public static createOrder(
    requestBody: OrderRequest
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/market/orders/',
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * GET /api/market/orders/{order_id}/
   * Retrieve order details from OANDA API
   * @param accountId OANDA account database ID
   * @param orderId OANDA Order ID
   * @returns any
   * @throws ApiError
   */
  public static getOrderDetail(
    accountId: number,
    orderId: string
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/market/orders/{order_id}/',
      path: {
        order_id: orderId,
      },
      query: {
        account_id: accountId,
      },
    });
  }
  /**
   * DELETE /api/market/orders/{order_id}/
   * Cancel a pending order via OANDA API
   * @param accountId OANDA account database ID
   * @param orderId OANDA Order ID
   * @returns any
   * @throws ApiError
   */
  public static cancelOrder(
    accountId: number,
    orderId: string
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'DELETE',
      url: '/api/market/orders/{order_id}/',
      path: {
        order_id: orderId,
      },
      query: {
        account_id: accountId,
      },
    });
  }
}
