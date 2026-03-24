import { describe, expect, it } from 'vitest';
import { buildCycleMarkers } from '../../../src/components/tasks/detail/strategy/buildCycleMarkers';
import type { DisplayCycleStep } from '../../../src/types/strategyVisualization';

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/** Build a minimal DisplayCycleStep with sensible defaults. */
function makeStep(overrides: Partial<DisplayCycleStep> = {}): DisplayCycleStep {
  return {
    kind: 'open_position',
    event_type: 'open_position',
    entry_id: 1,
    parent_entry_id: null,
    timestamp: '2026-03-20T10:00:00Z',
    basket: 'trend',
    direction: 'long',
    step: 1,
    entry_price: '150.000',
    exit_price: null,
    units: '3000',
    layer_number: null,
    retracement_count: null,
    description: 'Open position',
    expected_interval_pips: null,
    actual_interval_pips: null,
    expected_tp_pips: null,
    actual_tp_pips: null,
    expected_exit_price: null,
    actual_exit_price: null,
    validation_status: 'not_applicable',
    ...overrides,
  };
}

/** Generate M5 candle times starting from a base UTC timestamp. */
function makeCandleTimes(baseIso: string, count: number): number[] {
  const base = Math.floor(new Date(baseIso).getTime() / 1000);
  return Array.from({ length: count }, (_, i) => base + i * 300);
}

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

describe('buildCycleMarkers', () => {
  const candleTimes = makeCandleTimes('2026-03-20T09:55:00Z', 20);
  // candleTimes[0] = 09:55, [1] = 10:00, [2] = 10:05, ...

  /* ---- Req 9.2: null timestamp skipping ---- */
  it('skips steps with null timestamp', () => {
    const steps = [
      makeStep({ timestamp: null, entry_id: 1 }),
      makeStep({ timestamp: '2026-03-20T10:00:00Z', entry_id: 2 }),
    ];

    const markers = buildCycleMarkers(steps, candleTimes);

    expect(markers).toHaveLength(1);
    expect(markers[0].text).toContain('OPEN');
  });

  it('returns empty array when all steps have null timestamps', () => {
    const steps = [
      makeStep({ timestamp: null }),
      makeStep({ timestamp: null }),
    ];

    const markers = buildCycleMarkers(steps, candleTimes);

    expect(markers).toHaveLength(0);
  });

  /* ---- Req 9.4: LONG = green up arrow, SHORT = red down arrow ---- */
  it('generates green up arrow for LONG open position', () => {
    const steps = [
      makeStep({
        event_type: 'open_position',
        direction: 'long',
        timestamp: '2026-03-20T10:00:00Z',
      }),
    ];

    const markers = buildCycleMarkers(steps, candleTimes);

    expect(markers).toHaveLength(1);
    expect(markers[0].shape).toBe('arrowUp');
    expect(markers[0].color).toBe('#16a34a'); // green
    expect(markers[0].position).toBe('belowBar');
  });

  it('generates red down arrow for SHORT open position', () => {
    const steps = [
      makeStep({
        event_type: 'open_position',
        direction: 'short',
        timestamp: '2026-03-20T10:00:00Z',
      }),
    ];

    const markers = buildCycleMarkers(steps, candleTimes);

    expect(markers).toHaveLength(1);
    expect(markers[0].shape).toBe('arrowDown');
    expect(markers[0].color).toBe('#ef4444'); // red
    expect(markers[0].position).toBe('aboveBar');
  });

  /* ---- Req 9.5: close position = gray square ---- */
  it('generates gray square for close position', () => {
    const steps = [
      makeStep({
        event_type: 'close_position',
        direction: 'long',
        timestamp: '2026-03-20T10:00:00Z',
      }),
    ];

    const markers = buildCycleMarkers(steps, candleTimes);

    expect(markers).toHaveLength(1);
    expect(markers[0].shape).toBe('square');
    expect(markers[0].color).toBe('#9ca3af'); // gray
  });

  it('generates gray square for SHORT close position as well', () => {
    const steps = [
      makeStep({
        event_type: 'close_position',
        direction: 'short',
        timestamp: '2026-03-20T10:05:00Z',
      }),
    ];

    const markers = buildCycleMarkers(steps, candleTimes);

    expect(markers).toHaveLength(1);
    expect(markers[0].shape).toBe('square');
    expect(markers[0].color).toBe('#9ca3af');
  });

  /* ---- L/R label construction ---- */
  it('includes L/R label when layer_number and retracement_count are set', () => {
    const steps = [
      makeStep({
        layer_number: 2,
        retracement_count: 3,
        timestamp: '2026-03-20T10:00:00Z',
      }),
    ];

    const markers = buildCycleMarkers(steps, candleTimes);

    expect(markers[0].text).toContain('L2/R3');
  });

  it('uses dash for missing layer_number in L/R label', () => {
    const steps = [
      makeStep({
        layer_number: null,
        retracement_count: 1,
        timestamp: '2026-03-20T10:00:00Z',
      }),
    ];

    const markers = buildCycleMarkers(steps, candleTimes);

    expect(markers[0].text).toContain('L-/R1');
  });

  it('uses dash for missing retracement_count in L/R label', () => {
    const steps = [
      makeStep({
        layer_number: 5,
        retracement_count: null,
        timestamp: '2026-03-20T10:00:00Z',
      }),
    ];

    const markers = buildCycleMarkers(steps, candleTimes);

    expect(markers[0].text).toContain('L5/R-');
  });

  it('omits L/R label when both layer_number and retracement_count are null', () => {
    const steps = [
      makeStep({
        layer_number: null,
        retracement_count: null,
        timestamp: '2026-03-20T10:00:00Z',
      }),
    ];

    const markers = buildCycleMarkers(steps, candleTimes);

    expect(markers[0].text).not.toMatch(/L\d/);
    expect(markers[0].text).not.toMatch(/R\d/);
  });

  /* ---- Text label construction ---- */
  it('builds correct text label with all parts', () => {
    const steps = [
      makeStep({
        event_type: 'open_position',
        direction: 'long',
        units: '5000',
        layer_number: 1,
        retracement_count: 2,
        timestamp: '2026-03-20T10:00:00Z',
      }),
    ];

    const markers = buildCycleMarkers(steps, candleTimes);

    // units=5000 → 5000/1000=5 → "5L"
    expect(markers[0].text).toBe('OPEN LONG 5L L1/R2');
  });

  it('builds CLOSE label for close_position', () => {
    const steps = [
      makeStep({
        event_type: 'close_position',
        direction: 'short',
        units: '2000',
        layer_number: null,
        retracement_count: null,
        timestamp: '2026-03-20T10:00:00Z',
      }),
    ];

    const markers = buildCycleMarkers(steps, candleTimes);

    expect(markers[0].text).toBe('CLOSE SHORT 2L');
  });

  /* ---- Req 9.1: timestamp snaps to nearest candle time ---- */
  it('snaps marker time to the nearest candle time', () => {
    // 10:02:30 is between candle[1]=10:00 and candle[2]=10:05
    // Closer to 10:00 (150s away) than 10:05 (150s away) — ties go to earlier
    const steps = [makeStep({ timestamp: '2026-03-20T10:01:00Z' })];

    const markers = buildCycleMarkers(steps, candleTimes);

    expect(markers).toHaveLength(1);
    // 10:01 is 60s after 10:00 and 240s before 10:05 → snaps to 10:00
    expect(Number(markers[0].time)).toBe(candleTimes[1]); // 10:00
  });

  /* ---- Req 9.3: markers sorted by time ascending ---- */
  it('returns markers sorted by time ascending', () => {
    const steps = [
      makeStep({
        entry_id: 3,
        timestamp: '2026-03-20T10:10:00Z', // candle[3]
      }),
      makeStep({
        entry_id: 1,
        timestamp: '2026-03-20T10:00:00Z', // candle[1]
      }),
      makeStep({
        entry_id: 2,
        timestamp: '2026-03-20T10:05:00Z', // candle[2]
      }),
    ];

    const markers = buildCycleMarkers(steps, candleTimes);

    expect(markers).toHaveLength(3);
    for (let i = 1; i < markers.length; i++) {
      expect(Number(markers[i].time)).toBeGreaterThanOrEqual(
        Number(markers[i - 1].time)
      );
    }
  });

  /* ---- Multiple markers (mixed open/close, long/short) ---- */
  it('generates correct markers for a mixed step sequence', () => {
    const steps = [
      makeStep({
        entry_id: 1,
        event_type: 'open_position',
        direction: 'long',
        units: '1000',
        timestamp: '2026-03-20T10:00:00Z',
      }),
      makeStep({
        entry_id: 2,
        event_type: 'open_position',
        direction: 'short',
        units: '2000',
        layer_number: 1,
        retracement_count: 1,
        basket: 'counter',
        timestamp: '2026-03-20T10:05:00Z',
      }),
      makeStep({
        entry_id: 2,
        event_type: 'close_position',
        direction: 'short',
        units: '2000',
        basket: 'counter',
        timestamp: '2026-03-20T10:10:00Z',
      }),
    ];

    const markers = buildCycleMarkers(steps, candleTimes);

    expect(markers).toHaveLength(3);

    // First: LONG open → green arrowUp
    expect(markers[0].shape).toBe('arrowUp');
    expect(markers[0].color).toBe('#16a34a');

    // Second: SHORT open → red arrowDown
    expect(markers[1].shape).toBe('arrowDown');
    expect(markers[1].color).toBe('#ef4444');

    // Third: close → gray square
    expect(markers[2].shape).toBe('square');
    expect(markers[2].color).toBe('#9ca3af');
  });

  /* ---- Edge: empty inputs ---- */
  it('returns empty array for empty steps', () => {
    expect(buildCycleMarkers([], candleTimes)).toEqual([]);
  });

  it('returns empty array when candleTimes is empty', () => {
    const steps = [makeStep({ timestamp: '2026-03-20T10:00:00Z' })];
    expect(buildCycleMarkers(steps, [])).toEqual([]);
  });

  /* ---- Edge: units handling ---- */
  it('omits lot label when units is null', () => {
    const steps = [
      makeStep({
        units: null,
        timestamp: '2026-03-20T10:00:00Z',
      }),
    ];

    const markers = buildCycleMarkers(steps, candleTimes);

    // Should not contain the lot label pattern (e.g. "3L")
    expect(markers[0].text).not.toMatch(/\d+L/);
  });

  it('handles direction being null', () => {
    const steps = [
      makeStep({
        direction: null,
        timestamp: '2026-03-20T10:00:00Z',
      }),
    ];

    const markers = buildCycleMarkers(steps, candleTimes);

    expect(markers).toHaveLength(1);
    // direction null → position aboveBar (not isLong), shape arrowDown
    expect(markers[0].position).toBe('aboveBar');
  });
});
