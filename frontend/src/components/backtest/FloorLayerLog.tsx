/**
 * FloorLayerLog Component
 *
 * Displays floor strategy specific information including layer and retracement data.
 * Shows detailed execution logs with initial positions, add layers, direction decisions,
 * retracements, and take profits with buy/sell details.
 */

import { useState, useMemo } from 'react';
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TablePagination,
  Chip,
  Tooltip,
} from '@mui/material';
import type { Trade, BacktestStrategyEvent } from '../../types/execution';

type SortField = 'timestamp' | 'layer' | 'units' | 'entry_price' | 'pnl';
type SortOrder = 'asc' | 'desc';

interface DisplayEvent {
  id: string;
  timestamp: string;
  eventType: string;
  layerNumber: number;
  direction?: string;
  units?: number;
  entryPrice?: number;
  exitPrice?: number;
  pnl?: number;
  retracementCount?: number;
  maxRetracements?: number;
  description: string;
  source: 'event';
}

interface FloorLayerLogProps {
  trades: Trade[];
  strategyEvents?: BacktestStrategyEvent[];
  selectedTradeIndex?: number | null;
}

const getEventTypeDisplay = (eventType: string) => {
  const displays: Record<
    string,
    {
      label: string;
      color: 'info' | 'default' | 'error' | 'success' | 'warning' | 'primary';
    }
  > = {
    initial_entry: { label: 'Initial Entry', color: 'primary' },
    retracement: { label: 'Retracement', color: 'info' },
    take_profit: { label: 'Take Profit', color: 'success' },
    add_layer: { label: 'Add Layer', color: 'warning' },
    remove_layer: { label: 'Remove Layer', color: 'warning' },
    volatility_lock: { label: 'Volatility Lock', color: 'error' },
    margin_protection: { label: 'Margin Protection', color: 'error' },
  };
  return displays[eventType] || { label: eventType, color: 'default' as const };
};

const formatPrice = (price: unknown): string => {
  const parsed = parseNumber(price);
  if (parsed === undefined) return '-';
  return parsed.toFixed(5);
};

const formatCurrency = (value: unknown): string => {
  const parsed = parseNumber(value);
  if (parsed === undefined) return '-';
  return `$${parsed.toFixed(2)}`;
};

const formatDate = (dateString: string): string => {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleString();
};

const parseNumber = (value: unknown): number | undefined => {
  const parsedValue = Number(value);
  return Number.isFinite(parsedValue) ? parsedValue : undefined;
};

export function FloorLayerLog({ strategyEvents = [] }: FloorLayerLogProps) {
  const [sortField, setSortField] = useState<SortField>('timestamp');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  const displayEvents = useMemo(() => {
    const events: DisplayEvent[] = [];

    strategyEvents.forEach((event, idx) => {
      const ts = event.timestamp || '';
      const layerNumber =
        typeof event.layer_number === 'number' &&
        Number.isFinite(event.layer_number)
          ? event.layer_number
          : 1;
      const unitsNum = parseNumber(event.units);
      const entryPriceNum =
        event.entry_price !== undefined
          ? parseNumber(event.entry_price)
          : event.price !== undefined
            ? parseNumber(event.price)
            : undefined;
      const exitPriceNum =
        event.exit_price !== undefined
          ? parseNumber(event.exit_price)
          : event.price !== undefined
            ? parseNumber(event.price)
            : undefined;
      const pnlNum = parseNumber(event.pnl);

      const direction =
        typeof event.direction === 'string'
          ? (event.direction as string)
          : undefined;

      const retracementCount =
        typeof event.retracement_count === 'number'
          ? event.retracement_count
          : parseNumber(event.retracement_count);

      const descriptionParts: string[] = [];
      descriptionParts.push(event.event_type);
      if (typeof direction === 'string' && direction) {
        descriptionParts.push(direction.toUpperCase());
      }
      if (unitsNum !== undefined) {
        descriptionParts.push(`${unitsNum} units`);
      }
      if (event.price !== undefined) {
        const p = parseNumber(event.price);
        if (p !== undefined) descriptionParts.push(`@ ${formatPrice(p)}`);
      }
      if (pnlNum !== undefined) {
        descriptionParts.push(`P&L: ${formatCurrency(pnlNum)}`);
      }

      events.push({
        id: `event-${idx}`,
        timestamp: ts,
        eventType: event.event_type,
        layerNumber,
        direction,
        units: unitsNum,
        entryPrice: entryPriceNum,
        exitPrice: exitPriceNum,
        pnl: pnlNum,
        retracementCount,
        maxRetracements:
          typeof event.max_retracements_per_layer === 'number'
            ? event.max_retracements_per_layer
            : undefined,
        description: descriptionParts.join(' '),
        source: 'event',
      });
    });

    return events.sort((a, b) => {
      const timeA = new Date(a.timestamp).getTime();
      const timeB = new Date(b.timestamp).getTime();
      return sortOrder === 'asc' ? timeA - timeB : timeB - timeA;
    });
  }, [strategyEvents, sortOrder]);

  // Filter and sort all events (merged across all layers)
  const sortedFilteredEvents = useMemo(() => {
    const meaningfulEventTypes = [
      'initial_entry',
      'retracement',
      'take_profit',
      'add_layer',
      'remove_layer',
      'volatility_lock',
      'margin_protection',
    ];

    const filtered = displayEvents.filter((e) =>
      meaningfulEventTypes.includes(e.eventType)
    );

    return filtered.sort((a, b) => {
      let aValue = 0,
        bValue = 0;
      switch (sortField) {
        case 'timestamp':
          aValue = new Date(a.timestamp).getTime();
          bValue = new Date(b.timestamp).getTime();
          break;
        case 'layer':
          aValue = a.layerNumber ?? 1;
          bValue = b.layerNumber ?? 1;
          break;
        case 'units':
          aValue = a.units ?? -1;
          bValue = b.units ?? -1;
          break;
        case 'entry_price':
          aValue = a.entryPrice ?? -1;
          bValue = b.entryPrice ?? -1;
          break;
        case 'pnl':
          aValue = a.pnl ?? -1;
          bValue = b.pnl ?? -1;
          break;
      }
      if (aValue < bValue) return sortOrder === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
  }, [displayEvents, sortField, sortOrder]);

  const handleSort = (field: SortField) => {
    const isAsc = sortField === field && sortOrder === 'asc';
    setSortOrder(isAsc ? 'desc' : 'asc');
    setSortField(field);
    setPage(0);
  };

  const paginatedEvents = useMemo(() => {
    const start = page * rowsPerPage;
    return sortedFilteredEvents.slice(start, start + rowsPerPage);
  }, [sortedFilteredEvents, page, rowsPerPage]);

  // Calculate total P&L across all events
  const totalPnL = useMemo(() => {
    return sortedFilteredEvents
      .filter((e) => e.pnl !== undefined)
      .reduce((sum, e) => sum + (e.pnl || 0), 0);
  }, [sortedFilteredEvents]);

  const shouldShowTotalPnL = Number.isFinite(totalPnL);

  if (displayEvents.length === 0) {
    return (
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Floor Strategy Execution Log
        </Typography>
        <Typography variant="body2" color="text.secondary">
          No floor strategy events available for this backtest.
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 2,
        }}
      >
        <Typography variant="h6">Floor Strategy Execution Log</Typography>
        {shouldShowTotalPnL && (
          <Typography
            variant="body2"
            sx={{
              fontWeight: 'bold',
              color: totalPnL >= 0 ? 'success.main' : 'error.main',
            }}
          >
            Total P&L: {formatCurrency(totalPnL)}
          </Typography>
        )}
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Detailed execution log showing initial positions, layer additions,
        retracements, and take profits with buy/sell details.
      </Typography>

      <TablePagination
        component="div"
        count={sortedFilteredEvents.length}
        page={page}
        onPageChange={(_e, newPage) => setPage(newPage)}
        rowsPerPage={rowsPerPage}
        onRowsPerPageChange={(e) => {
          setRowsPerPage(parseInt(e.target.value, 10));
          setPage(0);
        }}
        rowsPerPageOptions={[10, 25, 50, 100]}
      />

      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Event</TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortField === 'timestamp'}
                  direction={sortField === 'timestamp' ? sortOrder : 'asc'}
                  onClick={() => handleSort('timestamp')}
                >
                  Time
                </TableSortLabel>
              </TableCell>
              <TableCell align="center">
                <TableSortLabel
                  active={sortField === 'layer'}
                  direction={sortField === 'layer' ? sortOrder : 'asc'}
                  onClick={() => handleSort('layer')}
                >
                  Layer
                </TableSortLabel>
              </TableCell>
              <TableCell>Action</TableCell>
              <TableCell align="right">Retracement #</TableCell>
              <TableCell align="right">
                <TableSortLabel
                  active={sortField === 'units'}
                  direction={sortField === 'units' ? sortOrder : 'asc'}
                  onClick={() => handleSort('units')}
                >
                  Units
                </TableSortLabel>
              </TableCell>
              <TableCell align="right">
                <TableSortLabel
                  active={sortField === 'entry_price'}
                  direction={sortField === 'entry_price' ? sortOrder : 'asc'}
                  onClick={() => handleSort('entry_price')}
                >
                  Price
                </TableSortLabel>
              </TableCell>
              <TableCell align="right">
                <TableSortLabel
                  active={sortField === 'pnl'}
                  direction={sortField === 'pnl' ? sortOrder : 'asc'}
                  onClick={() => handleSort('pnl')}
                >
                  Realized P&L
                </TableSortLabel>
              </TableCell>
              <TableCell align="right">Unrealized P&L</TableCell>
              <TableCell>Details</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {paginatedEvents.map((event) => {
              const eventDisplay = getEventTypeDisplay(event.eventType);
              const isEntry = ['initial_entry', 'retracement'].includes(
                event.eventType
              );
              const isClose = [
                'take_profit',
                'volatility_lock',
                'margin_protection',
              ].includes(event.eventType);

              const retracementValue = isEntry
                ? event.retracementCount
                : undefined;

              const isLayerChange = ['add_layer', 'remove_layer'].includes(
                event.eventType
              );

              let action = '-';
              if (isEntry && event.direction)
                action = event.direction === 'long' ? 'LONG' : 'SHORT';
              else if (isClose) action = 'CLOSE';
              else if (event.eventType === 'add_layer') action = 'ADD';
              else if (event.eventType === 'remove_layer') action = 'REMOVE';
              else if (isLayerChange) action = 'LAYER';

              return (
                <TableRow
                  key={event.id}
                  id={event.id}
                  sx={{
                    bgcolor:
                      event.eventType === 'initial_entry'
                        ? 'action.hover'
                        : undefined,
                    transition: 'background-color 0.3s',
                  }}
                >
                  <TableCell>
                    <Chip
                      label={eventDisplay.label}
                      size="small"
                      color={eventDisplay.color}
                    />
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.85rem' }}>
                    {formatDate(event.timestamp)}
                  </TableCell>
                  <TableCell align="center">
                    <Chip
                      label={event.layerNumber}
                      size="small"
                      variant="outlined"
                      color="default"
                    />
                  </TableCell>
                  <TableCell>
                    {action !== '-' && (
                      <Chip
                        label={action}
                        size="small"
                        variant="outlined"
                        color={
                          action === 'LONG'
                            ? 'success'
                            : action === 'SHORT'
                              ? 'error'
                              : 'default'
                        }
                      />
                    )}
                  </TableCell>
                  <TableCell align="right">
                    {retracementValue !== undefined ? (
                      <Tooltip
                        title={
                          event.maxRetracements
                            ? `Max ${event.maxRetracements}`
                            : ''
                        }
                        placement="top"
                      >
                        <Box
                          sx={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'flex-end',
                            gap: 0.5,
                          }}
                        >
                          {retracementValue !== undefined && (
                            <Typography
                              component="span"
                              variant="body2"
                              sx={{ fontWeight: 'bold' }}
                            >
                              {retracementValue}
                            </Typography>
                          )}
                        </Box>
                      </Tooltip>
                    ) : (
                      '-'
                    )}
                  </TableCell>
                  <TableCell align="right">
                    {(() => {
                      const units = parseNumber(event.units);
                      return units !== undefined ? units.toFixed(1) : '-';
                    })()}
                  </TableCell>
                  <TableCell align="right">
                    {isClose && event.exitPrice !== undefined
                      ? formatPrice(event.exitPrice)
                      : formatPrice(event.entryPrice)}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      color:
                        event.pnl !== undefined && event.pnl >= 0
                          ? 'success.main'
                          : event.pnl !== undefined
                            ? 'error.main'
                            : undefined,
                      fontWeight: event.pnl !== undefined ? 'bold' : undefined,
                    }}
                  >
                    {isClose && event.pnl !== undefined
                      ? formatCurrency(event.pnl)
                      : '-'}
                  </TableCell>
                  <TableCell align="right" sx={{}}>
                    -
                  </TableCell>
                  <TableCell sx={{ maxWidth: 300 }}>
                    <Tooltip title={event.description} arrow>
                      <Typography
                        variant="caption"
                        sx={{
                          display: 'block',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {event.description}
                      </Typography>
                    </Tooltip>
                    {retracementValue !== undefined && retracementValue > 0 && (
                      <Typography variant="caption" color="text.secondary">
                        Retracement #{retracementValue}
                      </Typography>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
            <TableRow sx={{ bgcolor: 'grey.100' }}>
              <TableCell colSpan={7} sx={{ fontWeight: 'bold' }}>
                Total
              </TableCell>
              <TableCell
                align="right"
                sx={{
                  fontWeight: 'bold',
                  color: totalPnL >= 0 ? 'success.main' : 'error.main',
                }}
              >
                {formatCurrency(totalPnL)}
              </TableCell>
              <TableCell />
              <TableCell />
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}
