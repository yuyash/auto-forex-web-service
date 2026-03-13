import { detectMarketGaps } from '../../../src/utils/marketClosedMarkers';

function toSec(value: string): number {
  return Math.floor(new Date(value).getTime() / 1000);
}

describe('marketClosedMarkers', () => {
  it('ignores small candle dropouts inside a loaded range', () => {
    const times = [
      toSec('2026-01-09T19:00:00Z'),
      toSec('2026-01-09T20:00:00Z'),
      toSec('2026-01-09T22:00:00Z'),
      toSec('2026-01-09T23:00:00Z'),
    ];

    const gaps = detectMarketGaps(
      times,
      'H1',
      [
        {
          from: toSec('2026-01-09T19:00:00Z'),
          to: toSec('2026-01-09T23:00:00Z'),
        },
      ],
      'Asia/Tokyo'
    );

    expect(gaps).toEqual([]);
  });

  it('ignores a 9-minute intraday outage on M1 candles', () => {
    const times = [
      toSec('2025-01-03T04:16:00Z'),
      toSec('2025-01-03T04:17:00Z'),
      toSec('2025-01-03T04:26:00Z'),
      toSec('2025-01-03T04:27:00Z'),
    ];

    const gaps = detectMarketGaps(
      times,
      'M1',
      [
        {
          from: toSec('2025-01-03T04:16:00Z'),
          to: toSec('2025-01-03T04:27:00Z'),
        },
      ],
      'Asia/Tokyo'
    );

    expect(gaps).toEqual([]);
  });

  it('detects a historical weekend gap from the configured granularity', () => {
    const times = [
      toSec('2026-01-09T19:00:00Z'),
      toSec('2026-01-09T20:00:00Z'),
      toSec('2026-01-09T21:00:00Z'),
      toSec('2026-01-11T22:00:00Z'),
      toSec('2026-01-11T23:00:00Z'),
    ];

    const gaps = detectMarketGaps(times, 'H1', undefined, 'UTC');

    expect(gaps).toHaveLength(1);
    expect(gaps[0]).toMatchObject({
      from: toSec('2026-01-09T21:00:00Z'),
      to: toSec('2026-01-11T22:00:00Z'),
    });
  });

  it('does not treat unloaded gaps between fetched windows as market closures', () => {
    const times = [
      toSec('2026-01-09T19:00:00Z'),
      toSec('2026-01-09T20:00:00Z'),
      toSec('2026-01-09T21:00:00Z'),
      toSec('2026-01-14T12:00:00Z'),
      toSec('2026-01-14T13:00:00Z'),
      toSec('2026-01-14T14:00:00Z'),
    ];

    const gaps = detectMarketGaps(
      times,
      'H1',
      [
        {
          from: toSec('2026-01-09T19:00:00Z'),
          to: toSec('2026-01-09T21:00:00Z'),
        },
        {
          from: toSec('2026-01-14T12:00:00Z'),
          to: toSec('2026-01-14T14:00:00Z'),
        },
      ],
      'UTC'
    );

    expect(gaps).toEqual([]);
  });

  it('detects the real weekend closure even when the two sides were loaded separately', () => {
    const times = [
      toSec('2025-01-03T04:58:00Z'),
      toSec('2025-01-03T04:59:00Z'),
      toSec('2025-01-05T05:00:00Z'),
      toSec('2025-01-05T05:01:00Z'),
    ];

    const gaps = detectMarketGaps(
      times,
      'M1',
      [
        {
          from: toSec('2025-01-03T04:58:00Z'),
          to: toSec('2025-01-03T04:59:00Z'),
        },
        {
          from: toSec('2025-01-05T05:00:00Z'),
          to: toSec('2025-01-05T05:01:00Z'),
        },
      ],
      'Asia/Tokyo'
    );

    expect(gaps).toHaveLength(1);
    expect(gaps[0]).toMatchObject({
      from: toSec('2025-01-03T04:59:00Z'),
      to: toSec('2025-01-05T05:00:00Z'),
    });
  });

  it('keeps real weekend gaps inside a loaded range', () => {
    const times = [
      toSec('2026-01-09T19:00:00Z'),
      toSec('2026-01-09T20:00:00Z'),
      toSec('2026-01-09T21:00:00Z'),
      toSec('2026-01-11T22:00:00Z'),
      toSec('2026-01-11T23:00:00Z'),
    ];

    const gaps = detectMarketGaps(
      times,
      'H1',
      [
        {
          from: toSec('2026-01-09T19:00:00Z'),
          to: toSec('2026-01-11T23:00:00Z'),
        },
      ],
      'UTC'
    );

    expect(gaps).toHaveLength(1);
    expect(gaps[0]).toMatchObject({
      from: toSec('2026-01-09T21:00:00Z'),
      to: toSec('2026-01-11T22:00:00Z'),
    });
  });
});
