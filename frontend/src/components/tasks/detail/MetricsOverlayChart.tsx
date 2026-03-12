/**
 * useMetricsOverlay — hook that attaches metric overlay series
 * (Margin Ratio, ATR, Lock Threshold) directly onto the parent
 * candlestick chart so they share the exact same X-axis.
 *
 * Metrics use two additional price scales:
 *   • 'left':          Margin Ratio (%)
 *   • 'metrics-right': Current ATR (pips) + Lock Threshold
 *
 * The candlestick series lives on the default 'right' price scale,
 * so there is no conflict.
 *
 * Data is fetched with time-range windowing: only the visible range
 * (plus a small buffer) is requested from the API, keeping payloads small.
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
  /** Current tick timestamp (ISO string) — used to extend metric drawing */
  currentTickTimestamp?: string | null;
  /** Guard ref to prevent metric data updates from disabling auto-follow */
  programmaticScrollRef?: { current: boolean };
}

/** Extract a numeric metric value from the JSON metrics object. */
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

  // Configure scales now that series exist
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

/**
 * Compute an appropriate aggregation interval (minutes) based on the
 * visible time range so we never request more than ~2000 points.
 */
function computeInterval(rangeSeconds: number): number {
  const targetPoints = 2000;
  const intervalMin = Math.ceil(rangeSeconds / 60 / targetPoints);
  return Math.max(1, intervalMin);
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

  // Track the visible time range for windowed fetching
  const visibleRangeRef = useRef<{ from: number; to: number } | null>(null);

  // Derive visible range from candle timestamps
  useEffect(() => {
    if (!candleTimestamps || candleTimestamps.length === 0) return;
    visibleRangeRef.current = {
      from: candleTimestamps[0],
      to: candleTimestamps[candleTimestamps.length - 1],
    };
  }, [candleTimestamps]);

  const loadMetrics = useCallback(
    async (since?: string) => {
      const range = visibleRangeRef.current;
      // Compute interval from the full candle range
      const rangeSeconds = range ? range.to - range.from : 0;
      const interval = rangeSeconds > 0 ? computeInterval(rangeSeconds) : 1;

      const page = await fetchMetrics({
        taskId,
        taskType,
        since,
        executionRunId,
        interval,
        pageSize: 5000,
      });
      return page.results;
    },
    [taskId, taskType, executionRunId]
  );

  // Track the latest timestamp for incremental fetching.
  const sinceRef = useRef<number | null>(null);

  // Incremental fetch: only get new snapshots since last fetch.
  const loadIncremental = useCallback(async () => {
    try {
      const sinceIso = sinceRef.current
        ? new Date(sinceRef.current * 1000).toISOString()
        : undefined;
      const data = await loadMetrics(sinceIso);
      if (data.length > 0) {
        setSnapshots((prev) => {
          const existingTs = new Set(prev.map((p) => p.t));
          const newPoints = data.filter((p) => !existingTs.has(p.t));
          if (newPoints.length === 0) return prev;
          return [...prev, ...newPoints];
        });
        const maxT = Math.max(...data.map((p) => p.t));
        if (!sinceRef.current || maxT > sinceRef.current) {
          sinceRef.current = maxT;
        }
      }
    } catch {
      // silent
    }
  }, [loadMetrics]);

  // Initial full fetch.
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    loadMetrics()
      .then((data) => {
        if (!cancelled && data.length > 0) {
          setSnapshots(data);
          const maxT = Math.max(...data.map((p) => p.t));
          sinceRef.current = maxT;
        }
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [loadMetrics]);

  // Incremental polling while task is running.
  useEffect(() => {
    if (!enableRealTimeUpdates) return undefined;
    intervalRef.current = setInterval(loadIncremental, 5000);
    return () => {
      if (intervalRef.current !== null) clearInterval(intervalRef.current);
      intervalRef.current = null;
    };
  }, [enableRealTimeUpdates, loadIncremental]);

  // ── Attach series (once per chart instance) ────────────────────
  useEffect(() => {
    if (!chart) return;
    seriesRef.current = null;
    attachedToChart.current = null;
    try {
      seriesRef.current = attachSeries(chart);
      attachedToChart.current = chart;
    } catch {
      // chart may have been disposed
    }
    return () => {
      seriesRef.current = null;
      attachedToChart.current = null;
    };
  }, [chart]);

  // ── Derive the current tick time in seconds for clipping ────
  const tickSec = useMemo(() => {
    if (!currentTickTimestamp) return null;
    const ms = new Date(currentTickTimestamp).getTime();
    return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
  }, [currentTickTimestamp]);

  // ── Set data (runs on every data / threshold / tick change) ──
  useEffect(() => {
    const s = seriesRef.current;
    if (!s) return;

    const hasCandles = candleTimestamps && candleTimestamps.length > 0;
    const hasSnapshots = snapshots.length > 0;
    if (!hasSnapshots && !hasCandles) return;

    let extended: MetricPoint[] = [];

    if (hasSnapshots) {
      const aligned = hasCandles
        ? resampleSnapshots(snapshots, candleTimestamps)
        : snapshots;

      extended = aligned;
      if (tickSec !== null && hasCandles) {
        const lastCandleTime = candleTimestamps[candleTimestamps.length - 1];
        if (tickSec > lastCandleTime) {
          const extra = snapshots.filter(
            (p) => p.t > lastCandleTime && p.t <= tickSec
          );
          if (extra.length > 0) {
            extended = [...aligned, ...extra];
          }
        }
      }
    }

    try {
      const savedRange = chart?.timeScale().getVisibleLogicalRange();

      if (programmaticScrollRef) {
        programmaticScrollRef.current = true;
      }

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

      if (savedRange) {
        if (programmaticScrollRef) {
          programmaticScrollRef.current = true;
        }
        chart?.timeScale().setVisibleLogicalRange(savedRange);
      }
    } catch {
      // Chart disposed mid-update — ignore
    }
  }, [snapshots, candleTimestamps, chart, tickSec, programmaticScrollRef]);

  return { hasData: snapshots.length > 0 };
}
