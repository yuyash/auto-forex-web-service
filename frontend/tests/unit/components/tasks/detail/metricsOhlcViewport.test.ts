import { describe, expect, it } from 'vitest';
import { buildMetricsOhlcVisibleRange } from '../../../../../src/components/tasks/detail/metricsOhlcViewport';

describe('buildMetricsOhlcVisibleRange', () => {
  it('keeps the full requested backtest range visible from the exact start', () => {
    const range = buildMetricsOhlcVisibleRange({
      startTime: '2024-01-01T00:00:00Z',
      endTime: '2024-01-05T00:00:00Z',
      granularity: 'H1',
    });

    expect(range).not.toBeNull();
    expect(range?.from).toBe(1704067200);
    expect(range?.to).toBe(1704528000);
  });

  it('anchors the live edge using the current tick timestamp', () => {
    const range = buildMetricsOhlcVisibleRange({
      startTime: '2024-01-01T00:00:00Z',
      currentTickTimestamp: '2024-01-01T12:00:00Z',
      latestCandleTimestamp: 1704106800,
      granularity: 'M15',
    });

    expect(range).not.toBeNull();
    expect(range?.from).toBe(1704067200);
    expect(range?.to).toBe(1704110400 + 14400);
  });

  it('falls back to the latest candle when no explicit live tick is available', () => {
    const range = buildMetricsOhlcVisibleRange({
      startTime: '2024-01-01T00:00:00Z',
      latestCandleTimestamp: 1704070800,
      granularity: 'M1',
    });

    expect(range).not.toBeNull();
    expect(range?.from).toBe(1704067200);
    expect(range?.to).toBe(1704070800 + 1200);
  });
});
