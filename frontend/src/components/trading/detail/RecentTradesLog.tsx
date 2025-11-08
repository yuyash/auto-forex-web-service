import { useState, useEffect } from 'react';
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
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
} from '@mui/icons-material';

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
  taskId: number;
}

type SortField = 'exit_time' | 'pnl' | 'instrument';
type SortOrder = 'asc' | 'desc';

export function RecentTradesLog({ taskId }: RecentTradesLogProps) {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [sortField, setSortField] = useState<SortField>('exit_time');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const tradesPerPage = 10;

  // Mock data - in real implementation, this would fetch from API
  useEffect(() => {
    const fetchTrades = () => {
      // Simulate fetching recent trades
      const mockTrades: Trade[] = [
        {
          id: 1,
          instrument: 'EUR_USD',
          direction: 'long',
          units: 10000,
          entry_price: '1.0800',
          exit_price: '1.0845',
          pnl: '45.20',
          entry_time: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
          exit_time: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
        },
        {
          id: 2,
          instrument: 'GBP_USD',
          direction: 'short',
          units: 5000,
          entry_price: '1.2680',
          exit_price: '1.2705',
          pnl: '-12.50',
          entry_time: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
          exit_time: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
        },
        {
          id: 3,
          instrument: 'USD_JPY',
          direction: 'long',
          units: 8000,
          entry_price: '149.50',
          exit_price: '149.85',
          pnl: '28.00',
          entry_time: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
          exit_time: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
        },
      ];

      // Sort trades
      const sortedTrades = [...mockTrades].sort((a, b) => {
        let aValue: string | number = a[sortField];
        let bValue: string | number = b[sortField];

        if (sortField === 'pnl') {
          aValue = parseFloat(a.pnl);
          bValue = parseFloat(b.pnl);
        } else if (sortField === 'exit_time') {
          aValue = new Date(a.exit_time).getTime();
          bValue = new Date(b.exit_time).getTime();
        }

        if (sortOrder === 'asc') {
          return aValue > bValue ? 1 : -1;
        } else {
          return aValue < bValue ? 1 : -1;
        }
      });

      setTrades(sortedTrades);
      setTotalPages(Math.ceil(sortedTrades.length / tradesPerPage));
    };

    fetchTrades();

    // Auto-refresh every 5 seconds
    const interval = setInterval(() => {
      // In real implementation, fetch updated trades
      setLastUpdate(new Date());
    }, 5000);

    return () => clearInterval(interval);
  }, [taskId, sortField, sortOrder, tradesPerPage]);

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
