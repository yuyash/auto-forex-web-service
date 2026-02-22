/**
 * Detects gaps in candle data caused by market closures (weekends)
 * and returns series markers and gap ranges to indicate those periods.
 *
 * A gap is detected when the time difference between two consecutive
 * candles exceeds the expected interval by a large margin (>6x),
 * which typically indicates a weekend or holiday closure.
 */
import type { UTCTimestamp } from 'lightweight-charts';
import type { ClosedGap } from './MarketClosedHighlight';

export interface MarketClosedMarker {
  time: UTCTimestamp;
  position: 'aboveBar';
  shape: 'square';
  color: string;
  text: string;
  size: number;
}

/** Shared gap-detection logic used by both markers and the highlight plugin */
export function detectMarketGaps(times: number[]): ClosedGap[] {
  if (times.length < 3) return [];

  const diffs: number[] = [];
  for (let i = 1; i < times.length; i++) {
    diffs.push(times[i] - times[i - 1]);
  }
  diffs.sort((a, b) => a - b);
  const medianInterval = diffs[Math.floor(diffs.length / 2)];
  const gapThreshold = medianInterval * 6;

  const gaps: ClosedGap[] = [];
  const fmtDate = (d: Date) => d.toISOString().slice(5, 10).replace('-', '/');

  for (let i = 1; i < times.length; i++) {
    const gap = times[i] - times[i - 1];
    if (gap > gapThreshold) {
      const start = new Date(times[i - 1] * 1000);
      const end = new Date(times[i] * 1000);
      gaps.push({
        from: times[i - 1],
        to: times[i],
        label: `Market Closed ${fmtDate(start)}–${fmtDate(end)}`,
      });
    }
  }
  return gaps;
}

/**
 * Build "Market Closed" markers for gaps in candle data.
 */
export function buildMarketClosedMarkers(
  times: number[]
): MarketClosedMarker[] {
  return detectMarketGaps(times).map((gap) => ({
    time: gap.from as UTCTimestamp,
    position: 'aboveBar' as const,
    shape: 'square' as const,
    color: '#94a3b8',
    text: gap.label,
    size: 0,
  }));
}
