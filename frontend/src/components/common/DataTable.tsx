import React, { useState, useMemo } from 'react';
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
}

type Order = 'asc' | 'desc';

/**
 * DataTable Component
 *
 * Reusable table with sorting, filtering, pagination, loading states,
 * and real-time update support.
 *
 * Requirements: 11.7, 11.15
 *
 * @param columns - Column definitions
 * @param data - Table data
 * @param rowsPerPageOptions - Options for rows per page
 * @param defaultRowsPerPage - Default rows per page
 * @param onRowClick - Callback when row is clicked
 * @param emptyMessage - Message to show when no data
 * @param stickyHeader - Enable sticky header
 * @param isLoading - Loading state
 * @param error - Error object if data failed to load
 * @param enableRealTimeUpdates - Enable real-time updates
 * @param onRefresh - Callback to refresh data
 * @param ariaLabel - Accessibility label for the table
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
}: DataTableProps<T>): React.ReactElement {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(defaultRowsPerPage);
  const [orderBy, setOrderBy] = useState<keyof T | string>('');
  const [order, setOrder] = useState<Order>('asc');
  const [filters, setFilters] = useState<Record<string, string>>({});

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
      }, 5000); // Refresh every 5 seconds

      return () => clearInterval(interval);
    }
  }, [enableRealTimeUpdates, onRefresh]);

  // Render loading skeleton
  if (isLoading && data.length === 0) {
    return (
      <Paper sx={{ width: '100%', overflow: 'hidden' }}>
        <TableContainer sx={{ maxHeight: 600 }}>
          <Table stickyHeader={stickyHeader}>
            <TableHead>
              <TableRow>
                {columns.map((column) => (
                  <TableCell
                    key={String(column.id)}
                    align={column.align || 'left'}
                    style={{ minWidth: column.minWidth }}
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
      <TableContainer sx={{ maxHeight: 600 }}>
        <Table stickyHeader={stickyHeader}>
          <TableHead>
            <TableRow>
              {columns.map((column) => (
                <TableCell
                  key={String(column.id)}
                  align={column.align || 'left'}
                  style={{ minWidth: column.minWidth }}
                >
                  {column.sortable ? (
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
                </TableCell>
              ))}
            </TableRow>
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
