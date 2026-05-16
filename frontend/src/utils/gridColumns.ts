export type GridColumnCount = 1 | 2 | 3 | 4;

export const GRID_COLUMN_COUNTS = [1, 2, 3, 4] as const;

export function isGridColumnCount(value: unknown): value is GridColumnCount {
  return (
    typeof value === 'number' &&
    GRID_COLUMN_COUNTS.includes(value as GridColumnCount)
  );
}

export function normalizeGridColumnCount(
  value: unknown,
  fallback: GridColumnCount
): GridColumnCount {
  const numericValue =
    typeof value === 'string' || typeof value === 'number'
      ? Number(value)
      : Number.NaN;
  return isGridColumnCount(numericValue) ? numericValue : fallback;
}

function repeatColumns(count: GridColumnCount): string {
  return `repeat(${count}, minmax(0, 1fr))`;
}

export function responsiveGridTemplateColumns(maxColumns: GridColumnCount) {
  if (maxColumns === 1) {
    return { xs: '1fr' };
  }
  if (maxColumns === 2) {
    return { xs: '1fr', md: repeatColumns(2) };
  }
  if (maxColumns === 3) {
    return {
      xs: '1fr',
      sm: repeatColumns(2),
      lg: repeatColumns(3),
    };
  }
  return {
    xs: '1fr',
    sm: repeatColumns(2),
    lg: repeatColumns(3),
    xl: repeatColumns(4),
  };
}

export function responsiveChartGridSize(maxColumns: GridColumnCount) {
  if (maxColumns === 1) {
    return { xs: 12 };
  }
  if (maxColumns === 2) {
    return { xs: 12, md: 6 };
  }
  if (maxColumns === 3) {
    return { xs: 12, md: 6, lg: 4 };
  }
  return { xs: 12, sm: 6, lg: 4, xl: 3 };
}
