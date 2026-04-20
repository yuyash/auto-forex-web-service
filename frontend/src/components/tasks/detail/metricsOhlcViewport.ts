import type { Time } from 'lightweight-charts';

const GRANULARITY_SECONDS: Record<string, number> = {
  M1: 60,
  M5: 300,
  M15: 900,
  H1: 3600,
  H4: 14400,
  D: 86400,
};

const MIN_VIEWPORT_SECONDS = 60;
const RIGHT_PAD_RATIO = 1 / 3;

function toUnixSeconds(value?: string | null): number | null {
  if (!value) return null;
  const ms = new Date(value).getTime();
  return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
}

function getGranularitySeconds(granularity: string): number {
  return GRANULARITY_SECONDS[granularity] ?? 60;
}

export interface MetricsOhlcVisibleRangeInput {
  startTime: string;
  endTime?: string;
  currentTickTimestamp?: string | null;
  latestCandleTimestamp?: number | null;
  granularity: string;
}

export function buildMetricsOhlcVisibleRange({
  startTime,
  endTime,
  currentTickTimestamp,
  latestCandleTimestamp,
  granularity,
}: MetricsOhlcVisibleRangeInput): { from: Time; to: Time } | null {
  const startSec = toUnixSeconds(startTime);
  if (startSec == null) return null;

  const explicitEndSec = toUnixSeconds(endTime);
  const currentTickSec = toUnixSeconds(currentTickTimestamp);
  const latestDataSec = Math.max(
    startSec,
    explicitEndSec ?? startSec,
    currentTickSec ?? startSec,
    latestCandleTimestamp ?? startSec
  );
  const dataSpanSec = Math.max(MIN_VIEWPORT_SECONDS, latestDataSec - startSec);
  const rightPadSec = Math.max(
    getGranularitySeconds(granularity),
    Math.ceil(dataSpanSec * RIGHT_PAD_RATIO)
  );

  return {
    from: startSec as Time,
    to: (latestDataSec + rightPadSec) as Time,
  };
}
