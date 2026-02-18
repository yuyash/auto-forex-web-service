import React, { useState, useMemo, useCallback, useRef } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  TableSortLabel,
  Paper,
  TextField,
  Box,
  Typography,
  CircularProgress,
  Alert,
  Skeleton,
} from '@mui/material';

export interface Column<T> {
  id: keyof T | string;
  label: string;
  sortable?: boolean;
  filterable?: boolean;
  render?: (row: T) => React.ReactNode;
  align?: 'left' | 'center' | 'right';
  minWidth?: number;
  width?: number;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  rowsPerPageOptions?: number[];
  defaultRowsPerPage?: number;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
  stickyHeader?: boolean;
  isLoading?: boolean;
  error?: Error | null;
  enableRealTimeUpdates?: boolean;
  onRefresh?: () => void;
  ariaLabel?: string;
  resizableColumns?: boolean;
  /** Unique key for persisting column widths to localStorage */
  storageKey?: string;
  /** Max height for the table container. Defaults to viewport-based calc. */
  tableMaxHeight?: number | string;
}

type Order = 'asc' | 'desc';

/**
 * DataTable Component
 *
 * Reusable table with sorting, filtering, pagination, loading states,
 * column resizing, and real-time update support.
 *
 */
function DataTable<T extends object>({
  columns,
  data,
  rowsPerPageOptions = [10, 25, 50, 100],
  defaultRowsPerPage = 10,
  onRowClick,
  emptyMessage = 'No data available',
  stickyHeader = true,
  isLoading = false,
  error = null,
  enableRealTimeUpdates = false,
  onRefresh,
  ariaLabel,
  resizableColumns = true,
  storageKey,
  tableMaxHeight,
}: DataTableProps<T>): React.ReactElement {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(defaultRowsPerPage);
  const [orderBy, setOrderBy] = useState<keyof T | string>('');
  const [order, setOrder] = useState<Order>('asc');
  const [filters, setFilters] = useState<Record<string, string>>({});

  // Column widths state for resizing
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>(
    () => {
      // Restore from localStorage if storageKey is provided
      if (storageKey) {
        try {
          const saved = localStorage.getItem(`datatable-widths-${storageKey}`);
          if (saved) return JSON.parse(saved) as Record<string, number>;
        } catch {
          // ignore parse errors
        }
      }
      const widths: Record<string, number> = {};
      columns.forEach((col) => {
        if (col.width) {
          widths[String(col.id)] = col.width;
        }
      });
      return widths;
    }
  );

  const resizingRef = useRef<{
    columnId: string;
    startX: number;
    startWidth: number;
  } | null>(null);

  const handleResizeStart = useCallback(
    (e: React.MouseEvent, columnId: string, currentWidth: number) => {
      e.preventDefault();
      e.stopPropagation();
      resizingRef.current = {
        columnId,
        startX: e.clientX,
        startWidth: currentWidth,
      };

      const handleMouseMove = (moveEvent: MouseEvent) => {
        if (!resizingRef.current) return;
        const diff = moveEvent.clientX - resizingRef.current.startX;
        const newWidth = Math.max(40, resizingRef.current.startWidth + diff);
        setColumnWidths((prev) => ({
          ...prev,
          [resizingRef.current!.columnId]: newWidth,
        }));
      };

      const handleMouseUp = () => {
        resizingRef.current = null;
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        // Persist widths to localStorage
        if (storageKey) {
          setColumnWidths((current) => {
            try {
              localStorage.setItem(
                `datatable-widths-${storageKey}`,
                JSON.stringify(current)
              );
            } catch {
              // ignore quota errors
            }
            return current;
          });
        }
      };

      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    },
    [storageKey]
  );

  const handleRequestSort = (property: keyof T | string) => {
    const isAsc = orderBy === property && order === 'asc';
    setOrder(isAsc ? 'desc' : 'asc');
    setOrderBy(property);
  };

  const handleChangePage = (_event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleFilterChange = (columnId: string, value: string) => {
    setFilters((prev) => ({ ...prev, [columnId]: value }));
    setPage(0);
  };

  const getNestedValue = useMemo(
    () =>
      (obj: T, path: string): unknown => {
        return path.split('.').reduce((acc: unknown, part: string) => {
          if (acc && typeof acc === 'object' && part in (acc as object)) {
            return (acc as Record<string, unknown>)[part];
          }
          return undefined;
        }, obj as unknown);
      },
    []
  );

  const filteredData = useMemo(() => {
    return data.filter((row) => {
      return Object.entries(filters).every(([columnId, filterValue]) => {
        if (!filterValue) return true;
        const cellValue = getNestedValue(row, columnId);
        return String(cellValue)
          .toLowerCase()
          .includes(filterValue.toLowerCase());
      });
    });
  }, [data, filters, getNestedValue]);

  const sortedData = useMemo(() => {
    if (!orderBy) return filteredData;

    return [...filteredData].sort((a, b) => {
      const aValue = getNestedValue(a, orderBy as string);
      const bValue = getNestedValue(b, orderBy as string);

      if (aValue === undefined || aValue === null) return 1;
      if (bValue === undefined || bValue === null) return -1;

      let comparison = 0;
      if (aValue < bValue) {
        comparison = -1;
      } else if (aValue > bValue) {
        comparison = 1;
      }

      return order === 'asc' ? comparison : -comparison;
    });
  }, [filteredData, orderBy, order, getNestedValue]);

  const paginatedData = useMemo(() => {
    const startIndex = page * rowsPerPage;
    return sortedData.slice(startIndex, startIndex + rowsPerPage);
  }, [sortedData, page, rowsPerPage]);

  // Real-time updates effect
  React.useEffect(() => {
    if (enableRealTimeUpdates && onRefresh) {
      const interval = setInterval(() => {
        onRefresh();
      }, 5000);

      return () => clearInterval(interval);
    }
  }, [enableRealTimeUpdates, onRefresh]);

  const getColumnStyle = (column: Column<T>): React.CSSProperties => {
    const colId = String(column.id);
    const w = columnWidths[colId] ?? column.width;
    return {
      width: w ? `${w}px` : undefined,
      minWidth: column.minWidth ?? 40,
      maxWidth: w ? `${w}px` : undefined,
      position: 'relative',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
    };
  };

  const resizeHandle = (columnId: string, column: Column<T>) => {
    if (!resizableColumns) return null;
    const w = columnWidths[columnId] ?? column.width ?? column.minWidth ?? 100;
    return (
      <Box
        onMouseDown={(e) => handleResizeStart(e, columnId, w)}
        sx={{
          position: 'absolute',
          right: 0,
          top: 0,
          bottom: 0,
          width: 4,
          cursor: 'col-resize',
          '&:hover': { backgroundColor: 'primary.main', opacity: 0.4 },
        }}
      />
    );
  };

  // Render loading skeleton
  if (isLoading && data.length === 0) {
    return (
      <Paper sx={{ width: '100%', overflow: 'hidden' }}>
        <TableContainer
          sx={{ maxHeight: tableMaxHeight ?? 'calc(100vh - 640px)' }}
        >
          <Table
            size="small"
            stickyHeader={stickyHeader}
            sx={{ tableLayout: 'fixed' }}
          >
            <TableHead>
              <TableRow>
                {columns.map((column) => (
                  <TableCell
                    key={String(column.id)}
                    align={column.align || 'left'}
                    style={getColumnStyle(column)}
                  >
                    {column.label}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {[...Array(5)].map((_, index) => (
                <TableRow key={index}>
                  {columns.map((column) => (
                    <TableCell key={String(column.id)}>
                      <Skeleton variant="text" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    );
  }

  // Render error state
  if (error) {
    return (
      <Paper sx={{ width: '100%', p: 2 }}>
        <Alert severity="error">
          <Typography variant="body2">
            {error.message || 'Failed to load data. Please try again.'}
          </Typography>
        </Alert>
      </Paper>
    );
  }

  return (
    <Paper
      sx={{ width: '100%', overflow: 'hidden' }}
      role="region"
      aria-label={ariaLabel || 'Data table'}
    >
      <TableContainer
        sx={{ maxHeight: tableMaxHeight ?? 'calc(100vh - 640px)' }}
      >
        <Table
          size="small"
          stickyHeader={stickyHeader}
          sx={{ tableLayout: 'fixed' }}
        >
          <TableHead>
            <TableRow>
              {columns.map((column) => {
                const colId = String(column.id);
                return (
                  <TableCell
                    key={colId}
                    align={column.align || 'left'}
                    style={getColumnStyle(column)}
                    sx={{ position: 'relative' }}
                  >
                    {column.sortable !== false ? (
                      <TableSortLabel
                        active={orderBy === column.id}
                        direction={orderBy === column.id ? order : 'asc'}
                        onClick={() => handleRequestSort(column.id)}
                      >
                        {column.label}
                      </TableSortLabel>
                    ) : (
                      column.label
                    )}
                    {resizeHandle(colId, column)}
                  </TableCell>
                );
              })}
            </TableRow>
            {columns.some((col) => col.filterable) && (
              <TableRow>
                {columns.map((column) => (
                  <TableCell
                    key={`filter-${String(column.id)}`}
                    align={column.align || 'left'}
                  >
                    {column.filterable && (
                      <TextField
                        size="small"
                        placeholder={`Filter ${column.label}`}
                        value={filters[String(column.id)] || ''}
                        onChange={(e) =>
                          handleFilterChange(String(column.id), e.target.value)
                        }
                        fullWidth
                        variant="outlined"
                      />
                    )}
                  </TableCell>
                ))}
              </TableRow>
            )}
          </TableHead>
          <TableBody>
            {paginatedData.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length} align="center">
                  <Box py={3}>
                    <Typography variant="body2" color="text.secondary">
                      {emptyMessage}
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              paginatedData.map((row, index) => (
                <TableRow
                  hover
                  key={index}
                  onClick={() => onRowClick?.(row)}
                  sx={{ cursor: onRowClick ? 'pointer' : 'default' }}
                >
                  {columns.map((column) => (
                    <TableCell
                      key={String(column.id)}
                      align={column.align || 'left'}
                      style={getColumnStyle(column)}
                    >
                      {column.render
                        ? column.render(row)
                        : String(getNestedValue(row, String(column.id)) ?? '')}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <TablePagination
          rowsPerPageOptions={rowsPerPageOptions}
          component="div"
          count={sortedData.length}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
        {isLoading && (
          <Box sx={{ display: 'flex', alignItems: 'center', pr: 2 }}>
            <CircularProgress size={20} sx={{ mr: 1 }} />
            <Typography variant="caption" color="text.secondary">
              Updating...
            </Typography>
          </Box>
        )}
      </Box>
    </Paper>
  );
}

export default DataTable;
