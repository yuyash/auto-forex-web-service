import { useState, useEffect, useCallback } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Chip,
  Box,
  Alert,
  Pagination,
  TableSortLabel,
  CircularProgress,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
} from '@mui/icons-material';
import { apiClient } from '../../../services/api/client';

interface Position {
  id: number;
  instrument: string;
  direction: 'long' | 'short';
  units: number;
  entry_price: string;
  current_price: string;
  realized_pnl: string;
  opened_at: string;
  closed_at: string;
}

interface Trade {
  id: number;
  instrument: string;
  direction: 'long' | 'short';
  units: number;
  entry_price: string;
  exit_price: string;
  pnl: string;
  entry_time: string;
  exit_time: string;
}

interface RecentTradesLogProps {
  taskId: string | number;
  executionStartedAt?: string;
}

type SortField = 'exit_time' | 'pnl' | 'instrument';
type SortOrder = 'asc' | 'desc';

export function RecentTradesLog({
  taskId,
  executionStartedAt,
}: RecentTradesLogProps) {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [sortField, setSortField] = useState<SortField>('exit_time');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const tradesPerPage = 10;

  const fetchTrades = useCallback(async () => {
    try {
      let url = `/positions/?trading_task_id=${taskId}&status=closed&page_size=50`;
      if (executionStartedAt) {
        url += `&opened_after=${encodeURIComponent(executionStartedAt)}`;
      }
      const response = await apiClient.get<{
        results: Position[];
        count: number;
      }>(url);
      // Convert positions to trades format
      const closedPositions = response.results || [];
      const tradeData: Trade[] = closedPositions.map((pos: Position) => ({
        id: pos.id,
        instrument: pos.instrument,
        direction: pos.direction,
        units: pos.units,
        entry_price: pos.entry_price,
        exit_price: pos.current_price,
        pnl: pos.realized_pnl || '0',
        entry_time: pos.opened_at,
        exit_time: pos.closed_at,
      }));
      setTrades(tradeData);
      setTotalPages(Math.ceil(tradeData.length / tradesPerPage));
      setError(null);
      setLastUpdate(new Date());
    } catch (err) {
      console.error('Failed to fetch trades:', err);
      setError('Failed to load trades');
    } finally {
      setIsLoading(false);
    }
  }, [taskId, executionStartedAt]);

  useEffect(() => {
    fetchTrades();

    const interval = setInterval(() => {
      fetchTrades();
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchTrades]);

  const handlePageChange = (
    _event: React.ChangeEvent<unknown>,
    value: number
  ) => {
    setPage(value);
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  const formatDuration = (entryTime: string, exitTime: string) => {
    const entry = new Date(entryTime);
    const exit = new Date(exitTime);
    const diff = exit.getTime() - entry.getTime();

    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else {
      return `${minutes}m`;
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const paginatedTrades = trades.slice(
    (page - 1) * tradesPerPage,
    page * tradesPerPage
  );

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  if (trades.length === 0) {
    return (
      <Alert severity="info">
        No trades executed yet. Trades will appear here as they are closed.
      </Alert>
    );
  }

  return (
    <Box>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ mb: 2, display: 'block' }}
      >
        Last updated: {lastUpdate.toLocaleTimeString()} • Auto-refreshing every
        5s
      </Typography>

      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>
                <TableSortLabel
                  active={sortField === 'instrument'}
                  direction={sortField === 'instrument' ? sortOrder : 'asc'}
                  onClick={() => handleSort('instrument')}
                >
                  Instrument
                </TableSortLabel>
              </TableCell>
              <TableCell>Direction</TableCell>
              <TableCell align="right">Units</TableCell>
              <TableCell align="right">Entry</TableCell>
              <TableCell align="right">Exit</TableCell>
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
                  active={sortField === 'exit_time'}
                  direction={sortField === 'exit_time' ? sortOrder : 'asc'}
                  onClick={() => handleSort('exit_time')}
                >
                  Closed At
                </TableSortLabel>
              </TableCell>
              <TableCell align="right">Duration</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {paginatedTrades.map((trade) => {
              const pnl = parseFloat(trade.pnl);
              const isProfitable = pnl >= 0;

              return (
                <TableRow key={trade.id} hover>
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {trade.instrument.replace('_', '/')}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={trade.direction.toUpperCase()}
                      size="small"
                      color={trade.direction === 'long' ? 'success' : 'error'}
                      icon={
                        trade.direction === 'long' ? (
                          <TrendingUpIcon />
                        ) : (
                          <TrendingDownIcon />
                        )
                      }
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2">
                      {trade.units.toLocaleString()}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2">
                      {parseFloat(trade.entry_price).toFixed(4)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2">
                      {parseFloat(trade.exit_price).toFixed(4)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography
                      variant="body2"
                      fontWeight="bold"
                      color={isProfitable ? 'success.main' : 'error.main'}
                    >
                      {isProfitable ? '+' : ''}${pnl.toFixed(2)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" color="text.secondary">
                      {formatTime(trade.exit_time)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" color="text.secondary">
                      {formatDuration(trade.entry_time, trade.exit_time)}
                    </Typography>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      {totalPages > 1 && (
        <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center' }}>
          <Pagination
            count={totalPages}
            page={page}
            onChange={handlePageChange}
            color="primary"
          />
        </Box>
      )}

      <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between' }}>
        <Typography variant="body2" color="text.secondary">
          Showing {paginatedTrades.length} of {trades.length} recent trades
        </Typography>
        <Typography
          variant="body2"
          fontWeight="bold"
          color={
            trades.reduce((sum, t) => sum + parseFloat(t.pnl), 0) >= 0
              ? 'success.main'
              : 'error.main'
          }
        >
          Total P&L: $
          {trades.reduce((sum, t) => sum + parseFloat(t.pnl), 0).toFixed(2)}
        </Typography>
      </Box>
    </Box>
  );
}
