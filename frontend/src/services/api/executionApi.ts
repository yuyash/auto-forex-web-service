/**
 * Execution API service using generated OpenAPI client
 *
 * This module provides a wrapper around the generated ExecutionsService
 * with consistent error handling and type safety.
 */

import { ExecutionsService } from '../../api/generated/services/ExecutionsService';
import { withRetry } from '../../api/client';

/**
 * Execution API wrapper using generated client
 */
export const executionApi = {
  /**
   * Get execution details
   */
  getDetail: (executionId: number) => {
    return withRetry(() => ExecutionsService.getExecutionDetail(executionId));
  },

  /**
   * Get current status of an execution
   */
  getStatus: (executionId: number) => {
    return withRetry(() => ExecutionsService.getExecutionStatus(executionId));
  },

  /**
   * Get execution logs with optional filtering
   */
  getLogs: (
    executionId: number,
    params?: {
      level?: 'debug' | 'info' | 'warning' | 'error';
      startTime?: string;
      endTime?: string;
      limit?: number;
    }
  ) => {
    return withRetry(() =>
      ExecutionsService.getExecutionLogs(
        executionId,
        params?.endTime,
        params?.level,
        params?.limit,
        params?.startTime
      )
    );
  },

  /**
   * Get strategy events for an execution with incremental fetching
   */
  getEvents: (
    executionId: number,
    params?: {
      sinceSequence?: number;
      eventType?: string;
    }
  ) => {
    return withRetry(() =>
      ExecutionsService.getExecutionEvents(
        executionId,
        params?.eventType,
        params?.sinceSequence
      )
    );
  },

  /**
   * Get trades for an execution with incremental fetching
   */
  getTrades: (
    executionId: number,
    params?: {
      sinceSequence?: number;
      instrument?: string;
      direction?: 'buy' | 'sell';
    }
  ) => {
    return withRetry(() =>
      ExecutionsService.getExecutionTrades(
        executionId,
        params?.direction,
        params?.instrument,
        params?.sinceSequence
      )
    );
  },

  /**
   * Get equity curve for an execution with configurable granularity
   */
  getEquity: (
    executionId: number,
    params?: {
      granularity?: number;
      startTime?: string;
      endTime?: string;
    }
  ) => {
    return withRetry(() =>
      ExecutionsService.getExecutionEquity(
        executionId,
        params?.endTime,
        params?.granularity,
        params?.startTime
      )
    );
  },

  /**
   * Get metrics data with optional granularity binning
   */
  getMetrics: (
    executionId: number,
    params?: {
      granularity?: number;
      startTime?: string;
      endTime?: string;
      lastN?: number;
    }
  ) => {
    return withRetry(() =>
      ExecutionsService.getExecutionMetrics(
        executionId,
        params?.endTime,
        params?.granularity,
        params?.lastN,
        params?.startTime
      )
    );
  },

  /**
   * Get latest metrics snapshot for an execution
   */
  getMetricsLatest: (executionId: number) => {
    return withRetry(() =>
      ExecutionsService.getExecutionLatestMetrics(executionId)
    );
  },
};
