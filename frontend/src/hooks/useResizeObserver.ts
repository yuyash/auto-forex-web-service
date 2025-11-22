import { useEffect, useState, type RefObject } from 'react';

/**
 * Hook to observe element size changes using ResizeObserver
 * Returns the current width and height of the observed element
 */
export function useResizeObserver(ref: RefObject<HTMLElement | null>) {
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    // Check if ResizeObserver is available (not available in some test environments)
    if (typeof ResizeObserver === 'undefined') {
      // Fallback: just get the initial size
      const { width, height } = element.getBoundingClientRect();
      setSize({ width, height });
      return;
    }

    const observer = new ResizeObserver((entries) => {
      if (entries[0]) {
        const { width, height } = entries[0].contentRect;
        setSize({ width, height });
      }
    });

    observer.observe(element);

    // Set initial size
    const { width, height } = element.getBoundingClientRect();
    setSize({ width, height });

    return () => {
      observer.disconnect();
    };
  }, [ref]);

  return size;
}
