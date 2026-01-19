/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class ExecutionsService {
  /**
   * Get execution details
   * Retrieve complete details for a specific execution including status, timing, resource usage, and logs.
   * @param executionId
   * @returns any
   * @throws ApiError
   */
  public static getExecutionDetail(
    executionId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/executions/{execution_id}/',
      path: {
        execution_id: executionId,
      },
    });
  }
  /**
   * Get execution equity curve
   * Retrieve equity curve data with configurable time granularity for binning and statistical aggregation.
   * @param executionId
   * @param endTime Filter data before this timestamp (ISO format)
   * @param granularity Time window in seconds for binning (default: 60)
   * @param startTime Filter data after this timestamp (ISO format)
   * @returns any
   * @throws ApiError
   */
  public static getExecutionEquity(
    executionId: number,
    endTime?: string,
    granularity?: number,
    startTime?: string
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/executions/{execution_id}/equity/',
      path: {
        execution_id: executionId,
      },
      query: {
        end_time: endTime,
        granularity: granularity,
        start_time: startTime,
      },
    });
  }
  /**
   * Get execution strategy events
   * Retrieve strategy events with optional filtering by event type and incremental fetching support.
   * @param executionId
   * @param eventType Filter by event type
   * @param sinceSequence Return only events with sequence number greater than this value (for incremental fetching)
   * @returns any
   * @throws ApiError
   */
  public static getExecutionEvents(
    executionId: number,
    eventType?: string,
    sinceSequence?: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/executions/{execution_id}/events/',
      path: {
        execution_id: executionId,
      },
      query: {
        event_type: eventType,
        since_sequence: sinceSequence,
      },
    });
  }
  /**
   * Get execution logs
   * Retrieve execution logs with optional filtering by level, time range, and limit.
   * @param executionId
   * @param endTime Filter logs before this timestamp (ISO format)
   * @param level Filter by log level (debug, info, warning, error)
   * @param limit Maximum number of logs to return (default: 100, max: 1000)
   * @param startTime Filter logs after this timestamp (ISO format)
   * @returns any
   * @throws ApiError
   */
  public static getExecutionLogs(
    executionId: number,
    endTime?: string,
    level?: 'debug' | 'error' | 'info' | 'warning',
    limit?: number,
    startTime?: string
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/executions/{execution_id}/logs/',
      path: {
        execution_id: executionId,
      },
      query: {
        end_time: endTime,
        level: level,
        limit: limit,
        start_time: startTime,
      },
    });
  }
  /**
   * Get execution metrics
   * Retrieve metrics data with optional granularity binning, time range filtering, or last N points.
   * @param executionId
   * @param endTime Filter metrics before this timestamp (ISO format)
   * @param granularity Time window in seconds for binning (optional, returns binned data if provided)
   * @param lastN Return last N metrics points (alternative to time range)
   * @param startTime Filter metrics after this timestamp (ISO format)
   * @returns any
   * @throws ApiError
   */
  public static getExecutionMetrics(
    executionId: number,
    endTime?: string,
    granularity?: number,
    lastN?: number,
    startTime?: string
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/executions/{execution_id}/metrics/',
      path: {
        execution_id: executionId,
      },
      query: {
        end_time: endTime,
        granularity: granularity,
        last_n: lastN,
        start_time: startTime,
      },
    });
  }
  /**
   * Get latest execution metrics
   * Retrieve the most recent metrics snapshot for an execution.
   * @param executionId
   * @returns any
   * @throws ApiError
   */
  public static getExecutionLatestMetrics(
    executionId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/executions/{execution_id}/metrics/latest/',
      path: {
        execution_id: executionId,
      },
    });
  }
  /**
   * Get execution status
   * Retrieve current execution status including progress, timing, and estimated completion.
   * @param executionId
   * @returns any
   * @throws ApiError
   */
  public static getExecutionStatus(
    executionId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/executions/{execution_id}/status/',
      path: {
        execution_id: executionId,
      },
    });
  }
  /**
   * Get execution trades
   * Retrieve trade logs with optional filtering by instrument, direction, and incremental fetching support.
   * @param executionId
   * @param direction Filter by trade direction (buy/sell)
   * @param instrument Filter by instrument (e.g., EUR_USD)
   * @param sinceSequence Return only trades with sequence number greater than this value (for incremental fetching)
   * @returns any
   * @throws ApiError
   */
  public static getExecutionTrades(
    executionId: number,
    direction?: 'buy' | 'sell',
    instrument?: string,
    sinceSequence?: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/trading/executions/{execution_id}/trades/',
      path: {
        execution_id: executionId,
      },
      query: {
        direction: direction,
        instrument: instrument,
        since_sequence: sinceSequence,
      },
    });
  }
}
