/**
 * useMetricsOverlay — hook that attaches metric overlay series
 * (Margin Ratio, ATR, Lock Threshold) directly onto the parent
 * candlestick chart so they share the exact same X-axis.
 *
 * Data is fetched based on the chart's visible time range:
 * when the user scrolls or zooms, the hook fetches the metrics
 * for the new viewport (debounced) and merges them into a local cache.
 */

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import {
  LineSeries,
  type IChartApi,
  type UTCTimestamp,
} from 'lightweight-charts';
import { fetchMetrics, type MetricPoint } from '../../../utils/fetchMetrics';
import { TaskType } from '../../../types/common';

export interface UseMetricsOverlayOptions {
  taskId: string;
  taskType: TaskType;
  executionRunId?: string;
  enableRealTimeUpdates?: boolean;
  chart: IChartApi | null;
  candleTimestamps?: number[];
  currentTickTimestamp?: string | null;
  programmaticScrollRef?: { current: boolean };
}

function metricVal(p: MetricPoint, key: string): number | null {
  const v = p.metrics[key];
  if (v === null || v === undefined) return null;
  return typeof v === 'string' ? parseFloat(v) : (v as number);
}

function resampleSnapshots(
  snapshots: MetricPoint[],
  candleTimestamps: number[]
): MetricPoint[] {
  if (snapshots.length === 0 || candleTimestamps.length === 0) return [];
  const lastSnapshotTime = snapshots[snapshots.length - 1].t;
  const result: MetricPoint[] = [];
  let si = 0;
  for (const ct of candleTimestamps) {
    if (ct > lastSnapshotTime) break;
    while (si < snapshots.length - 1 && snapshots[si + 1].t <= ct) si++;
    if (snapshots[si].t <= ct) result.push({ ...snapshots[si], t: ct });
  }
  return result;
}

function attachSeries(chart: IChartApi) {
  const mr = chart.addSeries(LineSeries, {
    color: '#3b82f6',
    lineWidth: 2,
    title: 'Margin Ratio',
    priceScaleId: 'left',
    priceFormat: {
      type: 'custom' as const,
      minMove: 0.01,
      formatter: (price: number) => `${price.toFixed(2)}%`,
    },
  });
  const atr = chart.addSeries(LineSeries, {
    color: '#8b5cf6',
    lineWidth: 2,
    title: 'Current ATR',
    priceScaleId: 'metrics-right',
  });
  const vt = chart.addSeries(LineSeries, {
    color: '#f97316',
    lineWidth: 1,
    lineStyle: 1,
    title: 'Lock Threshold',
    priceScaleId: 'metrics-right',
    crosshairMarkerVisible: false,
    lastValueVisible: true,
    priceLineVisible: false,
  });
  chart.priceScale('left').applyOptions({
    visible: true,
    borderColor: '#cbd5e1',
    minimumWidth: 60,
    ticksVisible: true,
    scaleMargins: { top: 0.7, bottom: 0.02 },
  });
  chart.priceScale('metrics-right').applyOptions({
    visible: true,
    borderColor: '#cbd5e1',
    minimumWidth: 60,
    ticksVisible: true,
    scaleMargins: { top: 0.7, bottom: 0.02 },
  });
  return { mr, atr, vt };
}

function computeInterval(rangeSeconds: number): number {
  return Math.max(1, Math.ceil(rangeSeconds / 60 / 2000));
}

function mergeSnapshots(
  existing: MetricPoint[],
  incoming: MetricPoint[]
): MetricPoint[] {
  if (incoming.length === 0) return existing;
  if (existing.length === 0) return incoming;
  const map = new Map<number, MetricPoint>();
  for (const p of existing) map.set(p.t, p);
  for (const p of incoming) map.set(p.t, p);
  return Array.from(map.values()).sort((a, b) => a.t - b.t);
}

export function useMetricsOverlay({
  taskId,
  taskType,
  executionRunId,
  enableRealTimeUpdates = false,
  chart,
  candleTimestamps,
  currentTickTimestamp,
  programmaticScrollRef,
}: UseMetricsOverlayOptions) {
  const seriesRef = useRef<ReturnType<typeof attachSeries> | null>(null);
  const attachedToChart = useRef<IChartApi | null>(null);
  const [snapshots, setSnapshots] = useState<MetricPoint[]>([]);
  const fetchedRangeRef = useRef<{ from: number; to: number } | null>(null);
  const latestTsRef = useRef<number | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchWindow = useCallback(
    async (from: number, to: number) => {
      const span = to - from;
      const bufFrom = from - span * 0.1;
      const bufTo = to + span * 0.1;
      const page = await fetchMetrics({
        taskId,
        taskType,
        executionRunId,
        since: new Date(bufFrom * 1000).toISOString(),
        until: new Date(bufTo * 1000).toISOString(),
        interval: computeInterval(bufTo - bufFrom),
        pageSize: 5000,
      });
      return page.results;
    },
    [taskId, taskType, executionRunId]
  );

  const isCovered = useCallback((from: number, to: number) => {
    const r = fetchedRangeRef.current;
    return r ? from >= r.from && to <= r.to : false;
  }, []);

  const expandRange = useCallback((from: number, to: number) => {
    const r = fetchedRangeRef.current;
    fetchedRangeRef.current = r
      ? { from: Math.min(r.from, from), to: Math.max(r.to, to) }
      : { from, to };
  }, []);

  // Keep latest timestamp ref in sync
  useEffect(() => {
    if (snapshots.length > 0)
      latestTsRef.current = snapshots[snapshots.length - 1].t;
  }, [snapshots]);

  // Initial fetch for the full candle range
  useEffect(() => {
    if (!candleTimestamps || candleTimestamps.length === 0) return;
    let cancelled = false;
    const from = candleTimestamps[0];
    const to = candleTimestamps[candleTimestamps.length - 1];
    fetchWindow(from, to)
      .then((data) => {
        if (!cancelled && data.length > 0) {
          setSnapshots(data);
          expandRange(from, to);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId, taskType, executionRunId, fetchWindow, expandRange]);

  // Viewport-driven fetch on scroll/zoom (debounced)
  useEffect(() => {
    if (!chart) return;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const handler = () => {
      const tr = chart.timeScale().getVisibleRange();
      if (!tr) return;
      const from = tr.from as number,
        to = tr.to as number;
      if (isCovered(from, to)) return;
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        fetchWindow(from, to)
          .then((data) => {
            if (data.length > 0) {
              setSnapshots((prev) => mergeSnapshots(prev, data));
              expandRange(from, to);
            }
          })
          .catch(() => {});
      }, 300);
    };
    chart.timeScale().subscribeVisibleTimeRangeChange(handler);
    return () => {
      if (timer) clearTimeout(timer);
      chart.timeScale().unsubscribeVisibleTimeRangeChange(handler);
    };
  }, [chart, fetchWindow, isCovered, expandRange]);

  // Real-time incremental polling
  useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const poll = async () => {
      try {
        const ts = latestTsRef.current;
        const page = await fetchMetrics({
          taskId,
          taskType,
          executionRunId,
          pageSize: 5000,
          since: ts ? new Date(ts * 1000).toISOString() : undefined,
        });
        if (page.results.length > 0)
          setSnapshots((prev) => mergeSnapshots(prev, page.results));
      } catch {
        /* silent */
      }
    };
    intervalRef.current = setInterval(poll, 5000);
    return () => {
      if (intervalRef.current !== null) clearInterval(intervalRef.current);
      intervalRef.current = null;
    };
  }, [enableRealTimeUpdates, taskId, taskType, executionRunId]);

  // Attach series once per chart instance
  useEffect(() => {
    if (!chart) return;
    seriesRef.current = null;
    attachedToChart.current = null;
    try {
      seriesRef.current = attachSeries(chart);
      attachedToChart.current = chart;
    } catch {
      /* disposed */
    }
    return () => {
      seriesRef.current = null;
      attachedToChart.current = null;
    };
  }, [chart]);

  const tickSec = useMemo(() => {
    if (!currentTickTimestamp) return null;
    const ms = new Date(currentTickTimestamp).getTime();
    return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
  }, [currentTickTimestamp]);

  // Push data to chart series
  useEffect(() => {
    const s = seriesRef.current;
    if (!s) return;
    const hasCandles = candleTimestamps && candleTimestamps.length > 0;
    if (!snapshots.length && !hasCandles) return;
    let extended: MetricPoint[] = [];
    if (snapshots.length > 0) {
      const aligned = hasCandles
        ? resampleSnapshots(snapshots, candleTimestamps)
        : snapshots;
      extended = aligned;
      if (tickSec !== null && hasCandles) {
        const last = candleTimestamps[candleTimestamps.length - 1];
        if (tickSec > last) {
          const extra = snapshots.filter((p) => p.t > last && p.t <= tickSec);
          if (extra.length > 0) extended = [...aligned, ...extra];
        }
      }
    }
    try {
      const saved = chart?.timeScale().getVisibleLogicalRange();
      if (programmaticScrollRef) programmaticScrollRef.current = true;
      s.mr.setData(
        extended
          .filter((p) => metricVal(p, 'margin_ratio') !== null)
          .map((p) => ({
            time: p.t as UTCTimestamp,
            value: (metricVal(p, 'margin_ratio') as number) * 100,
          }))
      );
      s.atr.setData(
        extended
          .filter((p) => metricVal(p, 'current_atr') !== null)
          .map((p) => ({
            time: p.t as UTCTimestamp,
            value: metricVal(p, 'current_atr') as number,
          }))
      );
      s.vt.setData(
        extended
          .filter(
            (p) =>
              metricVal(p, 'volatility_threshold') !== null &&
              (metricVal(p, 'volatility_threshold') as number) > 0
          )
          .map((p) => ({
            time: p.t as UTCTimestamp,
            value: metricVal(p, 'volatility_threshold') as number,
          }))
      );
      if (saved) {
        if (programmaticScrollRef) programmaticScrollRef.current = true;
        chart?.timeScale().setVisibleLogicalRange(saved);
      }
    } catch {
      /* Chart disposed */
    }
  }, [snapshots, candleTimestamps, chart, tickSec, programmaticScrollRef]);

  return { hasData: snapshots.length > 0 };
}
