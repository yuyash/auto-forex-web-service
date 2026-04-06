/**
 * useMetricsOrder Hook
 *
 * Persists the display order of metrics charts in localStorage.
 * Returns the ordered list of metric keys and a function to move items.
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

  /** Move sourceKey to the position currently occupied by targetKey. */
  const moveItem = useCallback(
    (sourceKey: string, targetKey: string) => {
      const fromIdx = orderedKeys.indexOf(sourceKey);
      const toIdx = orderedKeys.indexOf(targetKey);
      if (fromIdx < 0 || toIdx < 0 || fromIdx === toIdx) return;
      const next = [...orderedKeys];
      next.splice(fromIdx, 1);
      next.splice(toIdx, 0, sourceKey);
      persist(next);
    },
    [orderedKeys, persist]
  );

  const resetOrder = useCallback(() => {
    setSavedOrder(null);
    removeStoredValue(STORAGE_KEY);
  }, []);

  return { orderedKeys, moveItem, resetOrder };
}
