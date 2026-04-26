/**
 * useColumnConfig Hook
 *
 * Manages column visibility, order, and persistence to localStorage.
 * Each table has its own storage key.
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import { z } from 'zod';
import type { Column } from '../components/common/DataTable';
import {
  readStoredValue,
  removeStoredValue,
  writeStoredValue,
} from '../utils/persistentState';

export interface ColumnItem {
  id: string;
  label: string;
  visible: boolean;
}

interface ColumnConfig {
  columns: ColumnItem[];
}

const STORAGE_PREFIX = 'col_config_';
const columnConfigSchema = z.object({
  columns: z.array(
    z.object({
      id: z.string(),
      label: z.string(),
      visible: z.boolean(),
    })
  ),
});

function loadConfig(storageKey: string, defaults: ColumnItem[]): ColumnItem[] {
  const saved = readStoredValue<ColumnConfig | null>(
    `${STORAGE_PREFIX}${storageKey}`,
    columnConfigSchema.nullable(),
    null
  );
  if (saved) {
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
  return defaults;
}

function saveConfig(storageKey: string, columns: ColumnItem[]) {
  writeStoredValue(`${STORAGE_PREFIX}${storageKey}`, { columns });
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

  useEffect(() => {
    setColumns(loadConfig(storageKey, defaultColumns));
    // Reload only when the table identity changes. Several callers build
    // defaultColumns inline, so including it would reset user edits every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey]);

  const updateColumns = useCallback(
    (newColumns: ColumnItem[]) => {
      setColumns(newColumns);
      saveConfig(storageKey, newColumns);
    },
    [storageKey]
  );

  const resetToDefaults = useCallback(() => {
    setColumns(defaultColumns);
    removeStoredValue(`${STORAGE_PREFIX}${storageKey}`);
  }, [storageKey, defaultColumns]);

  const visibleColumns = useMemo(
    () => columns.filter((c) => c.visible),
    [columns]
  );

  return { columns, visibleColumns, updateColumns, resetToDefaults };
}
