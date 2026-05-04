const SECOND = 1;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export const DEFAULT_SNOWBALL_NET_GRANULARITY = 'M1';
export const DEFAULT_SNOWBALL_NET_SIDE_BARS = 24 * 60;
const MAX_CHART_RANGE_BARS = 14 * 24 * 60;
const TARGET_AUTO_CHART_RANGE_BARS = 5000;

export const SNOWBALL_NET_GRANULARITY_OPTIONS = [
  'Auto',
  'M1',
  'M5',
  'M15',
  'M30',
  'H1',
  'H4',
  'D',
] as const;

export type SnowballNetGranularitySelection =
  (typeof SNOWBALL_NET_GRANULARITY_OPTIONS)[number];
export type SnowballNetFixedGranularity = Exclude<
  SnowballNetGranularitySelection,
  'Auto'
>;

const FIXED_GRANULARITY_OPTIONS: readonly SnowballNetFixedGranularity[] = [
  'M1',
  'M5',
  'M15',
  'M30',
  'H1',
  'H4',
  'D',
] as const;

const CHART_GRANULARITY_SECONDS: Record<SnowballNetFixedGranularity, number> = {
  M1: MINUTE,
  M5: 5 * MINUTE,
  M15: 15 * MINUTE,
  M30: 30 * MINUTE,
  H1: HOUR,
  H4: 4 * HOUR,
  D: DAY,
};

export function maxSnowballNetRangeSecondsForGranularity(
  granularity: SnowballNetFixedGranularity
): number {
  return CHART_GRANULARITY_SECONDS[granularity] * MAX_CHART_RANGE_BARS;
}

export function isSnowballNetGranularityAllowedForRange(
  granularity: SnowballNetGranularitySelection,
  rangeSeconds: number | null
): boolean {
  if (granularity === 'Auto' || rangeSeconds == null) return true;
  return rangeSeconds <= maxSnowballNetRangeSecondsForGranularity(granularity);
}

export function constrainSnowballNetGranularityForRange(
  granularity: SnowballNetFixedGranularity,
  rangeSeconds: number | null
): SnowballNetFixedGranularity {
  if (rangeSeconds == null) return granularity;
  if (isSnowballNetGranularityAllowedForRange(granularity, rangeSeconds)) {
    return granularity;
  }
  return (
    FIXED_GRANULARITY_OPTIONS.find((candidate) =>
      isSnowballNetGranularityAllowedForRange(candidate, rangeSeconds)
    ) ?? 'D'
  );
}

export function granularityForRangeSeconds(
  seconds: number
): SnowballNetFixedGranularity {
  for (const granularity of FIXED_GRANULARITY_OPTIONS) {
    const granularitySeconds = CHART_GRANULARITY_SECONDS[granularity];
    if (seconds / granularitySeconds <= TARGET_AUTO_CHART_RANGE_BARS) {
      return granularity;
    }
  }
  return 'D';
}
