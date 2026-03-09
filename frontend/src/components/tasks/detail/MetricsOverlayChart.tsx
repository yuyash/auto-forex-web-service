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
  executionRunId?: number;
  enableRealTimeUpdates?: boolean;
  chart: IChartApi | null;
  candleTimestamps?: number[];
  /** Current tick timestamp (ISO string) — used to extend metric drawing up to the position line */
  currentTickTimestamp?: string | null;
  /** Guard ref to prevent metric data updates from disabling auto-follow on the parent chart */
  programmaticScrollRef?: { current: boolean };
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

  // Track the latest timestamp for incremental fetching.
  const sinceRef = useRef<number | null>(null);

  // Incremental fetch: only get new snapshots since last fetch.
  const loadIncremental = useCallback(async () => {
    try {
      const sinceIso = sinceRef.current
        ? new Date(sinceRef.current * 1000).toISOString()
        : undefined;
      const data = await fetchMetrics(
        taskId,
        taskType,
        10_000,
        sinceIso,
        executionRunId
      );
      if (data.length > 0) {
        setSnapshots((prev) => {
          // Merge: append new points (they are ordered by timestamp).
          const existingTs = new Set(prev.map((p) => p.t));
          const newPoints = data.filter((p) => !existingTs.has(p.t));
          if (newPoints.length === 0) return prev;
          return [...prev, ...newPoints];
        });
        // Update since to the latest timestamp.
        const maxT = Math.max(...data.map((p) => p.t));
        if (!sinceRef.current || maxT > sinceRef.current) {
          sinceRef.current = maxT;
        }
      }
    } catch {
      // silent
    }
  }, [taskId, taskType, executionRunId]);

  // Initial full fetch.
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetchMetrics(taskId, taskType, 10_000, undefined, executionRunId)
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
  }, [taskId, taskType, executionRunId]);

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

    // When there are no metric snapshots and no candles, nothing to draw.
    const hasCandles = candleTimestamps && candleTimestamps.length > 0;
    const hasSnapshots = snapshots.length > 0;

    if (!hasSnapshots && !hasCandles) return;

    let extended: MetricPoint[] = [];

    if (hasSnapshots) {
      const aligned = hasCandles
        ? resampleSnapshots(snapshots, candleTimestamps)
        : snapshots;

      // When a currentTickTimestamp is provided, extend the aligned data
      // with any snapshots that fall between the last candle and the tick
      // position.  This ensures the metric lines visually reach the
      // SequencePositionLine instead of stopping at the last closed candle.
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
      // Save the current visible range before calling setData so we can
      // restore it afterwards.  lightweight-charts resets the scroll
      // position to the last bar on setData, which causes the chart to
      // jump when a running task is stopped (enableRealTimeUpdates flips
      // to false, tickSec becomes null, and this effect re-runs).
      const savedRange = chart?.timeScale().getVisibleLogicalRange();

      // Guard all setData calls so the resulting visible-range changes
      // don't disable auto-follow on the parent chart.
      if (programmaticScrollRef) {
        programmaticScrollRef.current = true;
      }

      s.mr.setData(
        extended
          .filter((p) => p.mr !== null)
          .map((p) => ({
            time: p.t as UTCTimestamp,
            value: (p.mr as number) * 100,
          }))
      );
      s.atr.setData(
        extended
          .filter((p) => p.atr !== null)
          .map((p) => ({ time: p.t as UTCTimestamp, value: p.atr as number }))
      );
      s.vt.setData(
        extended
          .filter((p) => p.vt !== null && (p.vt as number) > 0)
          .map((p) => ({ time: p.t as UTCTimestamp, value: p.vt as number }))
      );

      // Restore the visible range so the chart doesn't jump.
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
