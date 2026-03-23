/**
 * useTabConfig Hook
 *
 * Manages tab visibility, order, and persistence to localStorage.
 * Each page type (backtest/trading) has its own storage key.
 */

import { useState, useCallback, useMemo } from 'react';
import { z } from 'zod';
import {
  readStoredValue,
  removeStoredValue,
  writeStoredValue,
} from '../utils/persistentState';

export interface TabItem {
  id: string;
  label: string;
  visible: boolean;
}

interface TabConfig {
  tabs: TabItem[];
}

const STORAGE_PREFIX = 'tab_config_';
const tabConfigSchema = z.object({
  tabs: z.array(
    z.object({
      id: z.string(),
      label: z.string(),
      visible: z.boolean(),
    })
  ),
});

function loadConfig(storageKey: string, defaults: TabItem[]): TabItem[] {
  const saved = readStoredValue<TabConfig | null>(
    `${STORAGE_PREFIX}${storageKey}`,
    tabConfigSchema.nullable(),
    null
  );
  if (saved) {
    const savedMap = new Map(saved.tabs.map((t) => [t.id, t]));
    const merged: TabItem[] = [];
    for (const tab of saved.tabs) {
      const def = defaults.find((d) => d.id === tab.id);
      if (def) {
        merged.push({ ...def, visible: tab.visible });
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

function saveConfig(storageKey: string, tabs: TabItem[]) {
  const config: TabConfig = { tabs };
  writeStoredValue(`${STORAGE_PREFIX}${storageKey}`, config);
}

export function useTabConfig(storageKey: string, defaultTabs: TabItem[]) {
  const [tabs, setTabs] = useState<TabItem[]>(() =>
    loadConfig(storageKey, defaultTabs)
  );
  const mergedTabs = useMemo(() => {
    const defaultMap = new Map(defaultTabs.map((tab) => [tab.id, tab]));
    const nextTabs: TabItem[] = [];

    for (const tab of tabs) {
      const defaultTab = defaultMap.get(tab.id);
      if (defaultTab) {
        nextTabs.push({
          ...defaultTab,
          visible: tab.visible,
        });
      }
    }

    for (const defaultTab of defaultTabs) {
      if (!tabs.some((tab) => tab.id === defaultTab.id)) {
        nextTabs.push(defaultTab);
      }
    }

    return nextTabs;
  }, [defaultTabs, tabs]);

  const visibleTabs = useMemo(
    () => mergedTabs.filter((t) => t.visible),
    [mergedTabs]
  );

  const updateTabs = useCallback(
    (newTabs: TabItem[]) => {
      setTabs(newTabs);
      saveConfig(storageKey, newTabs);
    },
    [storageKey]
  );

  const resetToDefaults = useCallback(() => {
    setTabs(defaultTabs);
    removeStoredValue(`${STORAGE_PREFIX}${storageKey}`);
  }, [storageKey, defaultTabs]);

  return { tabs: mergedTabs, visibleTabs, updateTabs, resetToDefaults };
}
