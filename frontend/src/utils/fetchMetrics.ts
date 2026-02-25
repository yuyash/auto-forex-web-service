/**
 * Fetch metrics (margin ratio, volatility) for replay overlay charts.
 */

import { getAuthToken } from '../api/client';
import { TaskType } from '../types/common';
import { handleAuthErrorStatus } from './authEvents';

export interface MetricPoint {
  /** Unix timestamp (seconds) */
  t: number;
  /** Margin ratio (required_margin / NAV) */
  mr: number | null;
  /** Current ATR in pips */
  atr: number | null;
  /** Baseline ATR in pips */
  base: number | null;
  /** Volatility threshold (baseline * multiplier) */
  vt: number | null;
}

export async function fetchMetrics(
  taskId: string,
  taskType: TaskType,
  maxPoints?: number,
  since?: string,
  celeryTaskId?: string
): Promise<MetricPoint[]> {
  const prefix =
    taskType === TaskType.BACKTEST
      ? '/api/trading/tasks/backtest'
      : '/api/trading/tasks/trading';

  const searchParams = new URLSearchParams();
  if (maxPoints) searchParams.set('max_points', String(maxPoints));
  if (since) searchParams.set('since', since);
  if (celeryTaskId) searchParams.set('celery_task_id', celeryTaskId);
  const qs = searchParams.toString();
  const url = `${prefix}/${taskId}/metrics/${qs ? `?${qs}` : ''}`;

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

  if (!response.ok) return [];

  const body = (await response.json().catch(() => ({}))) as {
    metrics?: MetricPoint[];
  };
  return body.metrics ?? [];
}
