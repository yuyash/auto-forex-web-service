/**
 * useTableRowSelection Hook
 *
 * Reusable hook for table row selection, copy-to-clipboard,
 * select-all-on-page, and reset functionality.
 */

import { useState, useCallback } from 'react';

export interface UseTableRowSelectionResult {
  selectedRowIds: Set<string>;
  toggleRowSelection: (id: string) => void;
  selectAllOnPage: (pageRowIds: string[]) => void;
  resetSelection: () => void;
  isAllPageSelected: (pageRowIds: string[]) => boolean;
  isIndeterminate: (pageRowIds: string[]) => boolean;
  copySelectedRows: (
    headers: string[],
    formatRow: (id: string) => string
  ) => void;
}

export function useTableRowSelection(): UseTableRowSelectionResult {
  const [selectedRowIds, setSelectedRowIds] = useState<Set<string>>(new Set());

  const toggleRowSelection = useCallback((id: string) => {
    setSelectedRowIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllOnPage = useCallback((pageRowIds: string[]) => {
    setSelectedRowIds((prev) => {
      const next = new Set(prev);
      for (const id of pageRowIds) next.add(id);
      return next;
    });
  }, []);

  const resetSelection = useCallback(() => {
    setSelectedRowIds(new Set());
  }, []);

  const isAllPageSelected = useCallback(
    (pageRowIds: string[]) =>
      pageRowIds.length > 0 && pageRowIds.every((id) => selectedRowIds.has(id)),
    [selectedRowIds]
  );

  const isIndeterminate = useCallback(
    (pageRowIds: string[]) =>
      !isAllPageSelected(pageRowIds) &&
      pageRowIds.some((id) => selectedRowIds.has(id)),
    [selectedRowIds, isAllPageSelected]
  );

  const copySelectedRows = useCallback(
    (headers: string[], formatRow: (id: string) => string) => {
      const header = headers.join('\t');
      const rows = [...selectedRowIds].map(formatRow).filter(Boolean);
      if (rows.length > 0) {
        navigator.clipboard.writeText([header, ...rows].join('\n'));
      }
    },
    [selectedRowIds]
  );

  return {
    selectedRowIds,
    toggleRowSelection,
    selectAllOnPage,
    resetSelection,
    isAllPageSelected,
    isIndeterminate,
    copySelectedRows,
  };
}
