import { useEffect, useMemo } from 'react';
import type { Time, UTCTimestamp } from 'lightweight-charts';
import {
  findFirstCandleAtOrAfter,
  findLastCandleAtOrBefore,
  parseUtcTimestamp,
  snapToCandleTimeInLoadedRange,
  toEventMarkerTime,
} from './shared';
import type { CandlePoint, ReplayTrade } from './shared';
import type { TaskEvent } from '../../../../hooks/useTaskEvents';

interface ChartMarker {
  time: Time;
  position: 'aboveBar' | 'belowBar';
  shape: 'circle' | 'arrowUp' | 'arrowDown' | 'square';
  color: string;
  text?: string;
  size?: number;
}

interface UseTaskTrendMarkersParams {
  candles: CandlePoint[];
  taskLifecycleEvents: TaskEvent[];
  strategyEvents: TaskEvent[];
  trades: ReplayTrade[];
  selectedTradeId: string | null;
  highlightedTradeIds: Set<string>;
  markersVisible: boolean;
  startTimeSec: number | null;
  endTimeSec: number | null;
  markerDisplayCutoffSec: number | null;
  markersRef: {
    current: { setMarkers: (markers: ChartMarker[]) => void } | null;
  };
  programmaticScrollRef: { current: boolean };
  reportChartWarning: (message: string | null) => void;
}

export function useTaskTrendMarkers({
  candles,
  taskLifecycleEvents,
  strategyEvents,
  trades,
  selectedTradeId,
  highlightedTradeIds,
  markersVisible,
  startTimeSec,
  endTimeSec,
  markerDisplayCutoffSec,
  markersRef,
  programmaticScrollRef,
  reportChartWarning,
}: UseTaskTrendMarkersParams): void {
  const eventMarkers = useMemo(() => {
    const candleTimes = candles.map((c) => Number(c.time));
    const markers: ChartMarker[] = [];

    for (const event of taskLifecycleEvents) {
      const rawTime = toEventMarkerTime(event);
      if (!rawTime) continue;
      const time = snapToCandleTimeInLoadedRange(Number(rawTime), candleTimes);
      if (!time) continue;
      markers.push({
        time,
        position: 'aboveBar',
        shape: 'circle',
        color: '#2563eb',
        text: String(event.event_type_display || event.event_type || ''),
      });
    }

    for (const event of strategyEvents) {
      const rawTime = toEventMarkerTime(event);
      if (!rawTime) continue;
      const time = snapToCandleTimeInLoadedRange(Number(rawTime), candleTimes);
      if (!time) continue;
      markers.push({
        time,
        position: 'aboveBar',
        shape: 'arrowDown',
        color: '#111111',
        text: String(event.event_type_display || event.event_type || ''),
      });
    }

    if (startTimeSec != null) {
      const time = findFirstCandleAtOrAfter(startTimeSec, candleTimes);
      if (time) {
        markers.push({
          time,
          position: 'aboveBar',
          shape: 'arrowDown',
          color: '#111111',
          text: 'START',
        });
      }
    }

    if (endTimeSec != null) {
      const time = findLastCandleAtOrBefore(endTimeSec, candleTimes);
      if (time) {
        markers.push({
          time,
          position: 'aboveBar',
          shape: 'arrowDown',
          color: '#111111',
          text: 'STOP',
        });
      }
    }

    return markers
      .filter((marker) => {
        if (markerDisplayCutoffSec == null) {
          return true;
        }
        return Number(marker.time) <= markerDisplayCutoffSec;
      })
      .sort((a, b) => Number(a.time) - Number(b.time));
  }, [
    candles,
    endTimeSec,
    markerDisplayCutoffSec,
    startTimeSec,
    strategyEvents,
    taskLifecycleEvents,
  ]);

  useEffect(() => {
    if (!markersRef.current) {
      return;
    }
    const candleTimes = candles.map((c) => Number(c.time));
    const renderedTradeMarkers = trades
      .map((trade) => {
        const selected =
          trade.id === selectedTradeId || highlightedTradeIds.has(trade.id);
        // When markers are hidden, only render selected/highlighted trades
        if (!markersVisible && !selected) return null;
        const units = Number(trade.units);
        const lots = Number.isFinite(units) ? Math.abs(units) / 1000 : null;
        const executionMethod = String(
          trade.execution_method || ''
        ).toLowerCase();
        const isClose =
          executionMethod === 'take_profit' ||
          executionMethod === 'margin_protection' ||
          executionMethod === 'volatility_lock' ||
          executionMethod === 'close_position' ||
          executionMethod === 'volatility_hedge_neutralize';
        const direction: 'long' | 'short' =
          trade.direction === 'long' || trade.direction === 'short'
            ? trade.direction
            : Number.isFinite(units) && units < 0
              ? 'short'
              : 'long';
        const lotLabel = lots === null ? '' : `${Math.round(lots)}L`;
        const dirLabel = direction.toUpperCase();
        const rawTradeTime = parseUtcTimestamp(trade.timestamp);
        const markerTime =
          rawTradeTime != null
            ? snapToCandleTimeInLoadedRange(Number(rawTradeTime), candleTimes)
            : null;

        return {
          time: (markerTime ?? 0) as UTCTimestamp,
          position:
            direction === 'short'
              ? ('aboveBar' as const)
              : ('belowBar' as const),
          shape:
            direction === 'short'
              ? ('arrowDown' as const)
              : ('arrowUp' as const),
          color: selected
            ? '#f59e0b'
            : isClose
              ? '#9ca3af'
              : direction === 'long'
                ? '#16a34a'
                : '#ef4444',
          text: isClose
            ? `CLOSE ${dirLabel} ${lotLabel}`.trim()
            : `OPEN ${dirLabel} ${lotLabel}`.trim(),
        };
      })
      .filter((marker): marker is NonNullable<typeof marker> => {
        if (!marker || Number(marker.time) <= 0) {
          return false;
        }
        if (markerDisplayCutoffSec == null) {
          return true;
        }
        return Number(marker.time) <= markerDisplayCutoffSec;
      });

    try {
      programmaticScrollRef.current = true;
      const eventMarkersToShow = markersVisible ? eventMarkers : [];
      markersRef.current.setMarkers(
        [...eventMarkersToShow, ...renderedTradeMarkers].sort(
          (a, b) => Number(a.time) - Number(b.time)
        )
      );
      requestAnimationFrame(() => {
        reportChartWarning(null);
      });
    } catch {
      requestAnimationFrame(() => {
        reportChartWarning('Failed to render trade markers.');
      });
    }
  }, [
    candles,
    eventMarkers,
    highlightedTradeIds,
    markerDisplayCutoffSec,
    markersRef,
    markersVisible,
    programmaticScrollRef,
    reportChartWarning,
    selectedTradeId,
    trades,
  ]);
}
