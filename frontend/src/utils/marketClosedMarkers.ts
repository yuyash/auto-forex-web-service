/**
 * Detect gaps that exist inside already-loaded candle ranges.
 *
 * The chart loads candle windows sparsely, so a plain diff across the whole
 * candle array will misclassify unloaded time spans as market closures.
 */
import type { ClosedGap } from './MarketClosedHighlight';
import type { TimeRange } from './windowedRanges';
import { formatInTimeZone } from 'date-fns-tz';

const GRANULARITY_SECONDS: Record<string, number> = {
  M1: 60,
  M2: 120,
  M4: 240,
  M5: 300,
  M10: 600,
  M15: 900,
  M30: 1800,
  H1: 3600,
  H2: 7200,
  H3: 10800,
  H4: 14400,
  H6: 21600,
  H8: 28800,
  H12: 43200,
  D: 86400,
  W: 604800,
  M: 2592000,
};

function normalizeTimes(times: number[]): number[] {
  return Array.from(
    new Set(
      times
        .filter((time) => Number.isFinite(time))
        .map((time) => Math.floor(time))
    )
  ).sort((a, b) => a - b);
}

function resolveExpectedIntervalSeconds(
  times: number[],
  granularity?: string
): number | null {
  const known = granularity
    ? GRANULARITY_SECONDS[String(granularity)]
    : undefined;
  if (known) return known;

  const normalized = normalizeTimes(times);
  if (normalized.length < 2) return null;

  const diffs: number[] = [];
  for (let i = 1; i < normalized.length; i++) {
    const diff = normalized[i] - normalized[i - 1];
    if (diff > 0) diffs.push(diff);
  }
  if (diffs.length === 0) return null;

  diffs.sort((a, b) => a - b);
  return diffs[Math.floor(diffs.length / 2)] ?? null;
}

function formatGapLabel(from: number, to: number): string {
  const fmtDate = (d: Date) => d.toISOString().slice(5, 10).replace('-', '/');
  return `Market Closed ${fmtDate(new Date(from * 1000))}–${fmtDate(new Date(to * 1000))}`;
}

function getWeekendAwareThreshold(expectedInterval: number): number {
  return Math.min(Math.max(expectedInterval * 6, 3600), 172800);
}

function getIsoWeekday(timeSec: number, timezone: string): number {
  return Number(formatInTimeZone(new Date(timeSec * 1000), timezone, 'i'));
}

function spansWeekendSession(
  fromSec: number,
  toSec: number,
  timezone: string
): boolean {
  if (toSec <= fromSec) return false;

  const durationSec = toSec - fromSec;
  if (durationSec < 24 * 3600) return false;

  const startWeekday = getIsoWeekday(fromSec, timezone);
  const endWeekday = getIsoWeekday(toSec, timezone);
  const startsNearWeekend = startWeekday === 5 || startWeekday === 6;
  const endsNearReopen = endWeekday === 7 || endWeekday === 1;
  if (!startsNearWeekend || !endsNearReopen) {
    return false;
  }

  const stepSec = 12 * 3600;
  for (let cursor = fromSec; cursor <= toSec; cursor += stepSec) {
    const weekday = getIsoWeekday(cursor, timezone);
    if (weekday === 6 || weekday === 7) {
      return true;
    }
  }

  return false;
}

function normalizeLoadedRanges(loadedRanges?: TimeRange[]): TimeRange[] {
  if (!loadedRanges || loadedRanges.length === 0) {
    return [{ from: Number.NEGATIVE_INFINITY, to: Number.POSITIVE_INFINITY }];
  }

  return [...loadedRanges]
    .filter(
      (range) =>
        Number.isFinite(range.from) &&
        Number.isFinite(range.to) &&
        range.to >= range.from
    )
    .sort((a, b) => a.from - b.from || a.to - b.to);
}

function buildGapMap(
  times: number[],
  granularity?: string,
  loadedRanges?: TimeRange[],
  timezone = 'UTC'
): Map<number, ClosedGap> {
  const normalized = normalizeTimes(times);
  const gaps = new Map<number, ClosedGap>();
  if (normalized.length < 2) return gaps;
  const expectedInterval = resolveExpectedIntervalSeconds(
    normalized,
    granularity
  );
  if (!expectedInterval) return gaps;
  const gapThreshold = getWeekendAwareThreshold(expectedInterval);
  const ranges = normalizeLoadedRanges(loadedRanges);
  for (let i = 1; i < normalized.length; i++) {
    const previous = normalized[i - 1];
    const current = normalized[i];
    const gap = current - previous;
    if (gap < gapThreshold) continue;

    const previousRangeIndex = ranges.findIndex(
      (range) => previous >= range.from && previous <= range.to
    );
    const currentRangeIndex = ranges.findIndex(
      (range) => current >= range.from && current <= range.to
    );
    const sameRange =
      previousRangeIndex !== -1 && previousRangeIndex === currentRangeIndex;

    if (!sameRange && !spansWeekendSession(previous, current, timezone)) {
      continue;
    }
    if (sameRange && !spansWeekendSession(previous, current, timezone)) {
      continue;
    }

    gaps.set(previous, {
      from: previous,
      to: current,
      label: formatGapLabel(previous, current),
    });
  }

  return gaps;
}

/** Shared gap-detection logic used by the highlight plugin. */
export function detectMarketGaps(
  times: number[],
  granularity?: string,
  loadedRanges?: TimeRange[],
  timezone = 'UTC'
): ClosedGap[] {
  return Array.from(
    buildGapMap(times, granularity, loadedRanges, timezone).values()
  );
}
