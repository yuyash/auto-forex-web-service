/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class HealthService {
  /**
   * GET /api/health/
   * Check the health status of the backend API service. Returns overall system status.
   * @returns any Service is healthy
   * @throws ApiError
   */
  public static healthCheck(): CancelablePromise<{
    /**
     * Overall health status
     */
    status: 'healthy';
    /**
     * Timestamp of the health check
     */
    timestamp: string;
    /**
     * Response time in milliseconds
     */
    response_time_ms: number;
  }> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/health/',
      errors: {
        503: `Service is unhealthy`,
      },
    });
  }
}
