/**
 * useMetricsOrder Hook
 *
 * Persists the display order of metrics charts in localStorage.
 * Returns the ordered list of metric keys and functions to move items.
 */

import { useState, useCallback, useMemo } from 'react';
import { z } from 'zod';
import {
  readStoredValue,
  removeStoredValue,
  writeStoredValue,
} from '../utils/persistentState';

const STORAGE_KEY = 'metrics_chart_order';
const orderSchema = z.array(z.string()).nullable();

export function useMetricsOrder(availableKeys: string[]) {
  const [savedOrder, setSavedOrder] = useState<string[] | null>(() =>
    readStoredValue(STORAGE_KEY, orderSchema, null)
  );

  // Merge saved order with available keys: keep saved order for keys that
  // exist, then append any new keys not in the saved order.
  const orderedKeys = useMemo(() => {
    if (!savedOrder) return availableKeys;
    const available = new Set(availableKeys);
    const ordered: string[] = [];
    for (const key of savedOrder) {
      if (available.has(key)) {
        ordered.push(key);
        available.delete(key);
      }
    }
    // Append any keys not in saved order (new metrics)
    for (const key of availableKeys) {
      if (available.has(key)) ordered.push(key);
    }
    return ordered;
  }, [savedOrder, availableKeys]);

  const persist = useCallback((keys: string[]) => {
    setSavedOrder(keys);
    writeStoredValue(STORAGE_KEY, keys);
  }, []);

  const moveUp = useCallback(
    (key: string) => {
      const idx = orderedKeys.indexOf(key);
      if (idx <= 0) return;
      const next = [...orderedKeys];
      [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
      persist(next);
    },
    [orderedKeys, persist]
  );

  const moveDown = useCallback(
    (key: string) => {
      const idx = orderedKeys.indexOf(key);
      if (idx < 0 || idx >= orderedKeys.length - 1) return;
      const next = [...orderedKeys];
      [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
      persist(next);
    },
    [orderedKeys, persist]
  );

  const resetOrder = useCallback(() => {
    setSavedOrder(null);
    removeStoredValue(STORAGE_KEY);
  }, []);

  return { orderedKeys, moveUp, moveDown, resetOrder };
}
