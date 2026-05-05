import { describe, expect, it } from 'vitest';
import {
  constrainSnowballNetGranularityForRange,
  granularityForRangeSeconds,
  isSnowballNetGranularityAllowedForRange,
  maxSnowballNetRangeSecondsForGranularity,
} from '../../../../../src/components/tasks/detail/strategy/snowballNetChartRange';

const DAY_SECONDS = 24 * 60 * 60;

describe('SnowballNet chart granularity range limits', () => {
  it('allows M1 ranges up to two weeks', () => {
    const twoWeeks = 14 * DAY_SECONDS;

    expect(maxSnowballNetRangeSecondsForGranularity('M1')).toBe(twoWeeks);
    expect(isSnowballNetGranularityAllowedForRange('M1', twoWeeks)).toBe(true);
    expect(isSnowballNetGranularityAllowedForRange('M1', twoWeeks + 60)).toBe(
      false
    );
  });

  it('selects an auto granularity that keeps the chart size practical', () => {
    expect(granularityForRangeSeconds(2 * DAY_SECONDS)).toBe('M5');
    expect(granularityForRangeSeconds(15 * DAY_SECONDS)).toBe('M15');
    expect(granularityForRangeSeconds(30 * DAY_SECONDS)).toBe('M30');
    expect(granularityForRangeSeconds(365 * DAY_SECONDS)).toBe('D');
    expect(
      constrainSnowballNetGranularityForRange('M1', 15 * DAY_SECONDS)
    ).toBe('M5');
  });
});
