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
import type { Trade } from '../../types/execution';

type SortField =
  | 'entry_time'
  | 'units'
  | 'entry_price'
  | 'exit_price'
  | 'pnl'
  | 'retracement_count';
type SortOrder = 'asc' | 'desc';

interface FloorLayerLogProps {
  trades: Trade[];
  selectedTradeIndex?: number | null;
}

export function FloorLayerLog({
  trades,
  selectedTradeIndex,
}: FloorLayerLogProps) {
  // Sorting state - default sort by entry_time ascending
  const [sortField, setSortField] = useState<SortField>('entry_time');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');

  // Filter trades that have floor strategy data
  const floorTrades = trades.filter(
    (trade) => trade.layer_number !== undefined
  );

  // Handle sort request
  const handleSort = (field: SortField) => {
    const isAsc = sortField === field && sortOrder === 'asc';
    setSortOrder(isAsc ? 'desc' : 'asc');
    setSortField(field);
  };

  // Group trades by layer with sorting applied
  const tradesByLayer = useMemo(() => {
    // Sort function
    const sortTradesInLayer = (tradesToSort: Trade[]) => {
      return [...tradesToSort].sort((a, b) => {
        let aValue: number | string = 0;
        let bValue: number | string = 0;

        switch (sortField) {
          case 'entry_time':
            aValue = new Date(a.entry_time).getTime();
            bValue = new Date(b.entry_time).getTime();
            break;
          case 'units':
            aValue = a.units;
            bValue = b.units;
            break;
          case 'entry_price':
            aValue = a.entry_price;
            bValue = b.entry_price;
            break;
          case 'exit_price':
            aValue = a.exit_price;
            bValue = b.exit_price;
            break;
          case 'pnl':
            aValue = a.pnl;
            bValue = b.pnl;
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

    const grouped = floorTrades.reduce(
      (acc, trade) => {
        const layer = trade.layer_number || 1;
        if (!acc[layer]) {
          acc[layer] = [];
        }
        acc[layer].push(trade);
        return acc;
      },
      {} as Record<number, Trade[]>
    );

    // Sort trades within each layer
    Object.keys(grouped).forEach((layerKey) => {
      grouped[Number(layerKey)] = sortTradesInLayer(grouped[Number(layerKey)]);
    });

    return grouped;
  }, [floorTrades, sortField, sortOrder]);

  if (import.meta.env.DEV) {
    console.log('[FloorLayerLog] Rendering', {
      total_trades: trades.length,
      floor_trades: floorTrades.length,
      sample_trade: trades[0],
    });
  }

  if (floorTrades.length === 0) {
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

      {Object.keys(tradesByLayer)
        .sort((a, b) => Number(a) - Number(b))
        .map((layerKey) => {
          const layer = Number(layerKey);
          const layerTrades = tradesByLayer[layer];

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
                  label={`${layerTrades.length} trades`}
                  size="small"
                  color="primary"
                  variant="outlined"
                />
              </Box>

              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Type</TableCell>
                      <TableCell>
                        <TableSortLabel
                          active={sortField === 'entry_time'}
                          direction={
                            sortField === 'entry_time' ? sortOrder : 'asc'
                          }
                          onClick={() => handleSort('entry_time')}
                        >
                          Entry Time
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
                    {/* All trades sorted together */}
                    {layerTrades.map((trade, idx) => {
                      // Find the index of this trade in the original trades array
                      const tradeIndex = trades.findIndex((t) => t === trade);
                      const isSelected = selectedTradeIndex === tradeIndex;
                      const isFirstLot = trade.is_first_lot;

                      return (
                        <TableRow
                          key={`trade-${idx}`}
                          id={`trade-${tradeIndex}`}
                          sx={{
                            bgcolor: isSelected
                              ? 'primary.light'
                              : isFirstLot
                                ? 'action.hover'
                                : undefined,
                            transition: 'background-color 0.3s',
                          }}
                        >
                          <TableCell>
                            <Chip
                              label={isFirstLot ? 'Initial' : 'Scale-in'}
                              size="small"
                              color={isFirstLot ? 'info' : 'default'}
                              sx={
                                isFirstLot ? { fontWeight: 'bold' } : undefined
                              }
                            />
                          </TableCell>
                          <TableCell>{formatDate(trade.entry_time)}</TableCell>
                          <TableCell>
                            <Chip
                              label={trade.direction.toUpperCase()}
                              size="small"
                              color={
                                trade.direction === 'long'
                                  ? 'success'
                                  : 'warning'
                              }
                            />
                          </TableCell>
                          <TableCell align="right">{trade.units}</TableCell>
                          <TableCell align="right">
                            {formatPrice(trade.entry_price)}
                          </TableCell>
                          <TableCell align="right">
                            {formatPrice(trade.exit_price)}
                          </TableCell>
                          <TableCell
                            align="right"
                            sx={{
                              color:
                                trade.pnl >= 0 ? 'success.main' : 'error.main',
                              fontWeight: 'bold',
                            }}
                          >
                            ${trade.pnl.toFixed(2)}
                          </TableCell>
                          <TableCell align="right">
                            {trade.retracement_count !== undefined
                              ? trade.retracement_count
                              : '-'}
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
                            layerTrades.reduce((sum, t) => sum + t.pnl, 0) >= 0
                              ? 'success.main'
                              : 'error.main',
                        }}
                      >
                        $
                        {layerTrades
                          .reduce((sum, t) => sum + t.pnl, 0)
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
