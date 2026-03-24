import type { Time } from 'lightweight-charts';
import type { DisplayCycleStep } from '../../../../types/strategyVisualization';
import { snapToCandleTimeInLoadedRange } from '../taskTrendPanel/shared';

export interface CycleChartMarker {
  time: Time;
  position: 'aboveBar' | 'belowBar';
  shape: 'arrowUp' | 'arrowDown' | 'square';
  color: string;
  text: string;
}

export function buildCycleMarkers(
  steps: DisplayCycleStep[],
  candleTimes: number[]
): CycleChartMarker[] {
  const markers: CycleChartMarker[] = [];

  for (const step of steps) {
    if (!step.timestamp) continue;

    const rawTime = Math.floor(new Date(step.timestamp).getTime() / 1000);
    const snappedTime = snapToCandleTimeInLoadedRange(rawTime, candleTimes);
    if (snappedTime == null) continue;

    const isClose = step.event_type === 'close_position';
    const isLong = step.direction === 'long';
    const units = step.units ? Math.abs(Number(step.units)) / 1000 : null;
    const lotLabel = units !== null ? `${Math.round(units)}L` : '';

    const lrLabel =
      step.layer_number != null || step.retracement_count != null
        ? `L${step.layer_number ?? '-'}/R${step.retracement_count ?? '-'}`
        : '';

    const textParts = [
      isClose ? 'CLOSE' : 'OPEN',
      step.direction?.toUpperCase() ?? '',
      lotLabel,
      lrLabel,
    ].filter(Boolean);

    markers.push({
      time: snappedTime as Time,
      position: isLong ? 'belowBar' : 'aboveBar',
      shape: isClose ? 'square' : isLong ? 'arrowUp' : 'arrowDown',
      color: isClose ? '#9ca3af' : isLong ? '#16a34a' : '#ef4444',
      text: textParts.join(' '),
    });
  }

  return markers.sort((a, b) => Number(a.time) - Number(b.time));
}
