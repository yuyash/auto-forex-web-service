/**
 * Fetch paginated metrics for replay overlay charts.
 */

import { api } from '../api/apiClient';
import { TaskType } from '../types/common';

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
  data_source: string;
  resume_cursor_timestamp: string | null;
  consistency_warnings: Array<Record<string, unknown>>;
  results: MetricPoint[];
}

export interface LatestMetricsResponse {
  data_source: string;
  resume_cursor_timestamp: string | null;
  consistency_warnings: Array<Record<string, unknown>>;
  result: MetricPoint | null;
}

function buildTaskPrefix(taskType: TaskType): string {
  return taskType === TaskType.BACKTEST
    ? '/api/trading/tasks/backtest'
    : '/api/trading/tasks/trading';
}

function normalizeMetricPoint(point: Partial<MetricPoint>): MetricPoint {
  let metrics: Record<string, number | string | null> = {};
  if (typeof point.metrics === 'string') {
    try {
      const parsed = JSON.parse(point.metrics);
      metrics =
        parsed && typeof parsed === 'object'
          ? (parsed as Record<string, number | string | null>)
          : {};
    } catch {
      metrics = {};
    }
  } else if (point.metrics && typeof point.metrics === 'object') {
    metrics = point.metrics;
  }

  return {
    t: Number(point.t ?? 0),
    metrics,
  };
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
  const prefix = buildTaskPrefix(opts.taskType);

  const searchParams = new URLSearchParams();
  if (opts.since) searchParams.set('since', opts.since);
  if (opts.until) searchParams.set('until', opts.until);
  if (opts.executionRunId != null)
    searchParams.set('execution_id', String(opts.executionRunId));
  if (opts.interval && opts.interval > 1)
    searchParams.set('interval', String(opts.interval));
  if (opts.page) searchParams.set('page', String(opts.page));
  if (opts.pageSize) searchParams.set('page_size', String(opts.pageSize));

  const body = await api.get<Partial<MetricsPage>>(
    `${prefix}/${opts.taskId}/metrics/`,
    Object.fromEntries(searchParams.entries())
  );

  const results = (body.results ?? []).map((point) =>
    normalizeMetricPoint(point)
  );

  return {
    count: body.count ?? 0,
    next: body.next ?? null,
    previous: body.previous ?? null,
    data_source:
      typeof body.data_source === 'string' ? body.data_source : 'unknown',
    resume_cursor_timestamp:
      typeof body.resume_cursor_timestamp === 'string'
        ? body.resume_cursor_timestamp
        : null,
    consistency_warnings: Array.isArray(body.consistency_warnings)
      ? (body.consistency_warnings as Array<Record<string, unknown>>)
      : [],
    results,
  };
}

export async function fetchLatestMetrics(opts: {
  taskId: string;
  taskType: TaskType;
  executionRunId?: string;
}): Promise<LatestMetricsResponse> {
  const query =
    opts.executionRunId != null
      ? { execution_id: String(opts.executionRunId) }
      : undefined;
  const body = await api.get<Partial<LatestMetricsResponse>>(
    `${buildTaskPrefix(opts.taskType)}/${opts.taskId}/latest-metrics/`,
    query
  );

  return {
    data_source:
      typeof body.data_source === 'string' ? body.data_source : 'unknown',
    resume_cursor_timestamp:
      typeof body.resume_cursor_timestamp === 'string'
        ? body.resume_cursor_timestamp
        : null,
    consistency_warnings: Array.isArray(body.consistency_warnings)
      ? (body.consistency_warnings as Array<Record<string, unknown>>)
      : [],
    result: body.result ? normalizeMetricPoint(body.result) : null,
  };
}

export async function fetchPaginatedMetrics(opts: {
  taskId: string;
  taskType: TaskType;
  since?: string;
  until?: string;
  executionRunId?: string;
  interval?: number;
  pageSize?: number;
  /** Maximum number of pages to fetch (default: unlimited). */
  maxPages?: number;
  /** Existing points to merge with fetched pages. */
  existingResults?: MetricPoint[];
}): Promise<MetricsPage> {
  const pageSize = opts.pageSize ?? 250;
  const maxPages = opts.maxPages ?? Infinity;
  const results: MetricPoint[] = opts.existingResults
    ? [...opts.existingResults]
    : [];
  let page = 1;
  let dataSource = 'unknown';
  let resumeCursorTimestamp: string | null = null;
  let consistencyWarnings: Array<Record<string, unknown>> = [];

  while (page <= maxPages) {
    const response = await fetchMetrics({
      ...opts,
      page,
      pageSize,
    });
    dataSource = response.data_source;
    resumeCursorTimestamp = response.resume_cursor_timestamp;
    consistencyWarnings = response.consistency_warnings;
    results.push(...response.results);
    if (!response.next) {
      return {
        count: results.length,
        next: null,
        previous: null,
        data_source: dataSource,
        resume_cursor_timestamp: resumeCursorTimestamp,
        consistency_warnings: consistencyWarnings,
        results,
      };
    }
    page += 1;
  }
  return {
    count: results.length,
    next: null,
    previous: null,
    data_source: dataSource,
    resume_cursor_timestamp: resumeCursorTimestamp,
    consistency_warnings: consistencyWarnings,
    results,
  };
}
