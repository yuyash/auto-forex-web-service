import { useCallback, useState } from 'react';
import type React from 'react';

import {
  readRawStoredValue,
  writeRawStoredValue,
} from '../../../utils/persistentState';

export type PositionViewMode = 'all' | 'byDirection' | 'byStatus';

const VIEW_MODE_STORAGE_KEY = 'positions_view_mode';

function loadPositionViewMode(): PositionViewMode {
  const value = readRawStoredValue(VIEW_MODE_STORAGE_KEY);
  if (value === 'all' || value === 'byDirection' || value === 'byStatus') {
    return value;
  }
  return 'all';
}

export function useTaskPositionViewMode() {
  const [viewMode, setViewMode] =
    useState<PositionViewMode>(loadPositionViewMode);

  const handleViewModeChange = useCallback(
    (_: React.MouseEvent<HTMLElement>, nextMode: PositionViewMode | null) => {
      if (!nextMode) {
        return;
      }
      setViewMode(nextMode);
      writeRawStoredValue(VIEW_MODE_STORAGE_KEY, nextMode);
    },
    []
  );

  return { viewMode, handleViewModeChange };
}
