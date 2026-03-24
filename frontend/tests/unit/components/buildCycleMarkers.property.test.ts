import { describe, expect, it } from 'vitest';
import * as fc from 'fast-check';
import { buildCycleMarkers } from '../../../src/components/tasks/detail/strategy/buildCycleMarkers';
import type { DisplayCycleStep } from '../../../src/types/strategyVisualization';

/* ------------------------------------------------------------------ */
/*  Arbitraries                                                        */
/* ------------------------------------------------------------------ */

/** Arbitrary for a valid ISO 8601 timestamp string (or null). */
const arbTimestamp: fc.Arbitrary<string | null> = fc.oneof(
  fc.constant(null),
  // Use integer epoch seconds to avoid invalid Date issues during shrinking
  fc
    .integer({ min: 1577836800, max: 1924991999 })
    .map((epochSec) => new Date(epochSec * 1000).toISOString())
);

/** Arbitrary for event_type. */
const arbEventType: fc.Arbitrary<'open_position' | 'close_position'> =
  fc.constantFrom('open_position' as const, 'close_position' as const);

/** Arbitrary for direction. */
const arbDirection: fc.Arbitrary<'long' | 'short' | null> = fc.constantFrom(
  'long' as const,
  'short' as const,
  null
);

/** Arbitrary for units (string representation of a number, or null). */
const arbUnits: fc.Arbitrary<string | null> = fc.oneof(
  fc.constant(null),
  fc.integer({ min: 1000, max: 100000 }).map(String)
);

/** Arbitrary for layer_number / retracement_count (nullable positive int). */
const arbNullablePositiveInt: fc.Arbitrary<number | null> = fc.oneof(
  fc.constant(null),
  fc.integer({ min: 1, max: 20 })
);

/** Arbitrary for a DisplayCycleStep with sensible defaults. */
const arbStep: fc.Arbitrary<DisplayCycleStep> = fc.record({
  kind: fc.constantFrom(
    'open_position',
    'close_position',
    'trend_tp',
    'counter_tp'
  ),
  event_type: arbEventType,
  entry_id: fc.oneof(fc.constant(null), fc.integer({ min: 1, max: 10000 })),
  parent_entry_id: fc.oneof(
    fc.constant(null),
    fc.integer({ min: 1, max: 10000 })
  ),
  timestamp: arbTimestamp,
  basket: fc.constantFrom('trend' as const, 'counter' as const),
  direction: arbDirection,
  step: fc.oneof(fc.constant(null), fc.integer({ min: 1, max: 100 })),
  entry_price: fc.oneof(
    fc.constant(null),
    fc.double({ min: 100, max: 200, noNaN: true }).map((n) => n.toFixed(3))
  ),
  exit_price: fc.oneof(
    fc.constant(null),
    fc.double({ min: 100, max: 200, noNaN: true }).map((n) => n.toFixed(3))
  ),
  units: arbUnits,
  layer_number: arbNullablePositiveInt,
  retracement_count: arbNullablePositiveInt,
  description: fc.constant('Test step'),
  expected_interval_pips: fc.constant(null),
  actual_interval_pips: fc.constant(null),
  expected_tp_pips: fc.constant(null),
  actual_tp_pips: fc.constant(null),
  expected_exit_price: fc.constant(null),
  actual_exit_price: fc.constant(null),
  validation_status: fc.constantFrom(
    'pass' as const,
    'fail' as const,
    'not_applicable' as const
  ),
});

/**
 * Arbitrary for a sorted array of candle times (ascending, unique, M5-spaced).
 * Generates a base time and then N candles at 300s intervals.
 */
const arbCandleTimes: fc.Arbitrary<number[]> = fc
  .record({
    base: fc.integer({ min: 1577836800, max: 1893456000 }), // 2020–2030 range in epoch seconds
    count: fc.integer({ min: 0, max: 200 }),
  })
  .map(({ base, count }) => {
    // Align base to 5-minute boundary
    const aligned = Math.floor(base / 300) * 300;
    return Array.from({ length: count }, (_, i) => aligned + i * 300);
  });

/* ------------------------------------------------------------------ */
/*  Property 8: マーカー生成の正確性                                      */
/*  Validates: Requirements 8.3, 8.4, 9.1, 9.2, 9.3, 9.4, 9.5        */
/* ------------------------------------------------------------------ */

describe('Property 8: マーカー生成の正確性', () => {
  /**
   * (a) Steps with null timestamps are skipped — no marker generated.
   * **Validates: Requirements 9.2**
   */
  it('(a) steps with null timestamps produce no markers', () => {
    fc.assert(
      fc.property(
        fc.array(arbStep, { minLength: 1, maxLength: 50 }),
        arbCandleTimes,
        (steps, candleTimes) => {
          const markers = buildCycleMarkers(steps, candleTimes);

          const stepsWithTimestamp = steps.filter((s) => s.timestamp !== null);
          // Markers can be at most the number of steps with non-null timestamps
          // (could be fewer if candleTimes is empty → snapToCandleTimeInLoadedRange returns null)
          expect(markers.length).toBeLessThanOrEqual(stepsWithTimestamp.length);

          // If candleTimes is empty, no markers at all
          if (candleTimes.length === 0) {
            expect(markers.length).toBe(0);
          }
        }
      ),
      { numRuns: 200 }
    );
  });

  /**
   * (b) Each marker snaps to the nearest candle time in the loaded range.
   * Every marker's time must be one of the candle times.
   * **Validates: Requirements 8.3, 9.1**
   */
  it('(b) each marker time is one of the candle times', () => {
    fc.assert(
      fc.property(
        fc.array(arbStep, { minLength: 1, maxLength: 50 }),
        arbCandleTimes.filter((ct) => ct.length > 0),
        (steps, candleTimes) => {
          const markers = buildCycleMarkers(steps, candleTimes);
          const candleTimeSet = new Set(candleTimes);

          for (const marker of markers) {
            expect(candleTimeSet.has(Number(marker.time))).toBe(true);
          }
        }
      ),
      { numRuns: 200 }
    );
  });

  /**
   * (c) Markers are sorted by time ascending.
   * **Validates: Requirements 9.3**
   */
  it('(c) markers are sorted by time ascending', () => {
    fc.assert(
      fc.property(
        fc.array(arbStep, { minLength: 0, maxLength: 50 }),
        arbCandleTimes,
        (steps, candleTimes) => {
          const markers = buildCycleMarkers(steps, candleTimes);

          for (let i = 1; i < markers.length; i++) {
            expect(Number(markers[i].time)).toBeGreaterThanOrEqual(
              Number(markers[i - 1].time)
            );
          }
        }
      ),
      { numRuns: 200 }
    );
  });

  /**
   * (d) Open position markers: LONG = green (#16a34a) arrowUp belowBar,
   *     SHORT = red (#ef4444) arrowDown aboveBar.
   * (e) Close position markers: gray (#9ca3af) square.
   * **Validates: Requirements 8.4, 9.4, 9.5**
   */
  it('(d/e) marker shape and color match event_type and direction', () => {
    fc.assert(
      fc.property(
        fc.array(arbStep, { minLength: 1, maxLength: 50 }),
        arbCandleTimes.filter((ct) => ct.length > 0),
        (steps, candleTimes) => {
          const markers = buildCycleMarkers(steps, candleTimes);

          // Each marker corresponds to a step (in order of original steps array,
          // but markers are sorted by time). We verify properties on each marker.
          for (const marker of markers) {
            const isClose = marker.text.startsWith('CLOSE');
            const isOpen = marker.text.startsWith('OPEN');

            // Every marker must be either OPEN or CLOSE
            expect(isClose || isOpen).toBe(true);

            if (isClose) {
              // Close position → gray square
              expect(marker.shape).toBe('square');
              expect(marker.color).toBe('#9ca3af');
            } else {
              // Open position
              const isLong = marker.text.includes('LONG');
              const isShort = marker.text.includes('SHORT');

              if (isLong) {
                expect(marker.shape).toBe('arrowUp');
                expect(marker.color).toBe('#16a34a');
                expect(marker.position).toBe('belowBar');
              } else if (isShort) {
                expect(marker.shape).toBe('arrowDown');
                expect(marker.color).toBe('#ef4444');
                expect(marker.position).toBe('aboveBar');
              }
              // direction=null → arrowDown, aboveBar (not isLong)
            }
          }
        }
      ),
      { numRuns: 200 }
    );
  });

  /**
   * Combined: marker count equals the number of steps with non-null timestamps
   * when candleTimes is non-empty (since snapToCandleTimeInLoadedRange clamps
   * to the loaded range and always returns a value for non-empty candleTimes).
   * **Validates: Requirements 9.2**
   */
  it('marker count equals steps-with-timestamp count when candleTimes is non-empty', () => {
    fc.assert(
      fc.property(
        fc.array(arbStep, { minLength: 0, maxLength: 50 }),
        arbCandleTimes.filter((ct) => ct.length > 0),
        (steps, candleTimes) => {
          const markers = buildCycleMarkers(steps, candleTimes);
          const expectedCount = steps.filter(
            (s) => s.timestamp !== null
          ).length;
          expect(markers.length).toBe(expectedCount);
        }
      ),
      { numRuns: 200 }
    );
  });
});
