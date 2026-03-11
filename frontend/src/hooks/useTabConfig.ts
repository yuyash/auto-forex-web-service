/**
 * useTabConfig Hook
 *
 * Manages tab visibility, order, and persistence to localStorage.
 * Each page type (backtest/trading) has its own storage key.
 */

import { useState, useCallback, useMemo } from 'react';

export interface TabItem {
  id: string;
  label: string;
  visible: boolean;
}

interface TabConfig {
  tabs: TabItem[];
}

const STORAGE_PREFIX = 'tab_config_';

function loadConfig(storageKey: string, defaults: TabItem[]): TabItem[] {
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}${storageKey}`);
    if (raw) {
      const saved: TabConfig = JSON.parse(raw);
      // Merge saved config with defaults to handle new tabs added after save
      const savedMap = new Map(saved.tabs.map((t) => [t.id, t]));
      const merged: TabItem[] = [];
      // First, add saved tabs in their saved order
      for (const tab of saved.tabs) {
        const def = defaults.find((d) => d.id === tab.id);
        if (def) {
          merged.push({ ...def, visible: tab.visible });
        }
      }
      // Then, add any new default tabs not in saved config
      for (const def of defaults) {
        if (!savedMap.has(def.id)) {
          merged.push(def);
        }
      }
      return merged;
    }
  } catch {
    // ignore parse errors
  }
  return defaults;
}

function saveConfig(storageKey: string, tabs: TabItem[]) {
  const config: TabConfig = { tabs };
  localStorage.setItem(
    `${STORAGE_PREFIX}${storageKey}`,
    JSON.stringify(config)
  );
}

export function useTabConfig(storageKey: string, defaultTabs: TabItem[]) {
  const [tabs, setTabs] = useState<TabItem[]>(() =>
    loadConfig(storageKey, defaultTabs)
  );

  const visibleTabs = useMemo(() => tabs.filter((t) => t.visible), [tabs]);

  const updateTabs = useCallback(
    (newTabs: TabItem[]) => {
      setTabs(newTabs);
      saveConfig(storageKey, newTabs);
    },
    [storageKey]
  );

  const resetToDefaults = useCallback(() => {
    setTabs(defaultTabs);
    localStorage.removeItem(`${STORAGE_PREFIX}${storageKey}`);
  }, [storageKey, defaultTabs]);

  return { tabs, visibleTabs, updateTabs, resetToDefaults };
}
