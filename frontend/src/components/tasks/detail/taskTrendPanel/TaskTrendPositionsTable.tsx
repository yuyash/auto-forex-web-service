import type { ReactNode, RefObject } from 'react';
import {
  Box,
  Checkbox,
  Chip,
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
import { computePosPips, formatTrendTimestamp } from './shared';
import type { LSPosSortableKey, TrendPosition } from './shared';

interface TaskTrendPositionsTableProps {
  title: string;
  count: number;
  positions: TrendPosition[];
  paginatedPositions: TrendPosition[];
  selectedPosId: string | null;
  selectedIds: Set<string>;
  isAllPageSelected: boolean;
  isRefreshing: boolean;
  showOpenOnly: boolean;
  orderBy: LSPosSortableKey;
  order: 'asc' | 'desc';
  colWidths: Record<string, number>;
  currentPrice: number | null;
  pipSize: number | null | undefined;
  isShort: boolean;
  page: number;
  rowsPerPage: number;
  timezone: string;
  selectedPosRowRef: RefObject<HTMLTableRowElement | null>;
  onConfigureColumns: () => void;
  onCopySelected: () => void;
  onSelectAllOnPage: () => void;
  onResetSelection: () => void;
  onReload: () => void;
  onToggleOpenOnly: () => void;
  onTogglePageSelection: () => void;
  onSort: (column: LSPosSortableKey) => void;
  onSelectPosition: (position: TrendPosition) => void;
  onToggleSelection: (id: string) => void;
  onPageChange: (_e: unknown, page: number) => void;
  onRowsPerPageChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  resizeHandle: (col: string) => ReactNode;
}

export function TaskTrendPositionsTable({
  title,
  count,
  positions,
  paginatedPositions,
  selectedPosId,
  selectedIds,
  isAllPageSelected,
  isRefreshing,
  showOpenOnly,
  orderBy,
  order,
  colWidths,
  currentPrice,
  pipSize,
  isShort,
  page,
  rowsPerPage,
  timezone,
  selectedPosRowRef,
  onConfigureColumns,
  onCopySelected,
  onSelectAllOnPage,
  onResetSelection,
  onReload,
  onToggleOpenOnly,
  onTogglePageSelection,
  onSort,
  onSelectPosition,
  onToggleSelection,
  onPageChange,
  onRowsPerPageChange,
  resizeHandle,
}: TaskTrendPositionsTableProps) {
  const { t } = useTranslation('common');
  const columns: Array<[LSPosSortableKey, string, 'left' | 'right']> = [
    ['entry_time', t('tables.trend.openTime'), 'left'],
    ['exit_time', t('tables.trend.closeTime'), 'left'],
    ['_status', t('tables.trend.status'), 'left'],
    ['layer_index', t('tables.trend.layer'), 'left'],
    ['retracement_count', t('tables.trend.retrace'), 'left'],
    ['units', t('tables.trend.units'), 'right'],
    ['entry_price', t('tables.trend.entry'), 'right'],
    ['exit_price', t('tables.trend.exit'), 'right'],
    ['_pips', t('tables.trend.pips'), 'right'],
    ['_pnl', t('tables.trend.pnl'), 'right'],
  ];

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
        title={title}
        count={count}
        selectedCount={selectedIds.size}
        isRefreshing={isRefreshing}
        onConfigureColumns={onConfigureColumns}
        onCopySelected={onCopySelected}
        onSelectAllOnPage={onSelectAllOnPage}
        onResetSelection={onResetSelection}
        onReload={onReload}
        showOpenOnly={showOpenOnly}
        onToggleOpenOnly={onToggleOpenOnly}
      />
      <TableContainer
        component={Paper}
        variant="outlined"
        sx={{ overflowX: 'auto' }}
      >
        <Table stickyHeader sx={{ tableLayout: 'fixed', minWidth: 1000 }}>
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox" sx={{ width: 42 }}>
                <Checkbox
                  checked={isAllPageSelected}
                  indeterminate={
                    !isAllPageSelected &&
                    paginatedPositions.some((r) => selectedIds.has(r.id))
                  }
                  onChange={onTogglePageSelection}
                />
              </TableCell>
              {columns.map(([column, label, align]) => (
                <TableCell
                  key={column}
                  align={align}
                  sortDirection={orderBy === column ? order : false}
                  sx={{
                    position: 'relative',
                    width: colWidths[column],
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
            {paginatedPositions.map((pos) => {
              const isOpen = pos._status === 'open';
              const entryP = pos.entry_price
                ? parseFloat(pos.entry_price)
                : null;
              const exitP = pos.exit_price ? parseFloat(pos.exit_price) : null;
              const units = Math.abs(pos.units ?? 0);
              let pnl: number | null = null;
              if (isOpen && currentPrice != null && entryP != null) {
                pnl = isShort
                  ? (entryP - currentPrice) * units
                  : (currentPrice - entryP) * units;
              } else if (!isOpen && exitP != null && entryP != null) {
                pnl = isShort
                  ? (entryP - exitP) * units
                  : (exitP - entryP) * units;
              }
              const posSelected = pos.id === selectedPosId;
              const checked = selectedIds.has(pos.id);
              const pips = computePosPips(pos, currentPrice, pipSize);
              const hasPips =
                pipSize &&
                (isOpen
                  ? currentPrice != null && entryP != null
                  : exitP != null && entryP != null);

              return (
                <TableRow
                  key={pos.id}
                  ref={posSelected ? selectedPosRowRef : undefined}
                  hover
                  onClick={() => onSelectPosition(pos)}
                  selected={posSelected}
                  sx={{
                    cursor: 'pointer',
                    height: 37,
                    ...(posSelected && {
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
                      onChange={() => onToggleSelection(pos.id)}
                    />
                  </TableCell>
                  <TableCell
                    sx={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {formatTrendTimestamp(pos.entry_time, timezone)}
                  </TableCell>
                  <TableCell
                    sx={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {formatTrendTimestamp(pos.exit_time, timezone)}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={isOpen ? 'Open' : 'Closed'}
                      color={isOpen ? 'success' : 'default'}
                      variant="outlined"
                      sx={{ height: 20, fontSize: '0.7rem' }}
                    />
                  </TableCell>
                  <TableCell>{pos.layer_index ?? '-'}</TableCell>
                  <TableCell>{pos.retracement_count ?? '-'}</TableCell>
                  <TableCell align="right">{pos.units}</TableCell>
                  <TableCell align="right">
                    {entryP != null ? `¥${entryP.toFixed(3)}` : '-'}
                  </TableCell>
                  <TableCell align="right">
                    {exitP != null ? `¥${exitP.toFixed(3)}` : '-'}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      color: !pipSize
                        ? 'text.secondary'
                        : pips >= 0
                          ? 'success.main'
                          : 'error.main',
                      fontWeight: 'bold',
                    }}
                  >
                    {hasPips
                      ? `${pips >= 0 ? '+' : ''}${pips.toFixed(1)}`
                      : '-'}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      color:
                        pnl != null
                          ? pnl >= 0
                            ? 'success.main'
                            : 'error.main'
                          : 'text.secondary',
                      fontWeight: 'bold',
                    }}
                  >
                    {pnl != null
                      ? `${pnl >= 0 ? '+' : ''}¥${pnl.toFixed(2)}`
                      : '-'}
                  </TableCell>
                </TableRow>
              );
            })}
            {paginatedPositions.length < rowsPerPage &&
              Array.from({
                length: rowsPerPage - paginatedPositions.length,
              }).map((_, i) => (
                <TableRow key={`${title}-empty-${i}`} sx={{ height: 37 }}>
                  <TableCell
                    colSpan={11}
                    sx={{
                      backgroundColor: 'action.hover',
                      borderBottom: '1px solid',
                      borderColor: 'divider',
                      py: 0,
                    }}
                  />
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination
        component="div"
        count={positions.length}
        page={page}
        onPageChange={onPageChange}
        rowsPerPage={rowsPerPage}
        onRowsPerPageChange={onRowsPerPageChange}
        rowsPerPageOptions={[10, 25, 50, 100]}
      />
    </Box>
  );
}
