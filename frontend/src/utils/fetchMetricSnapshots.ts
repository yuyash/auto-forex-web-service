/**
 * Fetch metric snapshots (margin ratio, volatility) for replay overlay charts.
 */

import { getAuthToken } from '../api/client';
import { TaskType } from '../types/common';
import { handleAuthErrorStatus } from './authEvents';

export interface MetricSnapshotPoint {
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

export async function fetchMetricSnapshots(
  taskId: string,
  taskType: TaskType,
  maxPoints?: number,
  since?: string,
  celeryTaskId?: string
): Promise<MetricSnapshotPoint[]> {
  const prefix =
    taskType === TaskType.BACKTEST
      ? '/api/trading/tasks/backtest'
      : '/api/trading/tasks/trading';

  const searchParams = new URLSearchParams();
  if (maxPoints) searchParams.set('max_points', String(maxPoints));
  if (since) searchParams.set('since', since);
  if (celeryTaskId) searchParams.set('celery_task_id', celeryTaskId);
  const qs = searchParams.toString();
  const url = `${prefix}/${taskId}/metric_snapshots/${qs ? `?${qs}` : ''}`;

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
    context: 'metric_snapshots',
  });

  if (!response.ok) return [];

  const body = (await response.json().catch(() => ({}))) as {
    snapshots?: MetricSnapshotPoint[];
  };
  return body.snapshots ?? [];
}
