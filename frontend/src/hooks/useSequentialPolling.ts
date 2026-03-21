import { useEffect, useRef } from 'react';

interface UseSequentialPollingOptions {
  enabled: boolean;
  intervalMs: number;
}

export function useSequentialPolling(
  callback: () => Promise<unknown> | unknown,
  { enabled, intervalMs }: UseSequentialPollingOptions
): void {
  const callbackRef = useRef(callback);

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;

    const run = async () => {
      await callbackRef.current();

      if (!cancelled) {
        timeoutId = window.setTimeout(() => {
          void run();
        }, intervalMs);
      }
    };

    timeoutId = window.setTimeout(() => {
      void run();
    }, intervalMs);

    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [enabled, intervalMs]);
}
