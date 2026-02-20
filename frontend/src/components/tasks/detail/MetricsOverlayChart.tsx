/**
 * MetricsOverlayChart — single dual-axis chart rendered above the main
 * candlestick combining:
 *   • Right axis: Margin Ratio (%) with cut-start / cut-target thresholds
 *   • Left axis:  Current ATR (pips) & Lock Threshold (pips) *
 * Time axis is synchronised with the parent candlestick chart via
 * subscribeVisibleTimeRangeChange so scroll / zoom stays in lock-step.
 *
 * A SequencePositionLine is drawn at the same position as the candlestick
 * chart when enableRealTimeUpdates is active.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Box, Typography, CircularProgress } from '@mui/material';
import {
  createChart,
  LineSeries,
  type IChartApi,
  type UTCTimestamp,
} from 'lightweight-charts';
import {
  createSuppressedTickMarkFormatter,
  createTooltipTimeFormatter,
} from '../../../utils/adaptiveTimeScalePlugin';
import {
  fetchMetricSnapshots,
  type MetricSnapshotPoint,
} from '../../../utils/fetchMetricSnapshots';
import { TaskType } from '../../../types/common';
import { configurationsApi } from '../../../services/api/configurations';
import { SequencePositionLine } from '../../../utils/SequencePositionLine';

interface MetricsOverlayChartProps {
  taskId: string;
  taskType: TaskType;
  timezone: string;
  configId?: string;
  enableRealTimeUpdates?: boolean;
  /** Parent candlestick chart — used for time-axis sync */
  parentChart?: IChartApi | null;
  /** Current tick for SequencePositionLine */
  currentTick?: { timestamp: string; price: string | null } | null;
  /**
   * Sorted array of candle timestamps (UTC seconds) from the parent
   * candlestick chart.  When provided, metric snapshot data is resampled
   * onto these exact timestamps so the two charts share identical X-axis
   * data points and logical-index sync works perfectly.
   */
  candleTimestamps?: number[];
}

/** Thin horizontal line spanning the full time range for threshold markers */
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

/**
 * Resample metric snapshots onto candle timestamps.
 *
 * For each candle timestamp, we pick the latest snapshot whose timestamp
 * is <= the candle timestamp (i.e. the value that was current at that candle).
 *
 * - Candles before the first snapshot are skipped (no data yet).
 * - Candles after the last snapshot are also skipped — we don't extrapolate
 *   stale values into the future where no snapshots were recorded.
 */
function resampleSnapshots(
  snapshots: MetricSnapshotPoint[],
  candleTimestamps: number[]
): MetricSnapshotPoint[] {
  if (snapshots.length === 0 || candleTimestamps.length === 0) return [];

  const lastSnapshotTime = snapshots[snapshots.length - 1].t;
  const result: MetricSnapshotPoint[] = [];
  let si = 0; // pointer into snapshots

  for (const ct of candleTimestamps) {
    // Skip candles that are after the last snapshot — no data to show
    if (ct > lastSnapshotTime) break;

    // Advance si to the last snapshot with t <= ct
    while (si < snapshots.length - 1 && snapshots[si + 1].t <= ct) {
      si++;
    }
    // Only emit if the snapshot is at or before this candle
    if (snapshots[si].t <= ct) {
      result.push({ ...snapshots[si], t: ct });
    }
  }

  return result;
}

const CHART_HEIGHT = 200;

export const MetricsOverlayChart: React.FC<MetricsOverlayChartProps> = ({
  taskId,
  taskType,
  timezone,
  configId,
  enableRealTimeUpdates = false,
  parentChart,
  currentTick,
  candleTimestamps,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const sequenceLineRef = useRef<SequencePositionLine | null>(null);

  const [snapshots, setSnapshots] = useState<MetricSnapshotPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [marginCutStartRatio, setMarginCutStartRatio] = useState<
    number | undefined
  >();
  const [marginCutTargetRatio, setMarginCutTargetRatio] = useState<
    number | undefined
  >();

  // Fetch strategy config to get threshold values
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
      .catch(() => {
        // silent
      });
  }, [configId]);

  const loadData = useCallback(async () => {
    try {
      const data = await fetchMetricSnapshots(taskId, taskType);
      setSnapshots(data);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [taskId, taskType]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return undefined;
    const id = setInterval(loadData, 5000);
    return () => clearInterval(id);
  }, [enableRealTimeUpdates, loadData]);

  // ── Combined dual-axis chart ──────────────────────────────────
  useEffect(() => {
    if (loading || snapshots.length === 0) return;
    if (!containerRef.current) return;

    // When candle timestamps are provided, resample snapshots so the
    // metrics chart uses the exact same X-axis data points as the
    // candlestick chart.
    const aligned =
      candleTimestamps && candleTimestamps.length > 0
        ? resampleSnapshots(snapshots, candleTimestamps)
        : snapshots;

    // Derive the canonical timestamp array for threshold lines & helper series
    const timestamps = aligned.map((s) => s.t);
    // The helper series still uses ALL candle timestamps for logical-index sync.
    const fullTimestamps =
      candleTimestamps && candleTimestamps.length > 0
        ? candleTimestamps
        : timestamps;

    if (aligned.length === 0) {
      console.warn(
        '[MetricsOverlayChart] aligned is empty — skipping chart render'
      );
      return;
    }

    // Safe to destroy previous chart now that we know we will create a new one
    chartRef.current?.remove();

    // ── DEBUG: log data alignment info ──
    console.group('[MetricsOverlayChart] Data alignment debug');
    console.log('candleTimestamps count:', candleTimestamps?.length ?? 0);
    console.log('raw snapshots count:', snapshots.length);
    console.log('aligned count:', aligned.length);
    console.log(
      'helperTimestamps count (fullTimestamps):',
      fullTimestamps.length
    );
    if (candleTimestamps && candleTimestamps.length > 0) {
      console.log(
        'candle first:',
        new Date(candleTimestamps[0] * 1000).toISOString()
      );
      console.log(
        'candle last:',
        new Date(
          candleTimestamps[candleTimestamps.length - 1] * 1000
        ).toISOString()
      );
    }
    if (snapshots.length > 0) {
      console.log(
        'snapshot first:',
        new Date(snapshots[0].t * 1000).toISOString()
      );
      console.log(
        'snapshot last:',
        new Date(snapshots[snapshots.length - 1].t * 1000).toISOString()
      );
    }
    if (aligned.length > 0) {
      console.log(
        'aligned first:',
        new Date(aligned[0].t * 1000).toISOString()
      );
      console.log(
        'aligned last:',
        new Date(aligned[aligned.length - 1].t * 1000).toISOString()
      );
    }
    console.log('mrData count:', aligned.filter((s) => s.mr !== null).length);
    console.log('atrData count:', aligned.filter((s) => s.atr !== null).length);
    console.log(
      'vtData count:',
      aligned.filter((s) => s.vt !== null && (s.vt as number) > 0).length
    );
    console.groupEnd();

    const container = containerRef.current;
    const chart = createChart(container, {
      height: CHART_HEIGHT,
      layout: { background: { color: '#ffffff' }, textColor: '#334155' },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: '#f1f5f9' },
      },
      rightPriceScale: {
        borderColor: '#cbd5e1',
        visible: true,
        minimumWidth: 80,
      },
      leftPriceScale: {
        borderColor: '#cbd5e1',
        visible: true,
        minimumWidth: 80,
      },
      timeScale: {
        borderColor: '#cbd5e1',
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: createSuppressedTickMarkFormatter(),
      },
      localization: {
        timeFormatter: createTooltipTimeFormatter({ timezone }),
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
    });
    chartRef.current = chart;

    // ── Right axis: Margin Ratio (%) ──────────────────────────
    const mrSeries = chart.addSeries(LineSeries, {
      color: '#3b82f6',
      lineWidth: 2,
      title: 'Margin Ratio',
      priceScaleId: 'right',
      priceFormat: { type: 'percent' as const, minMove: 0.01 },
    });
    const mrData = aligned
      .filter((s) => s.mr !== null)
      .map((s) => ({
        time: s.t as UTCTimestamp,
        value: (s.mr as number) * 100,
      }));
    mrSeries.setData(mrData);

    // Margin threshold lines (red dotted, right axis)
    const addMarginThreshold = (value: number | undefined, label: string) => {
      if (value === undefined || value <= 0) return;
      const series = chart.addSeries(LineSeries, {
        color: '#ef4444',
        lineWidth: 1,
        lineStyle: 1,
        title: label,
        priceScaleId: 'right',
        crosshairMarkerVisible: false,
        lastValueVisible: true,
        priceLineVisible: false,
        priceFormat: { type: 'percent' as const, minMove: 0.01 },
      });
      series.setData(makeThresholdData(timestamps, value * 100));
    };
    addMarginThreshold(marginCutStartRatio, 'Cut Start');
    addMarginThreshold(marginCutTargetRatio, 'Cut Target');

    // ── Left axis: Current ATR & Lock Threshold (pips) ──────────
    const atrSeries = chart.addSeries(LineSeries, {
      color: '#8b5cf6',
      lineWidth: 2,
      title: 'Current ATR',
      priceScaleId: 'left',
    });
    const atrData = aligned
      .filter((s) => s.atr !== null)
      .map((s) => ({ time: s.t as UTCTimestamp, value: s.atr as number }));
    atrSeries.setData(atrData);

    const vtSeries = chart.addSeries(LineSeries, {
      color: '#f97316',
      lineWidth: 1,
      lineStyle: 1,
      title: 'Lock Threshold',
      priceScaleId: 'left',
      crosshairMarkerVisible: false,
      lastValueVisible: true,
      priceLineVisible: false,
    });
    const vtData = aligned
      .filter((s) => s.vt !== null && (s.vt as number) > 0)
      .map((s) => ({ time: s.t as UTCTimestamp, value: s.vt as number }));
    vtSeries.setData(vtData);

    // ── SequencePositionLine (vertical line at current tick) ──
    // The helper series MUST contain ALL candle timestamps (not just the
    // aligned subset) so that the logical-index count matches the parent
    // candlestick chart exactly.  This is what makes the logical-range
    // sync produce pixel-perfect alignment.
    const helperTimestamps =
      candleTimestamps && candleTimestamps.length > 0
        ? candleTimestamps
        : timestamps;
    const seqHelperSeries = chart.addSeries(LineSeries, {
      color: 'transparent',
      lineWidth: 1,
      priceScaleId: 'seq-helper',
      lastValueVisible: false,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    });
    chart.priceScale('seq-helper').applyOptions({ visible: false });
    seqHelperSeries.setData(
      helperTimestamps.map((t) => ({ time: t as UTCTimestamp, value: 0 }))
    );
    const seqLine = new SequencePositionLine({ maxExtrapolation: Infinity });
    seqHelperSeries.attachPrimitive(seqLine);
    sequenceLineRef.current = seqLine;

    // Bump version so the setPosition effect re-runs for the new instance
    setChartVersion((v) => v + 1);

    chart.timeScale().fitContent();

    const observer = new ResizeObserver(() => {
      const w = container.clientWidth;
      if (w > 0) chart.applyOptions({ width: w });
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      sequenceLineRef.current = null;
    };
  }, [
    loading,
    snapshots,
    marginCutStartRatio,
    marginCutTargetRatio,
    timezone,
    candleTimestamps,
  ]);

  // ── Time-axis sync with parent candlestick chart ──────────────
  useEffect(() => {
    if (!parentChart || !chartRef.current) return;

    const metricsChart = chartRef.current;
    let syncing = false;
    let disposed = false;

    // Parent → Metrics
    const onParentRangeChange = () => {
      if (disposed || syncing) return;
      syncing = true;
      try {
        const range = parentChart.timeScale().getVisibleLogicalRange();
        if (range && chartRef.current === metricsChart) {
          console.log(
            '[MetricsOverlayChart] sync Parent→Metrics logicalRange:',
            JSON.stringify(range)
          );
          metricsChart.timeScale().setVisibleLogicalRange(range);
        }
      } catch {
        // chart may have been disposed between frames
      }
      syncing = false;
    };

    // Metrics → Parent
    const onMetricsRangeChange = () => {
      if (disposed || syncing) return;
      syncing = true;
      try {
        const range = metricsChart.timeScale().getVisibleLogicalRange();
        if (range) {
          console.log(
            '[MetricsOverlayChart] sync Metrics→Parent logicalRange:',
            JSON.stringify(range)
          );
          parentChart.timeScale().setVisibleLogicalRange(range);
        }
      } catch {
        // chart may have been disposed between frames
      }
      syncing = false;
    };

    parentChart
      .timeScale()
      .subscribeVisibleLogicalRangeChange(onParentRangeChange);
    metricsChart
      .timeScale()
      .subscribeVisibleLogicalRangeChange(onMetricsRangeChange);

    // Initial sync: defer to next frame so the chart layout has settled
    const raf = requestAnimationFrame(() => {
      if (disposed) return;
      try {
        const range = parentChart.timeScale().getVisibleLogicalRange();
        if (range && chartRef.current === metricsChart) {
          metricsChart.timeScale().setVisibleLogicalRange(range);
        }
      } catch {
        // silent
      }
    });

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      try {
        parentChart
          .timeScale()
          .unsubscribeVisibleLogicalRangeChange(onParentRangeChange);
      } catch {
        // parent may already be disposed
      }
      try {
        metricsChart
          .timeScale()
          .unsubscribeVisibleLogicalRangeChange(onMetricsRangeChange);
      } catch {
        // metrics chart may already be disposed
      }
    };
  }, [parentChart, loading, snapshots]);

  // ── Update SequencePositionLine when currentTick changes ──────
  // `chartVersion` bumps every time the chart is recreated so this effect
  // re-runs and applies the position to the new SequencePositionLine instance.
  const [chartVersion, setChartVersion] = useState(0);

  useEffect(() => {
    const seq = sequenceLineRef.current;
    if (!seq) return;
    if (!enableRealTimeUpdates || !currentTick?.timestamp) {
      seq.clear();
      return;
    }
    // Price is not meaningful on the metrics chart, so pass null.
    // Use a short delay so the chart layout (fitContent + time-axis sync)
    // has settled before we compute the x-coordinate.
    const raf1 = requestAnimationFrame(() => {
      const raf2 = requestAnimationFrame(() => {
        if (sequenceLineRef.current === seq) {
          seq.setPosition(currentTick.timestamp, null);
        }
      });
      // store raf2 for cleanup isn't strictly needed since we guard with ===
      void raf2;
    });
    return () => cancelAnimationFrame(raf1);
  }, [currentTick?.timestamp, enableRealTimeUpdates, chartVersion]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
        <CircularProgress size={20} />
      </Box>
    );
  }

  if (snapshots.length === 0) return null;

  return (
    <Box sx={{ mt: 0, mb: 0 }}>
      <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
        Margin Ratio (%) &amp; Volatility — Current ATR / Lock Threshold (pips)
      </Typography>
      <Box
        ref={containerRef}
        sx={{
          width: '100%',
          height: CHART_HEIGHT,
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
        }}
      />
    </Box>
  );
};
