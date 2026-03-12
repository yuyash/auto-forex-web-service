/**
 * Utility for building column-config-aware copy handlers.
 *
 * Given the visible columns (already filtered & ordered by useColumnConfig)
 * and a map of column-id → plain-text extractor, produces the headers array
 * and a row formatter that respect the current column order and visibility.
 */

import type { Column } from '../components/common/DataTable';

/**
 * Map from column id to a function that extracts a plain-text cell value.
 */
export type CopyValueExtractors<T> = Record<string, (row: T) => string>;

/**
 * Build headers and a row formatter aligned with the visible column order.
 *
 * @param visibleColumns - columns after applyColumnConfig (ordered + filtered)
 * @param extractors     - column id → plain-text value extractor
 * @returns { headers, formatRow } ready to pass to copySelectedRows
 */
export function buildCopyHandler<T>(
  visibleColumns: Column<T>[],
  extractors: CopyValueExtractors<T>,
  dataMap: Map<string, T>
): {
  headers: string[];
  formatRow: (id: string) => string;
} {
  const applicableCols = visibleColumns.filter(
    (col) => extractors[String(col.id)] != null
  );
  const headers = applicableCols.map((col) => col.label);
  const formatRow = (id: string): string => {
    const row = dataMap.get(id);
    if (!row) return '';
    return applicableCols
      .map((col) => {
        const extractor = extractors[String(col.id)];
        return extractor ? extractor(row) : '-';
      })
      .join('\t');
  };
  return { headers, formatRow };
}
