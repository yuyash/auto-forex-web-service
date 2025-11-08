import React from 'react';
import {
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TablePagination,
  TextField,
  Box,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  InputAdornment,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import DownloadIcon from '@mui/icons-material/Download';
import { format } from 'date-fns';

export interface Trade {
  entry_time: string;
  exit_time: string;
  instrument: string;
  direction: 'long' | 'short';
  units: number;
  entry_price: number;
  exit_price: number;
  pnl: number;
  duration?: string;
}

interface TradeLogTableProps {
  trades: Trade[];
  title?: string;
  showExport?: boolean;
  onExport?: () => void;
  defaultRowsPerPage?: number;
}

type SortField = 'entry_time' | 'exit_time' | 'instrument' | 'pnl' | 'duration';
type SortOrder = 'asc' | 'desc';

export const TradeLogTable: React.FC<TradeLogTableProps> = ({
  trades,
  title = 'Trade Log',
  showExport = true,
  onExport,
  defaultRowsPerPage = 10,
}) => {
  const [page, setPage] = React.useState(0);
  const [rowsPerPage, setRowsPerPage] = React.useState(defaultRowsPerPage);
  const [sortField, setSortField] = React.useState<SortField>('entry_time');
  const [sortOrder, setSortOrder] = React.useState<SortOrder>('desc');
  const [searchTerm, setSearchTerm] = React.useState('');

  // Filter trades by search term
  const filteredTrades = React.useMemo(() => {
    if (!searchTerm) return trades;
    const lowerSearch = searchTerm.toLowerCase();
    return trades.filter(
      (trade) =>
        trade.instrument.toLowerCase().includes(lowerSearch) ||
        trade.direction.toLowerCase().includes(lowerSearch)
    );
  }, [trades, searchTerm]);

  // Sort trades - disable React Compiler for this memo
  // eslint-disable-next-line react-hooks/preserve-manual-memoization
  const sortedTrades = React.useMemo(() => {
    return [...filteredTrades].sort((a, b) => {
      let aValue: string | number;
      let bValue: string | number;

      switch (sortField) {
        case 'entry_time':
          aValue = new Date(a.entry_time).getTime();
          bValue = new Date(b.entry_time).getTime();
          break;
        case 'exit_time':
          aValue = new Date(a.exit_time).getTime();
          bValue = new Date(b.exit_time).getTime();
          break;
        case 'instrument':
          aValue = a.instrument;
          bValue = b.instrument;
          break;
        case 'pnl':
          aValue = a.pnl;
          bValue = b.pnl;
          break;
        case 'duration':
          aValue = calculateDuration(a);
          bValue = calculateDuration(b);
          break;
        default:
          return 0;
      }

      if (aValue < bValue) return sortOrder === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
  }, [filteredTrades, sortField, sortOrder]);

  // Paginate trades
  const paginatedTrades = React.useMemo(() => {
    const start = page * rowsPerPage;
    return sortedTrades.slice(start, start + rowsPerPage);
  }, [sortedTrades, page, rowsPerPage]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
  };

  const handleChangePage = (_: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatDateTime = (dateString: string): string => {
    return format(new Date(dateString), 'MMM dd, yyyy HH:mm');
  };

  const calculateDuration = (trade: Trade): number => {
    const entry = new Date(trade.entry_time).getTime();
    const exit = new Date(trade.exit_time).getTime();
    return exit - entry;
  };

  const formatDuration = (trade: Trade): string => {
    const durationMs = calculateDuration(trade);
    const hours = Math.floor(durationMs / (1000 * 60 * 60));
    const minutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60));

    if (hours > 24) {
      const days = Math.floor(hours / 24);
      return `${days}d ${hours % 24}h`;
    } else if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else {
      return `${minutes}m`;
    }
  };

  // Calculate summary statistics
  const stats = React.useMemo(() => {
    const totalPnL = filteredTrades.reduce((sum, trade) => sum + trade.pnl, 0);
    const winningTrades = filteredTrades.filter((t) => t.pnl > 0).length;
    const losingTrades = filteredTrades.filter((t) => t.pnl < 0).length;
    const winRate =
      filteredTrades.length > 0
        ? (winningTrades / filteredTrades.length) * 100
        : 0;

    return {
      totalPnL,
      winningTrades,
      losingTrades,
      winRate,
    };
  }, [filteredTrades]);

  if (trades.length === 0) {
    return (
      <Paper sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          No trades available
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper>
      <Box
        sx={{
          p: 2,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Typography variant="h6">{title}</Typography>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <TextField
            size="small"
            placeholder="Search trades..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setPage(0);
            }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
          {showExport && onExport && (
            <Tooltip title="Export to CSV">
              <IconButton size="small" onClick={onExport}>
                <DownloadIcon />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      </Box>

      {/* Summary Statistics */}
      <Box sx={{ px: 2, pb: 2, display: 'flex', gap: 3, flexWrap: 'wrap' }}>
        <Box>
          <Typography variant="caption" color="text.secondary">
            Total P&L
          </Typography>
          <Typography
            variant="body2"
            sx={{
              fontWeight: 600,
              color: stats.totalPnL >= 0 ? 'success.main' : 'error.main',
            }}
          >
            {formatCurrency(stats.totalPnL)}
          </Typography>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">
            Win Rate
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {stats.winRate.toFixed(1)}%
          </Typography>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">
            Trades
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {filteredTrades.length} ({stats.winningTrades}W /{' '}
            {stats.losingTrades}L)
          </Typography>
        </Box>
      </Box>

      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>
                <TableSortLabel
                  active={sortField === 'entry_time'}
                  direction={sortField === 'entry_time' ? sortOrder : 'asc'}
                  onClick={() => handleSort('entry_time')}
                >
                  Entry Time
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortField === 'exit_time'}
                  direction={sortField === 'exit_time' ? sortOrder : 'asc'}
                  onClick={() => handleSort('exit_time')}
                >
                  Exit Time
                </TableSortLabel>
              </TableCell>
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
                  active={sortField === 'duration'}
                  direction={sortField === 'duration' ? sortOrder : 'asc'}
                  onClick={() => handleSort('duration')}
                >
                  Duration
                </TableSortLabel>
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {paginatedTrades.map((trade, index) => (
              <TableRow key={index} hover>
                <TableCell>{formatDateTime(trade.entry_time)}</TableCell>
                <TableCell>{formatDateTime(trade.exit_time)}</TableCell>
                <TableCell>{trade.instrument}</TableCell>
                <TableCell>
                  <Chip
                    label={trade.direction.toUpperCase()}
                    size="small"
                    color={trade.direction === 'long' ? 'success' : 'error'}
                    variant="outlined"
                  />
                </TableCell>
                <TableCell align="right">
                  {trade.units.toLocaleString()}
                </TableCell>
                <TableCell align="right">
                  {trade.entry_price.toFixed(5)}
                </TableCell>
                <TableCell align="right">
                  {trade.exit_price.toFixed(5)}
                </TableCell>
                <TableCell
                  align="right"
                  sx={{
                    fontWeight: 600,
                    color: trade.pnl >= 0 ? 'success.main' : 'error.main',
                  }}
                >
                  {formatCurrency(trade.pnl)}
                </TableCell>
                <TableCell align="right">{formatDuration(trade)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <TablePagination
        rowsPerPageOptions={[5, 10, 25, 50, 100]}
        component="div"
        count={sortedTrades.length}
        rowsPerPage={rowsPerPage}
        page={page}
        onPageChange={handleChangePage}
        onRowsPerPageChange={handleChangeRowsPerPage}
      />
    </Paper>
  );
};
