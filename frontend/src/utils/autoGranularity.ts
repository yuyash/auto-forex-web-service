/**
 * Compute the recommended metrics granularity (in minutes) based on the
 * time range of the data.
 *
 * Thresholds (approximate target: ≤ ~1500 data points):
 *   ≤ 1 day    → 1 min   (up to 1,440 points)
 *   ≤ 1 week   → 5 min   (up to 2,016 points)
 *   ≤ 1 month  → 15 min  (up to 2,976 points)
 *   ≤ 3 months → 1 hour  (up to 2,232 points)
 *   ≤ 1 year   → 4 hours (up to 2,190 points)
 *   > 1 year   → 1 day
 */
export function computeAutoInterval(dataRangeSeconds: number): number {
  const DAY = 86_400;
  if (dataRangeSeconds <= 1 * DAY) return 1;
  if (dataRangeSeconds <= 7 * DAY) return 5;
  if (dataRangeSeconds <= 31 * DAY) return 15;
  if (dataRangeSeconds <= 93 * DAY) return 60;
  if (dataRangeSeconds <= 366 * DAY) return 240;
  return 1440;
}
