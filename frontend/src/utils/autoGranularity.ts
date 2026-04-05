/**
 * Compute the recommended metrics granularity (in minutes) based on the
 * time range of the data.
 *
 * Thresholds (approximate):
 *   ≤ 2 weeks  → 1 min
 *   ≤ 1 month  → 5 min
 *   ≤ 3 months → 15 min
 *   ≤ 6 months → 1 hour
 *   ≤ 1 year   → 4 hours
 *   > 1 year   → 1 day
 */
export function computeAutoInterval(dataRangeSeconds: number): number {
  const DAY = 86_400;
  if (dataRangeSeconds <= 14 * DAY) return 1;
  if (dataRangeSeconds <= 31 * DAY) return 5;
  if (dataRangeSeconds <= 93 * DAY) return 15;
  if (dataRangeSeconds <= 183 * DAY) return 60;
  if (dataRangeSeconds <= 366 * DAY) return 240;
  return 1440;
}
