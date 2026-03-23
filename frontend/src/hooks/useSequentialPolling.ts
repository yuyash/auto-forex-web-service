import { useEffect, useRef } from 'react';

interface UseSequentialPollingOptions {
  enabled: boolean;
  intervalMs: number;
  onError?: (error: unknown) => void;
}

export function useSequentialPolling(
  callback: () => Promise<unknown> | unknown,
  { enabled, intervalMs, onError }: UseSequentialPollingOptions
): void {
  const callbackRef = useRef(callback);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;

    const run = async () => {
      try {
        await callbackRef.current();
      } catch (error) {
        onErrorRef.current?.(error);
      } finally {
        if (!cancelled) {
          timeoutId = window.setTimeout(() => {
            void run();
          }, intervalMs);
        }
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
