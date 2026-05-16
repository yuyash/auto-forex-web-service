import { useCallback, useState } from 'react';
import { z } from 'zod';
import { readStoredValue, writeStoredValue } from '../utils/persistentState';
import type { GridColumnCount } from '../utils/gridColumns';

const STORAGE_PREFIX = 'grid-column-count:';
const gridColumnCountSchema = z.union([
  z.literal(1),
  z.literal(2),
  z.literal(3),
  z.literal(4),
]);

export function useGridColumnCount(
  storageKey: string,
  defaultValue: GridColumnCount
) {
  const fullStorageKey = `${STORAGE_PREFIX}${storageKey}`;
  const [columnCount, setColumnCount] = useState<GridColumnCount>(() =>
    readStoredValue(fullStorageKey, gridColumnCountSchema, defaultValue)
  );

  const updateColumnCount = useCallback(
    (nextColumnCount: GridColumnCount) => {
      setColumnCount(nextColumnCount);
      writeStoredValue(fullStorageKey, nextColumnCount);
    },
    [fullStorageKey]
  );

  return [columnCount, updateColumnCount] as const;
}
