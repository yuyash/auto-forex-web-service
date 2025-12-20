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
  realizedPnl?: number;
  unrealizedPnl?: number;
  retracementCount?: number;
  entryRetracementCount?: number;
  maxRetracements?: number;
  isFirstLot?: boolean;
  description: string;
  tradeIndex?: number;
  source: 'trade' | 'event';
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
    scale_in: { label: 'Retracement', color: 'info' },
    take_profit: { label: 'Take Profit', color: 'success' },
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

export function FloorLayerLog({
  trades,
  strategyEvents = [],
  selectedTradeIndex,
}: FloorLayerLogProps) {
  const [sortField, setSortField] = useState<SortField>('timestamp');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');

  const displayEvents = useMemo(() => {
    const events: DisplayEvent[] = [];

    // Add strategy events
    strategyEvents.forEach((event, idx) => {
      const details = event.details || {};
      const layerNumber =
        (details.layer as number) || (details.layer_number as number) || 1;
      const entryRetracementCount = parseNumber(
        details.entry_retracement_count
      );
      const retracementCount = parseNumber(details.retracement_count);

      // Normalize strategy_close to take_profit (they're the same thing)
      const eventType =
        event.event_type === 'strategy_close'
          ? 'take_profit'
          : event.event_type;

      events.push({
        id: `event-${idx}`,
        timestamp: event.timestamp || (details.timestamp as string) || '',
        eventType,
        layerNumber,
        direction: details.direction as string | undefined,
        units: details.units ? parseFloat(String(details.units)) : undefined,
        entryPrice: details.entry_price
          ? parseFloat(String(details.entry_price))
          : details.price
            ? parseFloat(String(details.price))
            : undefined,
        exitPrice: details.exit_price
          ? parseFloat(String(details.exit_price))
          : undefined,
        pnl: details.pnl ? parseFloat(String(details.pnl)) : undefined,
        realizedPnl: details.realized_pnl
          ? parseFloat(String(details.realized_pnl))
          : details.pnl
            ? parseFloat(String(details.pnl))
            : undefined,
        unrealizedPnl: details.unrealized_pnl
          ? parseFloat(String(details.unrealized_pnl))
          : undefined,
        retracementCount,
        entryRetracementCount,
        maxRetracements: parseNumber(details.max_retracements),
        isFirstLot: details.is_first_lot as boolean | undefined,
        description: event.description,
        source: 'event',
      });
    });

    // Add entry events from trades (if not already in strategy events)
    trades.forEach((trade, idx) => {
      const layerNum = trade.layer_number ?? 1;
      const entryRetracementCount =
        typeof trade.entry_retracement_count === 'number'
          ? trade.entry_retracement_count
          : undefined;

      // Check if we already have an entry event for this trade
      const hasMatchingEntryEvent = events.some(
        (e) =>
          e.source === 'event' &&
          ['initial_entry', 'scale_in'].includes(e.eventType) &&
          e.entryPrice === trade.entry_price &&
          e.units === trade.units &&
          Math.abs(
            new Date(e.timestamp).getTime() -
              new Date(trade.entry_time).getTime()
          ) < 1000
      );

      if (!hasMatchingEntryEvent) {
        events.push({
          id: `trade-entry-${idx}`,
          timestamp: trade.entry_time,
          eventType: trade.is_first_lot ? 'initial_entry' : 'scale_in',
          layerNumber: layerNum,
          direction: trade.direction,
          units: trade.units,
          entryPrice: trade.entry_price,
          exitPrice: trade.exit_price,
          pnl: undefined, // Entry doesn't have P&L yet
          retracementCount: trade.retracement_count,
          entryRetracementCount:
            entryRetracementCount ?? trade.retracement_count,
          isFirstLot: trade.is_first_lot,
          description: trade.is_first_lot
            ? `Initial ${trade.direction?.toUpperCase()} entry @ ${formatPrice(trade.entry_price)}`
            : `Retracement ${trade.direction?.toUpperCase()} entry @ ${formatPrice(trade.entry_price)}`,
          tradeIndex: idx,
          source: 'trade',
        });
      }

      // Add close event from trade (take profit) - only if no matching close event exists
      const hasMatchingCloseEvent = events.some(
        (e) =>
          e.source === 'event' &&
          ['take_profit', 'volatility_lock', 'margin_protection'].includes(
            e.eventType
          ) &&
          e.units === trade.units &&
          Math.abs(
            new Date(e.timestamp).getTime() -
              new Date(trade.exit_time).getTime()
          ) < 2000
      );

      if (!hasMatchingCloseEvent && trade.exit_time) {
        events.push({
          id: `trade-close-${idx}`,
          timestamp: trade.exit_time,
          eventType: 'take_profit',
          layerNumber: layerNum,
          direction: trade.direction,
          units: trade.units,
          entryPrice: trade.entry_price,
          exitPrice: trade.exit_price,
          pnl: trade.pnl,
          realizedPnl: trade.realized_pnl ?? trade.pnl,
          unrealizedPnl: trade.unrealized_pnl,
          retracementCount: trade.retracement_count,
          entryRetracementCount:
            entryRetracementCount ?? trade.retracement_count,
          isFirstLot: trade.is_first_lot,
          description: `Take Profit: ${trade.direction?.toUpperCase()} ${trade.units} units closed @ ${formatPrice(trade.exit_price)} | P&L: ${formatCurrency(trade.pnl)}`,
          tradeIndex: idx,
          source: 'trade',
        });
      }
    });

    return events.sort((a, b) => {
      const timeA = new Date(a.timestamp).getTime();
      const timeB = new Date(b.timestamp).getTime();
      return sortOrder === 'asc' ? timeA - timeB : timeB - timeA;
    });
  }, [trades, strategyEvents, sortOrder]);

  // Filter and sort all events (merged across all layers)
  const sortedFilteredEvents = useMemo(() => {
    // Note: 'retracement_detected' and 'strategy_close' are excluded as they're redundant
    // with 'scale_in' (Add Layer) and 'take_profit' respectively
    const meaningfulEventTypes = [
      'initial_entry',
      'scale_in',
      'take_profit',
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
  };

  // Calculate total P&L across all events
  const totalPnL = useMemo(() => {
    return sortedFilteredEvents
      .filter((e) => e.pnl !== undefined)
      .reduce((sum, e) => sum + (e.pnl || 0), 0);
  }, [sortedFilteredEvents]);

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
        <Typography
          variant="body2"
          sx={{
            fontWeight: 'bold',
            color: totalPnL >= 0 ? 'success.main' : 'error.main',
          }}
        >
          Total P&L: {formatCurrency(totalPnL)}
        </Typography>
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Detailed execution log showing initial positions, layer additions,
        retracements, and take profits with buy/sell details.
      </Typography>

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
            {sortedFilteredEvents.map((event) => {
              const isSelected =
                event.tradeIndex !== undefined &&
                selectedTradeIndex === event.tradeIndex;
              const eventDisplay = getEventTypeDisplay(event.eventType);
              const isEntry = ['initial_entry', 'scale_in'].includes(
                event.eventType
              );
              const isClose = [
                'take_profit',
                'volatility_lock',
                'margin_protection',
              ].includes(event.eventType);
              const entryRetracementValue =
                event.entryRetracementCount ??
                (isEntry ? event.retracementCount : undefined);
              const remainingRetracementValue = !isEntry
                ? event.retracementCount
                : undefined;

              let action = '-';
              if (isEntry && event.direction)
                action = event.direction === 'long' ? 'LONG' : 'SHORT';
              else if (isClose) action = 'CLOSE';

              return (
                <TableRow
                  key={event.id}
                  id={event.id}
                  sx={{
                    bgcolor: isSelected
                      ? 'primary.light'
                      : event.isFirstLot
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
                    {entryRetracementValue !== undefined ||
                    remainingRetracementValue !== undefined ? (
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
                          {entryRetracementValue !== undefined && (
                            <Typography
                              component="span"
                              variant="body2"
                              sx={{ fontWeight: 'bold' }}
                            >
                              {entryRetracementValue}
                            </Typography>
                          )}
                          {remainingRetracementValue !== undefined && (
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              Remaining: {remainingRetracementValue}
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
                        event.realizedPnl !== undefined &&
                        event.realizedPnl >= 0
                          ? 'success.main'
                          : event.realizedPnl !== undefined
                            ? 'error.main'
                            : undefined,
                      fontWeight:
                        event.realizedPnl !== undefined ? 'bold' : undefined,
                    }}
                  >
                    {isClose && event.realizedPnl !== undefined
                      ? formatCurrency(event.realizedPnl)
                      : '-'}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      color:
                        event.unrealizedPnl !== undefined &&
                        event.unrealizedPnl >= 0
                          ? 'success.main'
                          : event.unrealizedPnl !== undefined
                            ? 'error.main'
                            : undefined,
                      fontWeight:
                        event.unrealizedPnl !== undefined ? 'bold' : undefined,
                    }}
                  >
                    {event.unrealizedPnl !== undefined
                      ? formatCurrency(event.unrealizedPnl)
                      : '-'}
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
                    {entryRetracementValue !== undefined &&
                      entryRetracementValue > 0 && (
                        <Typography variant="caption" color="text.secondary">
                          Retracement #{entryRetracementValue}
                        </Typography>
                      )}
                    {remainingRetracementValue !== undefined && (
                      <Typography variant="caption" color="text.secondary">
                        Remaining Retracements: {remainingRetracementValue}
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
