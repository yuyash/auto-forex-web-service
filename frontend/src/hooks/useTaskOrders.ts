/**
 * useTaskOrders Hook
 *
 * Fetches orders from task-based API endpoints with DRF pagination.
 */

import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { OpenAPI } from '../api/generated/core/OpenAPI';
import { TaskType } from '../types/common';
import { handleAuthErrorStatus } from '../utils/authEvents';

export interface TaskOrder {
  id: string;
  celery_task_id?: string | null;
  broker_order_id?: string | null;
  oanda_trade_id?: string | null;
  instrument: string;
  order_type: string;
  direction?: string | null;
  units: number;
  requested_price?: string | null;
  fill_price?: string | null;
  status: string;
  submitted_at: string;
  filled_at?: string | null;
  cancelled_at?: string | null;
  stop_loss?: string | null;
  error_message?: string | null;
  is_dry_run: boolean;
}

interface UseTaskOrdersOptions {
  taskId: string | number;
  taskType: TaskType;
  status?: string;
  orderType?: string;
  direction?: string;
  page?: number;
  pageSize?: number;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskOrdersResult {
  orders: TaskOrder[];
  totalCount: number;
  hasNext: boolean;
  hasPrevious: boolean;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export const useTaskOrders = ({
  taskId,
  taskType,
  status,
  orderType,
  direction,
  page = 1,
  pageSize = 100,
  enableRealTimeUpdates = false,
  refreshInterval = 5000,
}: UseTaskOrdersOptions): UseTaskOrdersResult => {
  const [orders, setOrders] = useState<TaskOrder[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchOrders = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const prefix =
        taskType === TaskType.BACKTEST
          ? '/api/trading/tasks/backtest'
          : '/api/trading/tasks/trading';

      const params: Record<string, string> = {
        page: String(page),
        page_size: String(pageSize),
      };
      if (status) params.status = status;
      if (orderType) params.order_type = orderType;
      if (direction) params.direction = direction;

      const url = `${OpenAPI.BASE}${prefix}/${taskId}/orders/`;

      const headers: Record<string, string> = {
        Accept: 'application/json',
      };
      if (OpenAPI.TOKEN) {
        const token =
          typeof OpenAPI.TOKEN === 'function'
            ? await (OpenAPI.TOKEN as (options: unknown) => Promise<string>)({})
            : OpenAPI.TOKEN;
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
      }

      const response = await axios.get(url, {
        params,
        headers,
        withCredentials: OpenAPI.WITH_CREDENTIALS,
      });

      const data = response.data;
      setOrders((data.results || []) as TaskOrder[]);
      setTotalCount(data.count ?? 0);
      setHasNext(Boolean(data.next));
      setHasPrevious(Boolean(data.previous));
    } catch (err) {
      if (axios.isAxiosError(err) && err.response) {
        handleAuthErrorStatus(err.response.status, {
          source: 'http',
          status: err.response.status,
          context: 'task_orders',
        });
      }
      const msg = err instanceof Error ? err.message : 'Failed to load orders';
      setError(new Error(msg));
    } finally {
      setIsLoading(false);
    }
  }, [taskId, taskType, status, orderType, direction, page, pageSize]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const interval = setInterval(fetchOrders, refreshInterval);
    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refreshInterval, fetchOrders]);

  return {
    orders,
    totalCount,
    hasNext,
    hasPrevious,
    isLoading,
    error,
    refetch: fetchOrders,
  };
};
