// Virtualized table component for efficient rendering of large datasets
import React from 'react';
import { List, type RowComponentProps } from 'react-window';
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Paper,
} from '@mui/material';

export interface VirtualizedTableColumn<T> {
  id: string;
  label: string;
  width?: number | string;
  align?: 'left' | 'center' | 'right';
  render?: (item: T, index: number) => React.ReactNode;
  getValue?: (item: T) => string | number;
}

interface VirtualizedTableProps<T> {
  data: T[];
  columns: VirtualizedTableColumn<T>[];
  rowHeight?: number;
  height: number;
  emptyMessage?: string;
  overscanCount?: number;
  onRowClick?: (item: T, index: number) => void;
}

export function VirtualizedTable<T>({
  data,
  columns,
  rowHeight = 52,
  height,
  emptyMessage = 'No data to display',
  overscanCount = 5,
  onRowClick,
}: VirtualizedTableProps<T>) {
  const Row = React.useCallback(
    ({ index, style }: RowComponentProps) => {
      const item = data[index];
      return (
        <TableRow
          hover={!!onRowClick}
          onClick={() => onRowClick?.(item, index)}
          sx={{
            ...style,
            display: 'flex',
            cursor: onRowClick ? 'pointer' : 'default',
            '&:hover': onRowClick
              ? {
                  backgroundColor: 'action.hover',
                }
              : {},
          }}
        >
          {columns.map((column) => (
            <TableCell
              key={column.id}
              align={column.align || 'left'}
              sx={{
                width: column.width || 'auto',
                flex: column.width ? 'none' : 1,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {column.render
                ? column.render(item, index)
                : column.getValue
                  ? column.getValue(item)
                  : ''}
            </TableCell>
          ))}
        </TableRow>
      );
    },
    [data, columns, onRowClick]
  );

  if (data.length === 0) {
    return (
      <Paper>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height,
            width: '100%',
          }}
        >
          <Typography variant="body2" color="text.secondary">
            {emptyMessage}
          </Typography>
        </Box>
      </Paper>
    );
  }

  return (
    <TableContainer component={Paper}>
      <Table stickyHeader>
        <TableHead>
          <TableRow sx={{ display: 'flex' }}>
            {columns.map((column) => (
              <TableCell
                key={column.id}
                align={column.align || 'left'}
                sx={{
                  width: column.width || 'auto',
                  flex: column.width ? 'none' : 1,
                  fontWeight: 600,
                  backgroundColor: 'background.paper',
                }}
              >
                {column.label}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
      </Table>
      <TableBody component="div">
        <List
          defaultHeight={height - 56} // Subtract header height
          rowCount={data.length}
          rowHeight={rowHeight}
          overscanCount={overscanCount}
          rowComponent={Row}
          rowProps={{}}
        />
      </TableBody>
    </TableContainer>
  );
}

export default VirtualizedTable;
