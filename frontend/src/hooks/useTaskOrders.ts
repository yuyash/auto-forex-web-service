/**
 * useTaskOrders Hook
 *
 * Fetches orders from task-based API endpoints with DRF pagination.
 * Supports incremental fetching via the `since` parameter — during polling
 * cycles only new/updated records are fetched and merged into the local cache.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
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
  updated_at?: string | null;
}

interface UseTaskOrdersOptions {
  taskId: string | number;
  taskType: TaskType;
  /** Filter orders by a specific Celery execution ID. */
  celeryTaskId?: string;
  status?: string;
  orderType?: string;
  direction?: string;
  page?: number;
  pageSize?: number;
  /** ISO 8601 timestamp — only return records updated after this time. */
  since?: string;
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

async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (OpenAPI.TOKEN) {
    const token =
      typeof OpenAPI.TOKEN === 'function'
        ? await (OpenAPI.TOKEN as (options: unknown) => Promise<string>)({})
        : OpenAPI.TOKEN;
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }
  return headers;
}

function getLatestUpdatedAt(orders: TaskOrder[]): string | null {
  let latest: string | null = null;
  for (const o of orders) {
    if (o.updated_at && (!latest || o.updated_at > latest)) {
      latest = o.updated_at;
    }
  }
  return latest;
}

export const useTaskOrders = ({
  taskId,
  taskType,
  celeryTaskId,
  status,
  orderType,
  direction,
  page = 1,
  pageSize = 100,
  since,
  enableRealTimeUpdates = false,
  refreshInterval = 5000,
}: UseTaskOrdersOptions): UseTaskOrdersResult => {
  const [orders, setOrders] = useState<TaskOrder[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const latestRequestRef = useRef(0);
  const sinceRef = useRef<string | null>(null);
  const hasInitialFetchRef = useRef(false);

  const paramsKey = `${taskId}-${taskType}-${celeryTaskId}-${status}-${orderType}-${direction}-${page}-${pageSize}-${since ?? ''}`;
  const prevParamsKeyRef = useRef(paramsKey);
  if (paramsKey !== prevParamsKeyRef.current) {
    prevParamsKeyRef.current = paramsKey;
    sinceRef.current = null;
    hasInitialFetchRef.current = false;
  }

  const fetchOrders = useCallback(
    async (incremental = false) => {
      if (!taskId) {
        setIsLoading(false);
        return;
      }

      const requestId = ++latestRequestRef.current;

      try {
        if (!incremental) setIsLoading(true);
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
        if (celeryTaskId) params.celery_task_id = celeryTaskId;
        const effectiveSince = since ?? (incremental ? sinceRef.current : null);
        if (effectiveSince) params.since = effectiveSince;

        const url = `${OpenAPI.BASE}${prefix}/${taskId}/orders/`;
        const headers = await getAuthHeaders();

        const response = await axios.get(url, {
          params,
          headers,
          withCredentials: OpenAPI.WITH_CREDENTIALS,
        });

        if (requestId !== latestRequestRef.current) return;

        const data = response.data;
        const incoming = (data.results || []) as TaskOrder[];

        if (incremental && incoming.length > 0) {
          setOrders((prev) => {
            const map = new Map(prev.map((o) => [o.id, o]));
            for (const o of incoming) {
              map.set(o.id, o);
            }
            return Array.from(map.values());
          });
          setTotalCount(data.count ?? totalCount);
        } else if (!incremental) {
          setOrders(incoming);
          setTotalCount(data.count ?? 0);
          setHasNext(Boolean(data.next));
          setHasPrevious(Boolean(data.previous));
        }

        const latestTs = getLatestUpdatedAt(incoming);
        if (latestTs && (!sinceRef.current || latestTs > sinceRef.current)) {
          sinceRef.current = latestTs;
        }
        hasInitialFetchRef.current = true;
      } catch (err) {
        if (requestId !== latestRequestRef.current) return;

        if (axios.isAxiosError(err) && err.response) {
          handleAuthErrorStatus(err.response.status, {
            source: 'http',
            status: err.response.status,
            context: 'task_orders',
          });
        }
        const msg =
          err instanceof Error ? err.message : 'Failed to load orders';
        setError(new Error(msg));
      } finally {
        if (requestId === latestRequestRef.current) {
          setIsLoading(false);
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      taskId,
      taskType,
      celeryTaskId,
      status,
      orderType,
      direction,
      page,
      pageSize,
      since,
    ]
  );

  useEffect(() => {
    fetchOrders(false);
  }, [fetchOrders]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const interval = setInterval(() => {
      if (hasInitialFetchRef.current) {
        fetchOrders(true);
      }
    }, refreshInterval);
    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refreshInterval, fetchOrders]);

  const prevRealTimeRef = useRef(enableRealTimeUpdates);
  useEffect(() => {
    if (prevRealTimeRef.current && !enableRealTimeUpdates) {
      sinceRef.current = null;
      hasInitialFetchRef.current = false;
      fetchOrders(false);
    }
    prevRealTimeRef.current = enableRealTimeUpdates;
  }, [enableRealTimeUpdates, fetchOrders]);

  return {
    orders,
    totalCount,
    hasNext,
    hasPrevious,
    isLoading,
    error,
    refetch: () => fetchOrders(false),
  };
};
