import { useCallback, useEffect, useMemo, useState } from 'react';
import { z } from 'zod';
import {
  readStoredValue,
  removeStoredValue,
  writeStoredValue,
} from '../utils/persistentState';

export interface OrderedItem {
  id: string;
}

const STORAGE_PREFIX = 'item_order_';
const itemOrderSchema = z.array(z.string());

function storageKeyFor(key: string) {
  return `${STORAGE_PREFIX}${key}`;
}

function loadOrder(storageKey: string): string[] {
  return readStoredValue(storageKeyFor(storageKey), itemOrderSchema, []);
}

export function applyItemOrder<T extends OrderedItem>(
  items: T[],
  order: string[]
): T[] {
  if (order.length === 0) return items;

  const itemMap = new Map(items.map((item) => [item.id, item]));
  const orderedItems: T[] = [];
  const orderedIds = new Set<string>();
  for (const id of order) {
    const item = itemMap.get(id);
    if (!item || orderedIds.has(id)) continue;
    orderedItems.push(item);
    orderedIds.add(id);
  }
  const newItems = items.filter((item) => !orderedIds.has(item.id));
  return [...orderedItems, ...newItems];
}

export function useItemOrder<T extends OrderedItem>(
  storageKey: string,
  items: T[]
) {
  const [order, setOrder] = useState<string[]>(() => loadOrder(storageKey));

  useEffect(() => {
    setOrder(loadOrder(storageKey));
  }, [storageKey]);

  const orderedItems = useMemo(
    () => applyItemOrder(items, order),
    [items, order]
  );

  const updateOrder = useCallback(
    (ids: string[]) => {
      setOrder(ids);
      writeStoredValue(storageKeyFor(storageKey), ids);
    },
    [storageKey]
  );

  const resetOrder = useCallback(() => {
    setOrder([]);
    removeStoredValue(storageKeyFor(storageKey));
  }, [storageKey]);

  return {
    order,
    orderedItems,
    updateOrder,
    resetOrder,
  };
}
