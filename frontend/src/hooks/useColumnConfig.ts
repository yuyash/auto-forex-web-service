/**
 * useColumnConfig Hook
 *
 * Manages column visibility, order, and persistence to localStorage.
 * Each table has its own storage key.
 */

import { useState, useCallback, useMemo } from 'react';
import type { Column } from '../components/common/DataTable';

export interface ColumnItem {
  id: string;
  label: string;
  visible: boolean;
}

interface ColumnConfig {
  columns: ColumnItem[];
}

const STORAGE_PREFIX = 'col_config_';

function loadConfig(storageKey: string, defaults: ColumnItem[]): ColumnItem[] {
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}${storageKey}`);
    if (raw) {
      const saved: ColumnConfig = JSON.parse(raw);
      const savedMap = new Map(saved.columns.map((c) => [c.id, c]));
      const merged: ColumnItem[] = [];
      for (const col of saved.columns) {
        if (defaults.find((d) => d.id === col.id)) {
          merged.push(col);
        }
      }
      for (const def of defaults) {
        if (!savedMap.has(def.id)) {
          merged.push(def);
        }
      }
      return merged;
    }
  } catch {
    // ignore
  }
  return defaults;
}

function saveConfig(storageKey: string, columns: ColumnItem[]) {
  localStorage.setItem(
    `${STORAGE_PREFIX}${storageKey}`,
    JSON.stringify({ columns })
  );
}

/**
 * Build default ColumnItem[] from a Column<T>[] definition.
 */
export function columnsToDefaults<T>(columns: Column<T>[]): ColumnItem[] {
  return columns.map((c) => ({
    id: String(c.id),
    label: c.label,
    visible: true,
  }));
}

/**
 * Apply column config (visibility + order) to the original columns array.
 */
export function applyColumnConfig<T>(
  allColumns: Column<T>[],
  config: ColumnItem[]
): Column<T>[] {
  const colMap = new Map(allColumns.map((c) => [String(c.id), c]));
  const result: Column<T>[] = [];
  for (const item of config) {
    if (item.visible) {
      const col = colMap.get(item.id);
      if (col) result.push(col);
    }
  }
  return result;
}

export function useColumnConfig(
  storageKey: string,
  defaultColumns: ColumnItem[]
) {
  const [columns, setColumns] = useState<ColumnItem[]>(() =>
    loadConfig(storageKey, defaultColumns)
  );

  const updateColumns = useCallback(
    (newColumns: ColumnItem[]) => {
      setColumns(newColumns);
      saveConfig(storageKey, newColumns);
    },
    [storageKey]
  );

  const resetToDefaults = useCallback(() => {
    setColumns(defaultColumns);
    localStorage.removeItem(`${STORAGE_PREFIX}${storageKey}`);
  }, [storageKey, defaultColumns]);

  const visibleColumns = useMemo(
    () => columns.filter((c) => c.visible),
    [columns]
  );

  return { columns, visibleColumns, updateColumns, resetToDefaults };
}
