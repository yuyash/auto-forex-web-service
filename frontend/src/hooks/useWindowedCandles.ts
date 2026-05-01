import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getApiErrorCode, getApiErrorMessage } from '../api/apiClient';
import { marketApi } from '../services/api/market';
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
  initialLoadMode?: 'recent-window' | 'full-range';
  initialFocusTime?: string;
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
  errorCode: string | null;
  loadedRanges: TimeRange[];
  dataRanges: TimeRange[];
  ensureRange: (range: TimeRange) => Promise<void>;
  fetchOlder: () => Promise<number>;
  fetchNewer: () => Promise<number>;
  refreshTail: () => Promise<number>;
  replaceWithRange: (
    range: TimeRange,
    options?: { preserveOnEmpty?: boolean }
  ) => Promise<number>;
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
const MAX_CANDLES_PER_REQUEST = 5000;

function getGranularitySeconds(granularity: Granularity | string): number {
  return GRANULARITY_SECONDS[String(granularity)] ?? 60;
}

function floorToGranularity(
  timeSec: number,
  granularitySeconds: number
): number {
  if (!Number.isFinite(timeSec) || granularitySeconds <= 0) return timeSec;
  return Math.floor(timeSec / granularitySeconds) * granularitySeconds;
}

function ceilToGranularity(
  timeSec: number,
  granularitySeconds: number
): number {
  if (!Number.isFinite(timeSec) || granularitySeconds <= 0) return timeSec;
  return Math.ceil(timeSec / granularitySeconds) * granularitySeconds;
}

function alignRangeToGranularity(
  range: TimeRange,
  granularity: Granularity | string
): TimeRange {
  const granularitySeconds = getGranularitySeconds(granularity);
  return {
    from: floorToGranularity(range.from, granularitySeconds),
    to: ceilToGranularity(range.to, granularitySeconds),
  };
}

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
    if (
      [rec.open, rec.high, rec.low, rec.close].some((value) => value == null) ||
      [open, high, low, close].some((value) => !Number.isFinite(value))
    ) {
      continue;
    }
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
  const granularitySeconds = getGranularitySeconds(granularity);
  const nowSec = Math.floor(Date.now() / 1000);
  const maxAllowedTo = floorToGranularity(nowSec, granularitySeconds);
  return {
    from: Math.max(0, floorToGranularity(bounds.from ?? 0, granularitySeconds)),
    to:
      bounds.to != null
        ? Math.min(
            ceilToGranularity(bounds.to, granularitySeconds),
            maxAllowedTo
          )
        : maxAllowedTo,
  };
}

function buildTrailingRange(
  rightEdgeSec: number,
  count: number,
  granularity: Granularity | string,
  bounds: { from?: number; to?: number }
): TimeRange {
  const granularitySeconds = getGranularitySeconds(granularity);
  const safeCount = Math.max(1, count);
  return clampRange(
    alignRangeToGranularity(
      {
        from: rightEdgeSec - Math.max(0, safeCount - 1) * granularitySeconds,
        to: rightEdgeSec,
      },
      granularity
    ),
    buildRequestBounds(bounds, granularity)
  );
}

export function useWindowedCandles({
  instrument,
  granularity,
  accountId,
  startTime,
  endTime,
  initialLoadMode = 'recent-window',
  initialFocusTime,
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
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [loadedRanges, setLoadedRanges] = useState<TimeRange[]>([]);
  const [dataRanges, setDataRanges] = useState<TimeRange[]>([]);

  const candlesRef = useRef<WindowedCandle[]>([]);
  const loadedRangesRef = useRef<TimeRange[]>([]);
  const dataRangesRef = useRef<TimeRange[]>([]);
  const inFlightKeysRef = useRef<Set<string>>(new Set());
  const hardResetKeyRef = useRef<string | null>(null);
  const initialRequestSeqRef = useRef(0);
  const bounds = useMemo(
    () => ({
      from: isoToSec(startTime) ?? undefined,
      to: isoToSec(endTime) ?? undefined,
    }),
    [startTime, endTime]
  );
  const initialFocusTimeSec = useMemo(
    () => isoToSec(initialFocusTime),
    [initialFocusTime]
  );
  const initialFocusTimeRef = useRef<number | null>(initialFocusTimeSec);
  const granularitySeconds = useMemo(
    () => getGranularitySeconds(granularity),
    [granularity]
  );
  const hardResetKey = useMemo(
    () =>
      [
        instrument,
        accountId ?? '',
        granularity,
        startTime ?? '',
        initialLoadMode,
      ].join('|'),
    [accountId, granularity, initialLoadMode, instrument, startTime]
  );

  useEffect(() => {
    candlesRef.current = candles;
  }, [candles]);

  useEffect(() => {
    initialFocusTimeRef.current = initialFocusTimeSec;
  }, [initialFocusTimeSec]);

  useEffect(() => {
    loadedRangesRef.current = loadedRanges;
  }, [loadedRanges]);

  useEffect(() => {
    dataRangesRef.current = dataRanges;
  }, [dataRanges]);

  const requestCandles = useCallback(
    async (query: Record<string, string | number | undefined>) => {
      const response = await marketApi.getCandles({
        instrument,
        granularity,
        account_id: accountId,
        ...query,
      });
      return parseCandles(response?.candles);
    },
    [accountId, granularity, instrument]
  );

  const requestCandleRange = useCallback(
    async (range: TimeRange) => {
      const estimatedCandles =
        Math.ceil(Math.max(0, range.to - range.from) / granularitySeconds) + 1;
      if (estimatedCandles <= MAX_CANDLES_PER_REQUEST) {
        return requestCandles({
          from_time: new Date(range.from * 1000).toISOString(),
          to_time: new Date(range.to * 1000).toISOString(),
        });
      }

      const chunks: WindowedCandle[] = [];
      const maxSpanSeconds =
        Math.max(1, MAX_CANDLES_PER_REQUEST - 1) * granularitySeconds;
      let cursor = range.from;
      while (cursor < range.to) {
        const chunkTo = Math.min(range.to, cursor + maxSpanSeconds);
        const chunk = await requestCandles({
          from_time: new Date(cursor * 1000).toISOString(),
          to_time: new Date(chunkTo * 1000).toISOString(),
        });
        chunks.push(...chunk);
        if (chunkTo >= range.to) break;
        cursor = chunkTo;
      }
      return mergeCandles([], chunks);
    },
    [granularitySeconds, requestCandles]
  );

  const setRequestError = useCallback((err: unknown, fallback: string) => {
    setErrorCode(getApiErrorCode(err));
    setError(
      getApiErrorMessage(err) ?? (err instanceof Error ? err.message : fallback)
    );
  }, []);

  const mergeLoadedRange = useCallback((range: TimeRange) => {
    setLoadedRanges((prev) => mergeRanges([...prev, normalizeRange(range)]));
  }, []);

  const mergeDataRanges = useCallback((ranges: TimeRange[]) => {
    if (ranges.length === 0) return;
    setDataRanges((prev) =>
      mergeRanges([...prev, ...ranges.map(normalizeRange)])
    );
  }, []);

  const requestRangeOrBridgeGap = useCallback(
    async (range: TimeRange) => {
      const alignedRange = alignRangeToGranularity(range, granularity);
      const directChunk = await requestCandleRange(alignedRange);
      if (directChunk.length > 0) {
        return {
          candles: directChunk,
          handledRange: alignedRange,
          dataRanges: [
            {
              from: directChunk[0].time,
              to: directChunk[directChunk.length - 1].time,
            },
          ],
        };
      }

      const windowSeconds = Math.max(1, edgeCount) * granularitySeconds;
      const requestBounds = buildRequestBounds(bounds, granularity);
      const beforeRange = clampRange(
        alignRangeToGranularity(
          {
            from: alignedRange.from - windowSeconds,
            to: alignedRange.from,
          },
          granularity
        ),
        requestBounds
      );
      const afterRange = clampRange(
        alignRangeToGranularity(
          {
            from: alignedRange.to,
            to: alignedRange.to + windowSeconds,
          },
          granularity
        ),
        requestBounds
      );
      const [beforeChunk, afterChunk] = await Promise.all([
        beforeRange.to >= beforeRange.from
          ? requestCandleRange(beforeRange)
          : Promise.resolve([]),
        afterRange.to >= afterRange.from
          ? requestCandleRange(afterRange)
          : Promise.resolve([]),
      ]);
      const bridgedCandles = mergeCandles(beforeChunk, afterChunk);
      if (bridgedCandles.length === 0) {
        return {
          candles: [],
          handledRange: alignedRange,
          dataRanges: [],
        };
      }

      const dataRanges: TimeRange[] = [];
      if (beforeChunk.length > 0) {
        dataRanges.push({
          from: beforeChunk[0].time,
          to: beforeChunk[beforeChunk.length - 1].time,
        });
      }
      if (afterChunk.length > 0) {
        dataRanges.push({
          from: afterChunk[0].time,
          to: afterChunk[afterChunk.length - 1].time,
        });
      }

      return {
        candles: bridgedCandles,
        handledRange: mergeRanges([
          alignedRange,
          {
            from: bridgedCandles[0].time,
            to: bridgedCandles[bridgedCandles.length - 1].time,
          },
        ])[0],
        dataRanges,
      };
    },
    [bounds, edgeCount, granularity, granularitySeconds, requestCandleRange]
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
      setErrorCode(null);
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
          mergeDataRanges(result.dataRanges);
        } catch (err) {
          setRequestError(err, 'Failed to load candles');
        } finally {
          inFlightKeysRef.current.delete(key);
        }
      }

      if (fetched.length > 0) {
        setCandles((prev) => mergeCandles(prev, fetched));
      }
    },
    [
      bounds,
      granularity,
      mergeDataRanges,
      mergeLoadedRange,
      requestRangeOrBridgeGap,
      setRequestError,
    ]
  );

  const replaceWithCountWindow = useCallback(
    async (count = initialCount) => {
      const hadCandles = candlesRef.current.length > 0;
      setIsInitialLoading(true);
      setError(null);
      setErrorCode(null);
      try {
        const rightEdgeSec =
          bounds.to ??
          floorToGranularity(Math.floor(Date.now() / 1000), granularitySeconds);
        const targetRange = buildTrailingRange(
          rightEdgeSec,
          count,
          granularity,
          bounds
        );
        const result = await requestRangeOrBridgeGap(targetRange);
        const nextCandles = result.candles;
        if (nextCandles.length > 0 || !hadCandles) {
          setCandles(nextCandles);
        }
        if (nextCandles.length > 0) {
          setLoadedRanges(mergeRanges([result.handledRange]));
          setDataRanges(mergeRanges(result.dataRanges));
        } else if (!hadCandles) {
          setLoadedRanges([]);
          setDataRanges([]);
        }
        return nextCandles.length;
      } catch (err) {
        setRequestError(err, 'Failed to load candles');
        return 0;
      } finally {
        setIsInitialLoading(false);
      }
    },
    [
      bounds,
      granularity,
      granularitySeconds,
      initialCount,
      requestRangeOrBridgeGap,
      setRequestError,
    ]
  );

  const replaceWithRange = useCallback(
    async (range: TimeRange, options?: { preserveOnEmpty?: boolean }) => {
      if (!isFiniteRange(range)) return 0;
      const preserveOnEmpty = options?.preserveOnEmpty ?? false;
      setIsInitialLoading(true);
      setError(null);
      setErrorCode(null);
      try {
        const requestBounds = buildRequestBounds(bounds, granularity);
        const targetRange = clampRange(
          alignRangeToGranularity(range, granularity),
          requestBounds
        );
        if (!isFiniteRange(targetRange) || targetRange.to < targetRange.from) {
          return 0;
        }
        const result = await requestRangeOrBridgeGap(targetRange);
        const nextCandles = result.candles;
        if (nextCandles.length > 0 || !preserveOnEmpty) {
          setCandles(nextCandles);
        }
        if (nextCandles.length > 0) {
          setLoadedRanges(mergeRanges([result.handledRange]));
          setDataRanges(mergeRanges(result.dataRanges));
        } else if (!preserveOnEmpty) {
          setLoadedRanges([]);
          setDataRanges([]);
        }
        return nextCandles.length;
      } catch (err) {
        setRequestError(err, 'Failed to load candles');
        return 0;
      } finally {
        setIsInitialLoading(false);
      }
    },
    [bounds, granularity, requestRangeOrBridgeGap, setRequestError]
  );

  const fetchOlder = useCallback(async () => {
    const first = candlesRef.current[0];
    if (!first) return 0;
    setLoadingOlder(true);
    setError(null);
    setErrorCode(null);
    try {
      const targetRange = clampRange(
        alignRangeToGranularity(
          {
            from: first.time - Math.max(1, edgeCount) * granularitySeconds,
            to: first.time - granularitySeconds,
          },
          granularity
        ),
        buildRequestBounds(bounds, granularity)
      );
      if (targetRange.to < targetRange.from) return 0;
      const result = await requestRangeOrBridgeGap(targetRange);
      const incoming = result.candles;
      if (incoming.length > 0) {
        setCandles((prev) => mergeCandles(prev, incoming));
        mergeLoadedRange(result.handledRange);
        mergeDataRanges(result.dataRanges);
      }
      return incoming.length;
    } catch (err) {
      setRequestError(err, 'Failed to load older candles');
      return 0;
    } finally {
      setLoadingOlder(false);
    }
  }, [
    bounds,
    edgeCount,
    granularity,
    granularitySeconds,
    mergeDataRanges,
    mergeLoadedRange,
    requestRangeOrBridgeGap,
    setRequestError,
  ]);

  const fetchNewer = useCallback(async () => {
    const last = candlesRef.current[candlesRef.current.length - 1];
    if (!last) return 0;
    setLoadingNewer(true);
    setError(null);
    setErrorCode(null);
    try {
      const targetRange = clampRange(
        alignRangeToGranularity(
          {
            from: last.time + granularitySeconds,
            to: last.time + Math.max(1, edgeCount) * granularitySeconds,
          },
          granularity
        ),
        buildRequestBounds(bounds, granularity)
      );
      if (targetRange.to < targetRange.from) return 0;
      const result = await requestRangeOrBridgeGap(targetRange);
      const incoming = result.candles;
      if (incoming.length > 0) {
        setCandles((prev) => mergeCandles(prev, incoming));
        mergeLoadedRange(result.handledRange);
        mergeDataRanges(result.dataRanges);
      }
      return incoming.length;
    } catch (err) {
      setRequestError(err, 'Failed to load newer candles');
      return 0;
    } finally {
      setLoadingNewer(false);
    }
  }, [
    bounds,
    edgeCount,
    granularity,
    granularitySeconds,
    mergeDataRanges,
    mergeLoadedRange,
    requestRangeOrBridgeGap,
    setRequestError,
  ]);

  const refreshTail = useCallback(async () => {
    const current = candlesRef.current;
    if (current.length === 0) return 0;
    const from = current[Math.max(0, current.length - edgeCount)].time;
    const to = current[current.length - 1].time;
    setIsRefreshing(true);
    setErrorCode(null);
    try {
      const incoming = await requestCandleRange({ from, to });
      if (incoming.length > 0) {
        setCandles((prev) => mergeCandles(prev, incoming));
        mergeLoadedRange({ from, to });
        mergeDataRanges([
          {
            from: incoming[0].time,
            to: incoming[incoming.length - 1].time,
          },
        ]);
      }
      return incoming.length;
    } catch (err) {
      setRequestError(err, 'Failed to refresh candles');
      return 0;
    } finally {
      setIsRefreshing(false);
    }
  }, [
    edgeCount,
    mergeDataRanges,
    mergeLoadedRange,
    requestCandleRange,
    setRequestError,
  ]);

  useEffect(() => {
    const shouldHardReset = hardResetKeyRef.current !== hardResetKey;
    const requestSeq = initialRequestSeqRef.current + 1;
    initialRequestSeqRef.current = requestSeq;
    hardResetKeyRef.current = hardResetKey;
    if (shouldHardReset) {
      candlesRef.current = [];
      loadedRangesRef.current = [];
      dataRangesRef.current = [];
      setCandles([]);
      setLoadedRanges([]);
      setDataRanges([]);
    }
    setError(null);
    setErrorCode(null);
    if (initialFocusTimeRef.current != null) {
      const granularitySeconds = GRANULARITY_SECONDS[String(granularity)] ?? 60;
      const leftCount = Math.floor(Math.max(1, initialCount) * 0.75);
      const rightCount = Math.max(1, initialCount - leftCount);
      const focusedRange = alignRangeToGranularity(
        {
          from: initialFocusTimeRef.current - leftCount * granularitySeconds,
          to: initialFocusTimeRef.current + rightCount * granularitySeconds,
        },
        granularity
      );
      const clampedFocusedRange = clampRange(
        focusedRange,
        buildRequestBounds(bounds, granularity)
      );
      setIsInitialLoading(true);
      void (async () => {
        try {
          const result = await requestRangeOrBridgeGap(clampedFocusedRange);
          if (initialRequestSeqRef.current !== requestSeq) return;
          if (result.candles.length > 0 || shouldHardReset) {
            setCandles(result.candles);
          }
          if (result.candles.length > 0) {
            setLoadedRanges(mergeRanges([result.handledRange]));
            setDataRanges(mergeRanges(result.dataRanges));
          }
        } catch (err) {
          if (initialRequestSeqRef.current !== requestSeq) return;
          setRequestError(err, 'Failed to load candles');
        } finally {
          if (initialRequestSeqRef.current === requestSeq) {
            setIsInitialLoading(false);
          }
        }
      })();
      return;
    }
    if (startTime && endTime) {
      const from = isoToSec(startTime);
      const to = isoToSec(endTime);
      if (from != null && to != null) {
        setIsInitialLoading(true);
        void (async () => {
          try {
            const requestBounds = buildRequestBounds(bounds, granularity);
            const granSec = GRANULARITY_SECONDS[String(granularity)] ?? 60;
            const requestedRange =
              initialLoadMode === 'full-range'
                ? {
                    from,
                    to,
                  }
                : {
                    // Load the most recent portion of the task range so the
                    // chart opens showing the latest data. The user can scroll
                    // left to fetch older candles on demand.
                    from: Math.max(
                      from,
                      Math.min(to, requestBounds.to) -
                        Math.max(1, edgeCount - 1) * granSec
                    ),
                    to: Math.min(to, requestBounds.to),
                  };
            const initialRange = clampRange(
              alignRangeToGranularity(requestedRange, granularity),
              requestBounds
            );
            const result = await requestRangeOrBridgeGap(initialRange);
            if (initialRequestSeqRef.current !== requestSeq) return;
            if (result.candles.length > 0 || shouldHardReset) {
              setCandles(result.candles);
            }
            if (result.candles.length > 0) {
              const initialLoadedRanges: TimeRange[] = [result.handledRange];
              setLoadedRanges(mergeRanges(initialLoadedRanges));
              setDataRanges(mergeRanges(result.dataRanges));
            }
          } catch (err) {
            if (initialRequestSeqRef.current !== requestSeq) return;
            setRequestError(err, 'Failed to load candles');
          } finally {
            if (initialRequestSeqRef.current === requestSeq) {
              setIsInitialLoading(false);
            }
          }
        })();
        return;
      }
    }
    void replaceWithCountWindow();
  }, [
    bounds,
    edgeCount,
    endTime,
    hardResetKey,
    initialCount,
    initialLoadMode,
    instrument,
    granularity,
    replaceWithCountWindow,
    requestRangeOrBridgeGap,
    setRequestError,
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
    errorCode,
    loadedRanges,
    dataRanges,
    ensureRange,
    fetchOlder,
    fetchNewer,
    refreshTail,
    replaceWithRange,
    replaceWithCountWindow,
  };
}
