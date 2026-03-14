import type { ReactNode, RefObject } from 'react';
import {
  Box,
  Checkbox,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TableSortLabel,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { TaskTrendSectionHeader } from './TaskTrendSectionHeader';
import { formatTrendTimestamp } from './shared';
import type { ReplayTrade, SortableKey } from './shared';

interface TaskTrendTradesTableProps {
  trades: ReplayTrade[];
  paginatedTrades: ReplayTrade[];
  selectedTradeId: string | null;
  highlightedTradeIds: Set<string>;
  selectedRowIds: Set<string>;
  isAllPageSelected: boolean;
  isRefreshing: boolean;
  orderBy: SortableKey;
  order: 'asc' | 'desc';
  replayColWidths: Record<string, number>;
  page: number;
  rowsPerPage: number;
  timezone: string;
  selectedRowRef: RefObject<HTMLTableRowElement | null>;
  onConfigureColumns: () => void;
  onCopySelected: () => void;
  onSelectAllOnPage: () => void;
  onResetSelection: () => void;
  onReload: () => void;
  onSelectTrade: (trade: ReplayTrade) => void;
  onToggleRowSelection: (id: string) => void;
  onTogglePageSelection: () => void;
  onSort: (column: SortableKey) => void;
  onPageChange: (_e: unknown, page: number) => void;
  onRowsPerPageChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  resizeHandle: (col: string) => ReactNode;
}

export function TaskTrendTradesTable({
  trades,
  paginatedTrades,
  selectedTradeId,
  highlightedTradeIds,
  selectedRowIds,
  isAllPageSelected,
  isRefreshing,
  orderBy,
  order,
  replayColWidths,
  page,
  rowsPerPage,
  timezone,
  selectedRowRef,
  onConfigureColumns,
  onCopySelected,
  onSelectAllOnPage,
  onResetSelection,
  onReload,
  onSelectTrade,
  onToggleRowSelection,
  onTogglePageSelection,
  onSort,
  onPageChange,
  onRowsPerPageChange,
  resizeHandle,
}: TaskTrendTradesTableProps) {
  const { t } = useTranslation('common');

  return (
    <Box
      sx={{
        flex: 1,
        minWidth: 0,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <TaskTrendSectionHeader
        title={t('tables.trend.trades')}
        count={trades.length}
        selectedCount={selectedRowIds.size}
        isRefreshing={isRefreshing}
        onConfigureColumns={onConfigureColumns}
        onCopySelected={onCopySelected}
        onSelectAllOnPage={onSelectAllOnPage}
        onResetSelection={onResetSelection}
        onReload={onReload}
      />

      <TableContainer
        component={Paper}
        variant="outlined"
        sx={{ overflowX: 'auto' }}
      >
        <Table stickyHeader sx={{ tableLayout: 'fixed', minWidth: 680 }}>
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox" sx={{ width: 42 }}>
                <Checkbox
                  checked={isAllPageSelected}
                  indeterminate={
                    !isAllPageSelected &&
                    paginatedTrades.some((r) => selectedRowIds.has(r.id))
                  }
                  onChange={onTogglePageSelection}
                />
              </TableCell>
              {(
                [
                  ['timestamp', t('tables.trend.time')],
                  ['direction', t('tables.trend.direction')],
                  ['layer_index', t('tables.trend.layer')],
                  ['retracement_count', t('tables.trend.ret')],
                  ['units', t('tables.trend.units')],
                  ['price', t('tables.trend.price')],
                  ['execution_method', t('tables.trend.event')],
                ] as Array<[SortableKey, string]>
              ).map(([column, label]) => (
                <TableCell
                  key={column}
                  align={
                    column === 'retracement_count' ||
                    column === 'units' ||
                    column === 'price'
                      ? 'right'
                      : 'left'
                  }
                  sortDirection={orderBy === column ? order : false}
                  sx={{
                    position: 'relative',
                    width: replayColWidths[column],
                    whiteSpace: 'nowrap',
                  }}
                >
                  <TableSortLabel
                    active={orderBy === column}
                    direction={orderBy === column ? order : 'asc'}
                    onClick={() => onSort(column)}
                  >
                    {label}
                  </TableSortLabel>
                  {resizeHandle(column)}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {paginatedTrades.map((row) => {
              const selected = row.id === selectedTradeId;
              const highlighted = highlightedTradeIds.has(row.id);
              const checked = selectedRowIds.has(row.id);
              return (
                <TableRow
                  key={row.id}
                  ref={selected ? selectedRowRef : undefined}
                  hover
                  onClick={() => onSelectTrade(row)}
                  selected={selected || highlighted}
                  sx={{
                    cursor: 'pointer',
                    height: 37,
                    ...((selected || highlighted) && {
                      backgroundColor: 'rgba(245, 158, 11, 0.15)',
                      '&.Mui-selected': {
                        backgroundColor: 'rgba(245, 158, 11, 0.15)',
                      },
                      '&.Mui-selected:hover': {
                        backgroundColor: 'rgba(245, 158, 11, 0.25)',
                      },
                    }),
                  }}
                >
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={checked}
                      onClick={(e) => e.stopPropagation()}
                      onChange={() => onToggleRowSelection(row.id)}
                    />
                  </TableCell>
                  <TableCell
                    sx={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {formatTrendTimestamp(row.timestamp, timezone)}
                  </TableCell>
                  <TableCell
                    sx={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {row.direction ? row.direction.toUpperCase() : ''}
                  </TableCell>
                  <TableCell
                    sx={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {row.layer_index ?? '-'}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {row.retracement_count ?? '-'}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {row.units}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {row.price ? `¥${parseFloat(row.price).toFixed(3)}` : '-'}
                  </TableCell>
                  <TableCell
                    sx={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {row.execution_method_display ||
                      row.execution_method ||
                      '-'}
                  </TableCell>
                </TableRow>
              );
            })}
            {paginatedTrades.length < rowsPerPage &&
              Array.from({ length: rowsPerPage - paginatedTrades.length }).map(
                (_, i) => (
                  <TableRow key={`trade-empty-${i}`} sx={{ height: 37 }}>
                    <TableCell
                      colSpan={8}
                      sx={{
                        backgroundColor: 'action.hover',
                        borderBottom: '1px solid',
                        borderColor: 'divider',
                        py: 0,
                      }}
                    />
                  </TableRow>
                )
              )}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination
        component="div"
        count={trades.length}
        page={page}
        onPageChange={onPageChange}
        rowsPerPage={rowsPerPage}
        onRowsPerPageChange={onRowsPerPageChange}
        rowsPerPageOptions={[10, 25, 50, 100]}
      />
    </Box>
  );
}
