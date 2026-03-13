import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/apiClient';
import type { Granularity } from '../types/chart';
import {
  clampRange,
  expandRange,
  mergeRanges,
  normalizeRange,
  subtractLoadedRanges,
  type TimeRange,
} from '../utils/windowedRanges';

export interface WindowedCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface UseWindowedCandlesOptions {
  instrument: string;
  granularity: Granularity | string;
  accountId?: string;
  startTime?: string;
  endTime?: string;
  initialCount?: number;
  edgeCount?: number;
  autoRefresh?: boolean;
  refreshIntervalSeconds?: number;
}

interface UseWindowedCandlesResult {
  candles: WindowedCandle[];
  isInitialLoading: boolean;
  isRefreshing: boolean;
  loadingOlder: boolean;
  loadingNewer: boolean;
  error: string | null;
  loadedRanges: TimeRange[];
  ensureRange: (range: TimeRange) => Promise<void>;
  fetchOlder: () => Promise<number>;
  fetchNewer: () => Promise<number>;
  refreshTail: () => Promise<number>;
  replaceWithCountWindow: (count?: number) => Promise<number>;
}

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

function parseCandles(raw: unknown): WindowedCandle[] {
  const arr = Array.isArray(raw) ? raw : [];
  const byTime = new Map<number, WindowedCandle>();

  for (const c of arr) {
    if (!c || typeof c !== 'object') continue;
    const rec = c as Record<string, unknown>;
    const timeRaw = rec.time;
    let ts: number;
    if (typeof timeRaw === 'number') {
      ts = timeRaw;
    } else if (typeof timeRaw === 'string') {
      const parsed = Date.parse(timeRaw);
      if (Number.isNaN(parsed)) continue;
      ts = Math.floor(parsed / 1000);
    } else {
      continue;
    }
    const open = Number(rec.open);
    const high = Number(rec.high);
    const low = Number(rec.low);
    const close = Number(rec.close);
    if ([open, high, low, close].some((value) => Number.isNaN(value))) continue;
    const volume = rec.volume != null ? Number(rec.volume) : undefined;
    byTime.set(ts, {
      time: ts,
      open,
      high,
      low,
      close,
      volume,
    });
  }

  return Array.from(byTime.values()).sort((a, b) => a.time - b.time);
}

function mergeCandles(
  current: WindowedCandle[],
  incoming: WindowedCandle[]
): WindowedCandle[] {
  const byTime = new Map<number, WindowedCandle>();
  for (const candle of current) byTime.set(candle.time, candle);
  for (const candle of incoming) byTime.set(candle.time, candle);
  return Array.from(byTime.values()).sort((a, b) => a.time - b.time);
}

function isoToSec(value?: string): number | null {
  if (!value) return null;
  const ms = new Date(value).getTime();
  return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
}

function isFiniteRange(range: TimeRange): boolean {
  return Number.isFinite(range.from) && Number.isFinite(range.to);
}

function buildRequestBounds(
  bounds: { from?: number; to?: number },
  granularity: Granularity | string
): TimeRange {
  return {
    from: Math.max(0, bounds.from ?? 0),
    to:
      bounds.to ??
      Math.floor(Date.now() / 1000) +
        (GRANULARITY_SECONDS[String(granularity)] ?? 60) * 2,
  };
}

export function useWindowedCandles({
  instrument,
  granularity,
  accountId,
  startTime,
  endTime,
  initialCount = 500,
  edgeCount = 500,
  autoRefresh = false,
  refreshIntervalSeconds = 60,
}: UseWindowedCandlesOptions): UseWindowedCandlesResult {
  const [candles, setCandles] = useState<WindowedCandle[]>([]);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [loadingNewer, setLoadingNewer] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadedRanges, setLoadedRanges] = useState<TimeRange[]>([]);

  const candlesRef = useRef<WindowedCandle[]>([]);
  const loadedRangesRef = useRef<TimeRange[]>([]);
  const inFlightKeysRef = useRef<Set<string>>(new Set());
  const bounds = useMemo(
    () => ({
      from: isoToSec(startTime) ?? undefined,
      to: isoToSec(endTime) ?? undefined,
    }),
    [startTime, endTime]
  );

  useEffect(() => {
    candlesRef.current = candles;
  }, [candles]);

  useEffect(() => {
    loadedRangesRef.current = loadedRanges;
  }, [loadedRanges]);

  const requestCandles = useCallback(
    async (query: Record<string, string | number | undefined>) => {
      const response = await api.get<{ candles?: unknown[] }>(
        '/api/market/candles/',
        {
          instrument,
          granularity,
          account_id: accountId,
          ...query,
        }
      );
      return parseCandles(response?.candles);
    },
    [accountId, granularity, instrument]
  );

  const mergeLoadedRange = useCallback((range: TimeRange) => {
    setLoadedRanges((prev) => mergeRanges([...prev, normalizeRange(range)]));
  }, []);

  const requestRangeOrBridgeGap = useCallback(
    async (range: TimeRange) => {
      const directChunk = await requestCandles({
        from_time: new Date(range.from * 1000).toISOString(),
        to_time: new Date(range.to * 1000).toISOString(),
      });
      if (directChunk.length > 0) {
        return {
          candles: directChunk,
          handledRange: range,
        };
      }

      const [beforeChunk, afterChunk] = await Promise.all([
        requestCandles({
          count: edgeCount,
          before: range.from,
        }),
        requestCandles({
          count: edgeCount,
          after: range.to,
        }),
      ]);
      const bridgedCandles = mergeCandles(beforeChunk, afterChunk);
      if (bridgedCandles.length === 0) {
        return {
          candles: [],
          handledRange: range,
        };
      }

      return {
        candles: bridgedCandles,
        handledRange: mergeRanges([
          range,
          {
            from: bridgedCandles[0].time,
            to: bridgedCandles[bridgedCandles.length - 1].time,
          },
        ])[0],
      };
    },
    [edgeCount, requestCandles]
  );

  const ensureRange = useCallback(
    async (requestedRange: TimeRange) => {
      if (!isFiniteRange(requestedRange)) return;
      const requestBounds = buildRequestBounds(bounds, granularity);
      const clamped = clampRange(
        expandRange(requestedRange, 0.15),
        requestBounds
      );
      if (!isFiniteRange(clamped) || clamped.to < clamped.from) return;
      const missing = subtractLoadedRanges(clamped, loadedRangesRef.current);
      if (missing.length === 0) return;

      setError(null);
      const fetched: WindowedCandle[] = [];

      for (const range of missing) {
        const key = `${range.from}:${range.to}`;
        if (inFlightKeysRef.current.has(key)) continue;
        inFlightKeysRef.current.add(key);
        try {
          const result = await requestRangeOrBridgeGap(range);
          if (result.candles.length > 0) {
            fetched.push(...result.candles);
          }
          mergeLoadedRange(result.handledRange);
        } catch (err) {
          setError(
            err instanceof Error ? err.message : 'Failed to load candles'
          );
        } finally {
          inFlightKeysRef.current.delete(key);
        }
      }

      if (fetched.length > 0) {
        setCandles((prev) => mergeCandles(prev, fetched));
      }
    },
    [bounds, granularity, mergeLoadedRange, requestRangeOrBridgeGap]
  );

  const replaceWithCountWindow = useCallback(
    async (count = initialCount) => {
      setIsInitialLoading(true);
      setError(null);
      try {
        const nextCandles = await requestCandles({ count });
        setCandles(nextCandles);
        if (nextCandles.length > 0) {
          setLoadedRanges([
            {
              from: nextCandles[0].time,
              to: nextCandles[nextCandles.length - 1].time,
            },
          ]);
        } else {
          setLoadedRanges([]);
        }
        return nextCandles.length;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load candles');
        return 0;
      } finally {
        setIsInitialLoading(false);
      }
    },
    [initialCount, requestCandles]
  );

  const fetchOlder = useCallback(async () => {
    const first = candlesRef.current[0];
    if (!first) return 0;
    setLoadingOlder(true);
    setError(null);
    try {
      const incoming = await requestCandles({
        count: edgeCount,
        before: first.time,
      });
      if (incoming.length > 0) {
        setCandles((prev) => mergeCandles(prev, incoming));
        mergeLoadedRange({
          from: incoming[0].time,
          to: incoming[incoming.length - 1].time,
        });
      }
      return incoming.length;
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load older candles'
      );
      return 0;
    } finally {
      setLoadingOlder(false);
    }
  }, [edgeCount, mergeLoadedRange, requestCandles]);

  const fetchNewer = useCallback(async () => {
    const last = candlesRef.current[candlesRef.current.length - 1];
    if (!last) return 0;
    setLoadingNewer(true);
    setError(null);
    try {
      const incoming = await requestCandles({
        count: edgeCount,
        after: last.time,
      });
      if (incoming.length > 0) {
        setCandles((prev) => mergeCandles(prev, incoming));
        mergeLoadedRange({
          from: incoming[0].time,
          to: incoming[incoming.length - 1].time,
        });
      }
      return incoming.length;
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load newer candles'
      );
      return 0;
    } finally {
      setLoadingNewer(false);
    }
  }, [edgeCount, mergeLoadedRange, requestCandles]);

  const refreshTail = useCallback(async () => {
    const current = candlesRef.current;
    if (current.length === 0) return 0;
    const from = current[Math.max(0, current.length - edgeCount)].time;
    const to = current[current.length - 1].time;
    setIsRefreshing(true);
    try {
      const incoming = await requestCandles({
        from_time: new Date(from * 1000).toISOString(),
        to_time: new Date(to * 1000).toISOString(),
      });
      if (incoming.length > 0) {
        setCandles((prev) => mergeCandles(prev, incoming));
        mergeLoadedRange({ from, to });
      }
      return incoming.length;
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to refresh candles'
      );
      return 0;
    } finally {
      setIsRefreshing(false);
    }
  }, [edgeCount, mergeLoadedRange, requestCandles]);

  useEffect(() => {
    candlesRef.current = [];
    loadedRangesRef.current = [];
    setCandles([]);
    setLoadedRanges([]);
    if (startTime && endTime) {
      const from = isoToSec(startTime);
      const to = isoToSec(endTime);
      if (from != null && to != null) {
        const initialTo = Math.min(
          to,
          from +
            Math.max(1, edgeCount - 1) *
              (GRANULARITY_SECONDS[String(granularity)] ?? 60)
        );
        setIsInitialLoading(true);
        void (async () => {
          try {
            const initialRange = {
              from,
              to: initialTo,
            };
            const result = await requestRangeOrBridgeGap(initialRange);
            setCandles(result.candles);
            const initialLoadedRanges: TimeRange[] = [result.handledRange];
            if (result.candles.length > 0) {
              initialLoadedRanges.push({
                from: result.candles[0].time,
                to: result.candles[result.candles.length - 1].time,
              });
            }
            setLoadedRanges(mergeRanges(initialLoadedRanges));
          } catch (err) {
            setError(
              err instanceof Error ? err.message : 'Failed to load candles'
            );
          } finally {
            setIsInitialLoading(false);
          }
        })();
        return;
      }
    }
    void replaceWithCountWindow();
  }, [
    edgeCount,
    endTime,
    instrument,
    granularity,
    replaceWithCountWindow,
    requestRangeOrBridgeGap,
    startTime,
  ]);

  useEffect(() => {
    if (!autoRefresh || refreshIntervalSeconds <= 0) return;
    const id = window.setInterval(() => {
      void refreshTail();
    }, refreshIntervalSeconds * 1000);
    return () => window.clearInterval(id);
  }, [autoRefresh, refreshIntervalSeconds, refreshTail]);

  return {
    candles,
    isInitialLoading,
    isRefreshing,
    loadingOlder,
    loadingNewer,
    error,
    loadedRanges,
    ensureRange,
    fetchOlder,
    fetchNewer,
    refreshTail,
    replaceWithCountWindow,
  };
}
