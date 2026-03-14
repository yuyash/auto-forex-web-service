/**
 * Fetch paginated metrics for replay overlay charts.
 */

import { getAuthToken } from '../api/client';
import { TaskType } from '../types/common';
import { handleAuthErrorStatus } from './authEvents';

export interface MetricPoint {
  /** Unix timestamp (seconds) */
  t: number;
  /** Strategy-specific metrics JSON */
  metrics: Record<string, number | string | null>;
}

export interface MetricsPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: MetricPoint[];
}

export async function fetchMetrics(opts: {
  taskId: string;
  taskType: TaskType;
  since?: string;
  until?: string;
  executionRunId?: string;
  interval?: number;
  page?: number;
  pageSize?: number;
}): Promise<MetricsPage> {
  const prefix =
    opts.taskType === TaskType.BACKTEST
      ? '/api/trading/tasks/backtest'
      : '/api/trading/tasks/trading';

  const searchParams = new URLSearchParams();
  if (opts.since) searchParams.set('since', opts.since);
  if (opts.until) searchParams.set('until', opts.until);
  if (opts.executionRunId != null)
    searchParams.set('execution_id', String(opts.executionRunId));
  if (opts.interval && opts.interval > 1)
    searchParams.set('interval', String(opts.interval));
  if (opts.page) searchParams.set('page', String(opts.page));
  if (opts.pageSize) searchParams.set('page_size', String(opts.pageSize));

  const qs = searchParams.toString();
  const url = `${prefix}/${opts.taskId}/metrics/${qs ? `?${qs}` : ''}`;

  const response = await fetch(url, {
    method: 'GET',
    credentials: 'include',
    headers: (() => {
      const token = getAuthToken();
      return token
        ? { Authorization: `Bearer ${token}` }
        : ({} as Record<string, string>);
    })(),
  });

  handleAuthErrorStatus(response.status, {
    source: 'http',
    status: response.status,
    context: 'metrics',
  });

  if (!response.ok) {
    throw response;
  }

  const body = (await response
    .json()
    .catch(() => ({}))) as Partial<MetricsPage>;

  // Normalise: the backend may return `metrics` as a JSON string
  // (double-encoded) instead of an object.  Parse it defensively.
  const results = (body.results ?? []).map((r) => ({
    ...r,
    metrics:
      typeof r.metrics === 'string'
        ? (JSON.parse(r.metrics) as Record<string, number | string | null>)
        : r.metrics,
  }));

  return {
    count: body.count ?? 0,
    next: body.next ?? null,
    previous: body.previous ?? null,
    results,
  };
}
