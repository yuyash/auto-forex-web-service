import { useEffect, useRef, useCallback } from 'react';

const ACTIVITY_EVENTS: (keyof DocumentEventMap)[] = [
  'mousedown',
  'keydown',
  'scroll',
  'touchstart',
];

/**
 * Calls `onTimeout` after `timeoutMinutes` of user inactivity.
 * Pass 0 to disable.
 */
export function useIdleTimeout(timeoutMinutes: number, onTimeout: () => void) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onTimeoutRef = useRef(onTimeout);

  useEffect(() => {
    onTimeoutRef.current = onTimeout;
  }, [onTimeout]);

  const resetTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    if (timeoutMinutes > 0) {
      timerRef.current = setTimeout(
        () => onTimeoutRef.current(),
        timeoutMinutes * 60 * 1000
      );
    }
  }, [timeoutMinutes]);

  useEffect(() => {
    if (timeoutMinutes <= 0) return;

    resetTimer();

    const handler = () => resetTimer();
    for (const event of ACTIVITY_EVENTS) {
      document.addEventListener(event, handler, { passive: true });
    }

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      for (const event of ACTIVITY_EVENTS) {
        document.removeEventListener(event, handler);
      }
    };
  }, [timeoutMinutes, resetTimer]);
}
