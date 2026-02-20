/**
 * useMetricsOverlay — hook that attaches metric overlay series
 * (Margin Ratio, ATR, Lock Threshold, cut-start/cut-target thresholds)
 * directly onto the parent candlestick chart so they share the exact
 * same X-axis.
 *
 * Metrics use two additional price scales:
 *   • 'metrics-right': Margin Ratio (%) + threshold lines
 *   • 'left':          Current ATR (pips) + Lock Threshold
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
import {
  fetchMetricSnapshots,
  type MetricSnapshotPoint,
} from '../../../utils/fetchMetricSnapshots';
import { TaskType } from '../../../types/common';
import { configurationsApi } from '../../../services/api/configurations';

export interface UseMetricsOverlayOptions {
  taskId: string;
  taskType: TaskType;
  configId?: string;
  enableRealTimeUpdates?: boolean;
  chart: IChartApi | null;
  candleTimestamps?: number[];
  /** Current tick timestamp (ISO string) — used to extend metric drawing up to the position line */
  currentTickTimestamp?: string | null;
}

function makeThresholdData(
  timestamps: number[],
  value: number
): { time: UTCTimestamp; value: number }[] {
  if (timestamps.length === 0) return [];
  return [
    { time: timestamps[0] as UTCTimestamp, value },
    { time: timestamps[timestamps.length - 1] as UTCTimestamp, value },
  ];
}

function resampleSnapshots(
  snapshots: MetricSnapshotPoint[],
  candleTimestamps: number[]
): MetricSnapshotPoint[] {
  if (snapshots.length === 0 || candleTimestamps.length === 0) return [];
  const lastSnapshotTime = snapshots[snapshots.length - 1].t;
  const result: MetricSnapshotPoint[] = [];
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
    priceScaleId: 'metrics-right',
    priceFormat: { type: 'percent' as const, minMove: 0.01 },
  });
  const cutStart = chart.addSeries(LineSeries, {
    color: '#ef4444',
    lineWidth: 1,
    lineStyle: 1,
    title: 'Cut Start',
    priceScaleId: 'metrics-right',
    crosshairMarkerVisible: false,
    lastValueVisible: true,
    priceLineVisible: false,
    priceFormat: { type: 'percent' as const, minMove: 0.01 },
  });
  const cutTarget = chart.addSeries(LineSeries, {
    color: '#ef4444',
    lineWidth: 1,
    lineStyle: 1,
    title: 'Cut Target',
    priceScaleId: 'metrics-right',
    crosshairMarkerVisible: false,
    lastValueVisible: true,
    priceLineVisible: false,
    priceFormat: { type: 'percent' as const, minMove: 0.01 },
  });
  const atr = chart.addSeries(LineSeries, {
    color: '#8b5cf6',
    lineWidth: 2,
    title: 'Current ATR',
    priceScaleId: 'left',
  });
  const vt = chart.addSeries(LineSeries, {
    color: '#f97316',
    lineWidth: 1,
    lineStyle: 1,
    title: 'Lock Threshold',
    priceScaleId: 'left',
    crosshairMarkerVisible: false,
    lastValueVisible: true,
    priceLineVisible: false,
  });

  // Configure scales now that series exist
  chart.priceScale('metrics-right').applyOptions({
    visible: true,
    borderColor: '#cbd5e1',
    minimumWidth: 60,
    scaleMargins: { top: 0.7, bottom: 0.02 },
  });
  chart.priceScale('left').applyOptions({
    visible: true,
    borderColor: '#cbd5e1',
    minimumWidth: 60,
    ticksVisible: true,
    scaleMargins: { top: 0.7, bottom: 0.02 },
  });

  return { mr, cutStart, cutTarget, atr, vt };
}

export function useMetricsOverlay({
  taskId,
  taskType,
  configId,
  enableRealTimeUpdates = false,
  chart,
  candleTimestamps,
  currentTickTimestamp,
}: UseMetricsOverlayOptions) {
  const seriesRef = useRef<ReturnType<typeof attachSeries> | null>(null);
  const attachedToChart = useRef<IChartApi | null>(null);

  const [snapshots, setSnapshots] = useState<MetricSnapshotPoint[]>([]);
  const [marginCutStartRatio, setMarginCutStartRatio] = useState<
    number | undefined
  >();
  const [marginCutTargetRatio, setMarginCutTargetRatio] = useState<
    number | undefined
  >();

  // Fetch strategy config
  useEffect(() => {
    if (!configId) return;
    configurationsApi
      .get(configId)
      .then((config) => {
        const params = (config.parameters ?? {}) as Record<string, string>;
        const start = parseFloat(params.margin_cut_start_ratio);
        const target = parseFloat(params.margin_cut_target_ratio);
        if (Number.isFinite(start)) setMarginCutStartRatio(start);
        if (Number.isFinite(target)) setMarginCutTargetRatio(target);
      })
      .catch(() => {});
  }, [configId]);

  // Fetch snapshots
  const loadData = useCallback(async () => {
    try {
      const data = await fetchMetricSnapshots(taskId, taskType, 10_000);
      if (data.length > 0) setSnapshots(data);
    } catch {
      // silent
    }
  }, [taskId, taskType]);

  // Initial fetch + optional polling.
  // We avoid calling any setState-containing function directly in the effect
  // body.  Instead we use inline .then() for the initial fetch (subscription
  // callback pattern) and wrap setInterval in a ref so the effect body never
  // references loadData.
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetchMetricSnapshots(taskId, taskType, 10_000)
      .then((data) => {
        if (!cancelled && data.length > 0) setSnapshots(data);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [taskId, taskType]);

  // Polling effect — setInterval with loadData is a subscription, which the
  // rule permits.
  useEffect(() => {
    if (!enableRealTimeUpdates) return undefined;
    intervalRef.current = setInterval(loadData, 5000);
    return () => {
      if (intervalRef.current !== null) clearInterval(intervalRef.current);
      intervalRef.current = null;
    };
  }, [enableRealTimeUpdates, loadData]);

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
    if (snapshots.length === 0) return;

    const aligned =
      candleTimestamps && candleTimestamps.length > 0
        ? resampleSnapshots(snapshots, candleTimestamps)
        : snapshots;
    if (aligned.length === 0) return;

    // When a currentTickTimestamp is provided, extend the aligned data
    // with any snapshots that fall between the last candle and the tick
    // position.  This ensures the metric lines visually reach the
    // SequencePositionLine instead of stopping at the last closed candle.
    let extended = aligned;
    if (tickSec !== null && candleTimestamps && candleTimestamps.length > 0) {
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

    const timestamps = extended.map((p) => p.t);

    try {
      s.mr.setData(
        extended
          .filter((p) => p.mr !== null)
          .map((p) => ({
            time: p.t as UTCTimestamp,
            value: (p.mr as number) * 100,
          }))
      );
      s.cutStart.setData(
        marginCutStartRatio !== undefined && marginCutStartRatio > 0
          ? makeThresholdData(timestamps, marginCutStartRatio * 100)
          : []
      );
      s.cutTarget.setData(
        marginCutTargetRatio !== undefined && marginCutTargetRatio > 0
          ? makeThresholdData(timestamps, marginCutTargetRatio * 100)
          : []
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
    } catch {
      // Chart disposed mid-update — ignore
    }
  }, [
    snapshots,
    candleTimestamps,
    marginCutStartRatio,
    marginCutTargetRatio,
    chart,
    tickSec,
  ]);

  return { hasData: snapshots.length > 0 };
}
