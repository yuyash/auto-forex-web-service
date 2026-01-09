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
  selectedTradeIndex?: number | null; // Index of selected trade for highlighting
}

type SortField = 'entry_time' | 'exit_time' | 'instrument' | 'pnl' | 'duration';
type SortOrder = 'asc' | 'desc';

export const TradeLogTable: React.FC<TradeLogTableProps> = ({
  trades,
  title = 'Trade Log',
  showExport = true,
  onExport,
  defaultRowsPerPage = 10,
  selectedTradeIndex = null,
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

  const safeDateMs = (value: unknown): number => {
    const d = new Date(String(value ?? ''));
    const ms = d.getTime();
    return Number.isNaN(ms) ? 0 : ms;
  };

  const calculateDurationMs = React.useCallback((trade: Trade): number | undefined => {
    const entry = safeDateMs(trade.entry_time);
    const exit = safeDateMs(trade.exit_time);
    if (!entry || !exit) return undefined;
    return exit - entry;
  }, []);

  // Sort trades
  const sortedTrades = React.useMemo(() => {
    return [...filteredTrades].sort((a, b) => {
      let aValue: string | number;
      let bValue: string | number;

      switch (sortField) {
        case 'entry_time':
          aValue = safeDateMs(a.entry_time);
          bValue = safeDateMs(b.entry_time);
          break;
        case 'exit_time':
          aValue = safeDateMs(a.exit_time);
          bValue = safeDateMs(b.exit_time);
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
          aValue = calculateDurationMs(a) ?? 0;
          bValue = calculateDurationMs(b) ?? 0;
          break;
        default:
          return 0;
      }

      if (aValue < bValue) return sortOrder === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
  }, [filteredTrades, sortField, sortOrder, calculateDurationMs]);

  // Scroll to selected trade when it changes
  React.useEffect(() => {
    if (selectedTradeIndex !== null) {
      // Find the page containing the selected trade
      const selectedTradeInSorted = sortedTrades.findIndex(
        (_, idx) => idx === selectedTradeIndex
      );

      if (selectedTradeInSorted !== -1) {
        const targetPage = Math.floor(selectedTradeInSorted / rowsPerPage);
        if (targetPage !== page) {
          setPage(targetPage);
        }
      }
    }
  }, [selectedTradeIndex, sortedTrades, rowsPerPage, page]);

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

  const toNumber = (value: unknown): number | undefined => {
    const n = typeof value === 'number' ? value : Number(value);
    return Number.isFinite(n) ? n : undefined;
  };

  const formatCurrency = (value: unknown): string => {
    const n = toNumber(value);
    if (n === undefined) return '-';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(n);
  };

  const formatPrice = (value: unknown): string => {
    const n = toNumber(value);
    if (n === undefined) return '-';
    return n.toFixed(5);
  };

  const formatDateTime = (dateString: unknown): string => {
    if (!dateString) return '-';
    const d = new Date(String(dateString));
    if (Number.isNaN(d.getTime())) return '-';
    return format(d, 'MMM dd, yyyy HH:mm');
  };

  const formatDuration = (trade: Trade): string => {
    const durationMs = calculateDurationMs(trade);
    if (durationMs === undefined) return '-';
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
            {paginatedTrades.map((trade, paginatedIndex) => {
              // Calculate the actual index in the original trades array
              const actualIndex = sortedTrades.findIndex((t) => t === trade);
              const isSelected = selectedTradeIndex === actualIndex;

              const directionRaw = (trade as unknown as { direction?: unknown })
                .direction;
              const direction =
                typeof directionRaw === 'string' ? directionRaw : '';
              const directionLabel = direction ? direction.toUpperCase() : '-';
              const pnlValue = toNumber(
                (trade as unknown as { pnl?: unknown }).pnl
              );

              return (
                <TableRow
                  key={paginatedIndex}
                  hover
                  selected={isSelected}
                  sx={{
                    backgroundColor: isSelected ? 'action.selected' : 'inherit',
                    transition: 'background-color 0.3s ease',
                  }}
                >
                  <TableCell>{formatDateTime(trade.entry_time)}</TableCell>
                  <TableCell>{formatDateTime(trade.exit_time)}</TableCell>
                  <TableCell>{trade.instrument || '-'}</TableCell>
                  <TableCell>
                    <Chip
                      label={directionLabel}
                      size="small"
                      color={
                        direction === 'long'
                          ? 'success'
                          : direction === 'short'
                            ? 'error'
                            : 'default'
                      }
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell align="right">
                    {toNumber(trade.units)?.toLocaleString() ?? '-'}
                  </TableCell>
                  <TableCell align="right">
                    {formatPrice(trade.entry_price)}
                  </TableCell>
                  <TableCell align="right">
                    {formatPrice(trade.exit_price)}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      fontWeight: 600,
                      color:
                        pnlValue === undefined
                          ? undefined
                          : pnlValue >= 0
                            ? 'success.main'
                            : 'error.main',
                    }}
                  >
                    {formatCurrency(trade.pnl)}
                  </TableCell>
                  <TableCell align="right">{formatDuration(trade)}</TableCell>
                </TableRow>
              );
            })}
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
