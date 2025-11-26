/**
 * FloorLayerLog Component
 *
 * Displays floor strategy specific information including layer and retracement data.
 * Shows a table of trades grouped by layer with retracement counts.
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
} from '@mui/material';
import type { Trade, StrategyEvent } from '../../types/execution';

type SortField =
  | 'timestamp'
  | 'units'
  | 'entry_price'
  | 'exit_price'
  | 'pnl'
  | 'retracement_count';
type SortOrder = 'asc' | 'desc';

// Combined event type that can be either a trade or a strategy event
interface CombinedEvent {
  type: 'trade' | 'event';
  timestamp: string;
  layer_number: number;
  event_type: string;
  direction?: 'long' | 'short';
  units?: number;
  entry_price?: number;
  exit_price?: number;
  pnl?: number;
  retracement_count?: number;
  is_first_lot?: boolean;
  tradeIndex?: number; // For highlighting selected trade
}

interface FloorLayerLogProps {
  trades: Trade[];
  strategyEvents?: StrategyEvent[];
  selectedTradeIndex?: number | null;
}

export function FloorLayerLog({
  trades,
  strategyEvents = [],
  selectedTradeIndex,
}: FloorLayerLogProps) {
  // Sorting state - default sort by timestamp ascending
  const [sortField, setSortField] = useState<SortField>('timestamp');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');

  // Filter trades that have floor strategy data
  const floorTrades = trades.filter(
    (trade) => trade.layer_number !== undefined
  );

  // Merge trades and strategy events into combined events
  const combinedEvents = useMemo(() => {
    const events: CombinedEvent[] = [];

    // Add trades as events
    floorTrades.forEach((trade) => {
      const tradeIndex = trades.findIndex((t) => t === trade);
      events.push({
        type: 'trade',
        timestamp: trade.entry_time,
        layer_number: trade.layer_number || 1,
        event_type: trade.is_first_lot ? 'initial' : 'retracement',
        direction: trade.direction,
        units: trade.units,
        entry_price: trade.entry_price,
        exit_price: trade.exit_price,
        pnl: trade.pnl,
        retracement_count: trade.retracement_count,
        is_first_lot: trade.is_first_lot,
        tradeIndex,
      });
    });

    // Add strategy events
    strategyEvents.forEach((event) => {
      events.push({
        type: 'event',
        timestamp: event.timestamp,
        layer_number: event.layer_number,
        event_type: event.event_type,
        direction: event.direction,
        units: event.units,
        entry_price: event.entry_price,
        exit_price: event.exit_price,
        pnl: event.pnl,
        retracement_count: event.retracement_count,
      });
    });

    // Sort by timestamp
    return events.sort((a, b) => {
      const timeA = new Date(a.timestamp).getTime();
      const timeB = new Date(b.timestamp).getTime();
      return timeA - timeB;
    });
  }, [floorTrades, strategyEvents, trades]);

  // Handle sort request
  const handleSort = (field: SortField) => {
    const isAsc = sortField === field && sortOrder === 'asc';
    setSortOrder(isAsc ? 'desc' : 'asc');
    setSortField(field);
  };

  // Group events by layer with sorting applied
  const eventsByLayer = useMemo(() => {
    // Sort function
    const sortEventsInLayer = (eventsToSort: CombinedEvent[]) => {
      return [...eventsToSort].sort((a, b) => {
        let aValue: number | string = 0;
        let bValue: number | string = 0;

        switch (sortField) {
          case 'timestamp':
            aValue = new Date(a.timestamp).getTime();
            bValue = new Date(b.timestamp).getTime();
            break;
          case 'units':
            aValue = a.units ?? -1;
            bValue = b.units ?? -1;
            break;
          case 'entry_price':
            aValue = a.entry_price ?? -1;
            bValue = b.entry_price ?? -1;
            break;
          case 'exit_price':
            aValue = a.exit_price ?? -1;
            bValue = b.exit_price ?? -1;
            break;
          case 'pnl':
            aValue = a.pnl ?? -1;
            bValue = b.pnl ?? -1;
            break;
          case 'retracement_count':
            aValue = a.retracement_count ?? -1;
            bValue = b.retracement_count ?? -1;
            break;
        }

        if (aValue < bValue) {
          return sortOrder === 'asc' ? -1 : 1;
        }
        if (aValue > bValue) {
          return sortOrder === 'asc' ? 1 : -1;
        }
        return 0;
      });
    };

    const grouped = combinedEvents.reduce(
      (acc, event) => {
        const layer = event.layer_number || 1;
        if (!acc[layer]) {
          acc[layer] = [];
        }
        acc[layer].push(event);
        return acc;
      },
      {} as Record<number, CombinedEvent[]>
    );

    // Sort events within each layer
    Object.keys(grouped).forEach((layerKey) => {
      grouped[Number(layerKey)] = sortEventsInLayer(grouped[Number(layerKey)]);
    });

    return grouped;
  }, [combinedEvents, sortField, sortOrder]);

  if (import.meta.env.DEV) {
    console.log('[FloorLayerLog] Rendering', {
      total_trades: trades.length,
      floor_trades: floorTrades.length,
      strategy_events: strategyEvents.length,
      combined_events: combinedEvents.length,
      sample_trade: trades[0],
    });
  }

  if (combinedEvents.length === 0) {
    // Show a message if no floor data is available
    return (
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Floor Strategy - Layer & Retracement Log
        </Typography>
        <Typography variant="body2" color="text.secondary">
          No floor/layer data available for these trades. This may be because:
        </Typography>
        <Box component="ul" sx={{ mt: 1, pl: 3 }}>
          <Typography component="li" variant="body2" color="text.secondary">
            The backtest was run before floor/layer tracking was implemented
          </Typography>
          <Typography component="li" variant="body2" color="text.secondary">
            The trades don't have layer_number metadata
          </Typography>
        </Box>
      </Paper>
    );
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const formatPrice = (price: number) => {
    return price.toFixed(5);
  };

  // Helper to determine if event type is a close event
  const isCloseEvent = (eventType: string) => {
    return [
      'close',
      'take_profit',
      'volatility_lock',
      'margin_protection',
    ].includes(eventType);
  };

  // Helper to get event type display properties
  const getEventTypeDisplay = (eventType: string) => {
    const displays: Record<
      string,
      {
        label: string;
        color: 'info' | 'default' | 'error' | 'success' | 'warning';
      }
    > = {
      initial: { label: 'Initial', color: 'info' },
      retracement: { label: 'Retracement', color: 'default' },
      layer: { label: 'Layer', color: 'default' },
      close: { label: 'Close', color: 'error' },
      take_profit: { label: 'Take Profit', color: 'success' },
      volatility_lock: { label: 'Volatility Lock', color: 'warning' },
      margin_protection: { label: 'Margin Protection', color: 'error' },
    };
    return displays[eventType] || { label: eventType, color: 'default' };
  };

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Floor Strategy - Layer & Retracement Log
      </Typography>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        This table shows trades grouped by layer with retracement counts at the
        time of entry. The floor strategy scales into positions as price
        retraces, creating multiple layers.
      </Typography>

      {Object.keys(eventsByLayer)
        .sort((a, b) => Number(a) - Number(b))
        .map((layerKey) => {
          const layer = Number(layerKey);
          const layerEvents = eventsByLayer[layer];

          return (
            <Box key={layer} sx={{ mb: 4 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 2,
                  mb: 2,
                }}
              >
                <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                  Layer {layer}
                </Typography>
                <Chip
                  label={`${layerEvents.length} events`}
                  size="small"
                  color="primary"
                  variant="outlined"
                />
              </Box>

              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Event Type</TableCell>
                      <TableCell>
                        <TableSortLabel
                          active={sortField === 'timestamp'}
                          direction={
                            sortField === 'timestamp' ? sortOrder : 'asc'
                          }
                          onClick={() => handleSort('timestamp')}
                        >
                          Time
                        </TableSortLabel>
                      </TableCell>
                      <TableCell>Direction</TableCell>
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
                          direction={
                            sortField === 'entry_price' ? sortOrder : 'asc'
                          }
                          onClick={() => handleSort('entry_price')}
                        >
                          Entry Price
                        </TableSortLabel>
                      </TableCell>
                      <TableCell align="right">
                        <TableSortLabel
                          active={sortField === 'exit_price'}
                          direction={
                            sortField === 'exit_price' ? sortOrder : 'asc'
                          }
                          onClick={() => handleSort('exit_price')}
                        >
                          Exit Price
                        </TableSortLabel>
                      </TableCell>
                      <TableCell align="right">
                        <TableSortLabel
                          active={sortField === 'pnl'}
                          direction={sortField === 'pnl' ? sortOrder : 'asc'}
                          onClick={() => handleSort('pnl')}
                        >
                          P&L
                        </TableSortLabel>
                      </TableCell>
                      <TableCell align="right">
                        <TableSortLabel
                          active={sortField === 'retracement_count'}
                          direction={
                            sortField === 'retracement_count'
                              ? sortOrder
                              : 'asc'
                          }
                          onClick={() => handleSort('retracement_count')}
                        >
                          Retracements
                        </TableSortLabel>
                      </TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {/* All events sorted together */}
                    {layerEvents.map((event, idx) => {
                      const isSelected =
                        event.tradeIndex !== undefined &&
                        selectedTradeIndex === event.tradeIndex;
                      const isInitial = event.event_type === 'initial';
                      const isClose = isCloseEvent(event.event_type);
                      const eventDisplay = getEventTypeDisplay(
                        event.event_type
                      );

                      return (
                        <TableRow
                          key={`event-${idx}`}
                          id={
                            event.tradeIndex !== undefined
                              ? `trade-${event.tradeIndex}`
                              : undefined
                          }
                          sx={{
                            bgcolor: isSelected
                              ? 'primary.light'
                              : isInitial
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
                              sx={
                                isInitial ? { fontWeight: 'bold' } : undefined
                              }
                            />
                          </TableCell>
                          <TableCell>{formatDate(event.timestamp)}</TableCell>
                          <TableCell>
                            {event.direction ? (
                              <Chip
                                label={event.direction.toUpperCase()}
                                size="small"
                                color={
                                  event.direction === 'long'
                                    ? 'success'
                                    : 'warning'
                                }
                              />
                            ) : (
                              '-'
                            )}
                          </TableCell>
                          <TableCell align="right">
                            {event.units !== undefined ? event.units : '-'}
                          </TableCell>
                          <TableCell align="right">
                            {event.entry_price !== undefined
                              ? formatPrice(event.entry_price)
                              : '-'}
                          </TableCell>
                          <TableCell align="right">
                            {isClose && event.exit_price !== undefined
                              ? formatPrice(event.exit_price)
                              : '-'}
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
                              fontWeight:
                                event.pnl !== undefined ? 'bold' : undefined,
                            }}
                          >
                            {isClose && event.pnl !== undefined
                              ? `$${event.pnl.toFixed(2)}`
                              : '-'}
                          </TableCell>
                          <TableCell align="right">
                            {event.retracement_count !== undefined &&
                            event.retracement_count > 0
                              ? event.retracement_count
                              : ''}
                          </TableCell>
                        </TableRow>
                      );
                    })}

                    {/* Layer summary row */}
                    <TableRow sx={{ bgcolor: 'grey.100' }}>
                      <TableCell colSpan={6} sx={{ fontWeight: 'bold' }}>
                        Layer {layer} Total
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{
                          fontWeight: 'bold',
                          color:
                            layerEvents
                              .filter((e) => e.pnl !== undefined)
                              .reduce((sum, e) => sum + (e.pnl || 0), 0) >= 0
                              ? 'success.main'
                              : 'error.main',
                        }}
                      >
                        $
                        {layerEvents
                          .filter((e) => e.pnl !== undefined)
                          .reduce((sum, e) => sum + (e.pnl || 0), 0)
                          .toFixed(2)}
                      </TableCell>
                      <TableCell />
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          );
        })}
    </Paper>
  );
}
