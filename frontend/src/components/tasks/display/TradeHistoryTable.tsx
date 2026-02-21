// TradeHistoryTable component - displays all trades with filtering, sorting, and pagination
import React, { useState, useMemo } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Button,
  TextField,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Chip,
  IconButton,
  Tooltip,
  Stack,
} from '@mui/material';
import {
  Download as DownloadIcon,
  FilterList as FilterIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import DataTable, { type Column } from '../../common/DataTable';
import { formatCurrency } from '../../../utils/formatters';
import type { Trade } from '../../../types';

interface TradeHistoryTableProps {
  trades: Trade[];
}

type DirectionFilter = 'all' | 'long' | 'short';
type SortField = 'entry_time' | 'exit_time' | 'pnl' | 'duration';
type SortOrder = 'asc' | 'desc';

export const TradeHistoryTable: React.FC<TradeHistoryTableProps> = ({
  trades,
}) => {
  const [instrumentFilter, setInstrumentFilter] = useState<string>('all');
  const [directionFilter, setDirectionFilter] =
    useState<DirectionFilter>('all');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [sortField, setSortField] = useState<SortField>('entry_time');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [showFilters, setShowFilters] = useState(false);

  // Get unique instruments for filter
  const instruments = useMemo(() => {
    const uniqueInstruments = new Set(trades.map((t) => t.instrument));
    return Array.from(uniqueInstruments).sort();
  }, [trades]);

  // Apply filters and sorting
  const filteredTrades = useMemo(() => {
    let filtered = [...trades];

    // Apply instrument filter
    if (instrumentFilter !== 'all') {
      filtered = filtered.filter((t) => t.instrument === instrumentFilter);
    }

    // Apply direction filter
    if (directionFilter !== 'all') {
      filtered = filtered.filter((t) => t.direction === directionFilter);
    }

    // Apply date range filter
    if (dateFrom) {
      const fromDate = new Date(dateFrom);
      filtered = filtered.filter((t) => new Date(t.entry_time) >= fromDate);
    }
    if (dateTo) {
      const toDate = new Date(dateTo);
      toDate.setHours(23, 59, 59, 999); // Include entire day
      filtered = filtered.filter((t) => new Date(t.entry_time) <= toDate);
    }

    // Apply sorting
    filtered.sort((a, b) => {
      let aValue: number;
      let bValue: number;

      switch (sortField) {
        case 'entry_time':
          aValue = new Date(a.entry_time).getTime();
          bValue = new Date(b.entry_time).getTime();
          break;
        case 'exit_time':
          aValue = new Date(a.exit_time).getTime();
          bValue = new Date(b.exit_time).getTime();
          break;
        case 'pnl':
          aValue = a.pnl;
          bValue = b.pnl;
          break;
        case 'duration':
          aValue =
            new Date(a.exit_time).getTime() - new Date(a.entry_time).getTime();
          bValue =
            new Date(b.exit_time).getTime() - new Date(b.entry_time).getTime();
          break;
        default:
          return 0;
      }

      if (sortOrder === 'asc') {
        return aValue > bValue ? 1 : -1;
      } else {
        return aValue < bValue ? 1 : -1;
      }
    });

    return filtered;
  }, [
    trades,
    instrumentFilter,
    directionFilter,
    dateFrom,
    dateTo,
    sortField,
    sortOrder,
  ]);

  const handleClearFilters = () => {
    setInstrumentFilter('all');
    setDirectionFilter('all');
    setDateFrom('');
    setDateTo('');
  };

  const handleExportCSV = () => {
    const headers = [
      'Entry Time',
      'Exit Time',
      'Instrument',
      'Direction',
      'Units',
      'Entry Price',
      'Exit Price',
      'P&L',
      'Realized P&L',
      'Duration (ms)',
    ];

    const csvRows = [
      headers.join(','),
      ...filteredTrades.map((trade) =>
        [
          trade.entry_time,
          trade.exit_time,
          trade.instrument,
          trade.direction,
          trade.units,
          trade.entry_price,
          trade.exit_price,
          trade.pnl,
          trade.realized_pnl || '',
          new Date(trade.exit_time).getTime() -
            new Date(trade.entry_time).getTime(),
        ].join(',')
      ),
    ];

    const csvContent = csvRows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute(
      'download',
      `trade_history_${new Date().toISOString().split('T')[0]}.csv`
    );
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const formatDuration = (entryTime: string, exitTime: string): string => {
    const durationMs =
      new Date(exitTime).getTime() - new Date(entryTime).getTime();
    const seconds = Math.floor(durationMs / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) {
      return `${days}d ${hours % 24}h`;
    } else if (hours > 0) {
      return `${hours}h ${minutes % 60}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    } else {
      return `${seconds}s`;
    }
  };

  const columns: Column<Trade>[] = [
    {
      id: 'entry_time',
      label: 'Entry Time',
      sortable: true,
      minWidth: 180,
      render: (row) => (
        <Typography variant="body2" sx={{ whiteSpace: 'nowrap' }}>
          {new Date(row.entry_time).toLocaleString()}
        </Typography>
      ),
    },
    {
      id: 'exit_time',
      label: 'Exit Time',
      sortable: true,
      minWidth: 180,
      render: (row) => (
        <Typography variant="body2" sx={{ whiteSpace: 'nowrap' }}>
          {new Date(row.exit_time).toLocaleString()}
        </Typography>
      ),
    },
    {
      id: 'instrument',
      label: 'Instrument',
      sortable: true,
      filterable: true,
      minWidth: 100,
      render: (row) => (
        <Typography variant="body2" fontWeight="medium">
          {row.instrument}
        </Typography>
      ),
    },
    {
      id: 'direction',
      label: 'Direction',
      sortable: true,
      filterable: true,
      minWidth: 100,
      align: 'center',
      render: (row) => (
        <Chip
          label={row.direction.toUpperCase()}
          size="small"
          color={row.direction === 'long' ? 'success' : 'error'}
          sx={{ fontWeight: 'bold', minWidth: 60 }}
        />
      ),
    },
    {
      id: 'units',
      label: 'Units',
      sortable: true,
      minWidth: 100,
      align: 'right',
      render: (row) => (
        <Typography variant="body2" fontFamily="monospace">
          {row.units.toLocaleString()}
        </Typography>
      ),
    },
    {
      id: 'entry_price',
      label: 'Entry Price',
      sortable: true,
      minWidth: 110,
      align: 'right',
      render: (row) => (
        <Typography variant="body2" fontFamily="monospace">
          {row.entry_price.toFixed(5)}
        </Typography>
      ),
    },
    {
      id: 'exit_price',
      label: 'Exit Price',
      sortable: true,
      minWidth: 110,
      align: 'right',
      render: (row) => (
        <Typography variant="body2" fontFamily="monospace">
          {row.exit_price.toFixed(5)}
        </Typography>
      ),
    },
    {
      id: 'pnl',
      label: 'P&L',
      sortable: true,
      minWidth: 110,
      align: 'right',
      render: (row) => (
        <Typography
          variant="body2"
          fontWeight="bold"
          fontFamily="monospace"
          sx={{
            color: row.pnl >= 0 ? 'success.main' : 'error.main',
          }}
        >
          {row.pnl >= 0 ? '+' : ''}
          {formatCurrency(row.pnl)}
        </Typography>
      ),
    },
    {
      id: 'duration',
      label: 'Duration',
      sortable: true,
      minWidth: 100,
      align: 'right',
      render: (row) => (
        <Typography variant="body2" fontFamily="monospace">
          {formatDuration(row.entry_time, row.exit_time)}
        </Typography>
      ),
    },
  ];

  const activeFiltersCount = [
    instrumentFilter !== 'all',
    directionFilter !== 'all',
    dateFrom !== '',
    dateTo !== '',
  ].filter(Boolean).length;

  return (
    <Card>
      <CardContent>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 2,
          }}
        >
          <Typography variant="h6">Trade History</Typography>

          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title={showFilters ? 'Hide Filters' : 'Show Filters'}>
              <IconButton
                onClick={() => setShowFilters(!showFilters)}
                size="small"
              >
                <FilterIcon />
                {activeFiltersCount > 0 && (
                  <Chip
                    label={activeFiltersCount}
                    size="small"
                    color="primary"
                    sx={{
                      position: 'absolute',
                      top: -5,
                      right: -5,
                      height: 18,
                      minWidth: 18,
                    }}
                  />
                )}
              </IconButton>
            </Tooltip>

            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              onClick={handleExportCSV}
              disabled={filteredTrades.length === 0}
              size="small"
            >
              Export CSV
            </Button>
          </Box>
        </Box>

        {/* Filters */}
        {showFilters && (
          <Box
            sx={{ mb: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}
          >
            <Stack spacing={2}>
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <FormControl size="small" sx={{ minWidth: 150 }}>
                  <InputLabel>Instrument</InputLabel>
                  <Select
                    value={instrumentFilter}
                    label="Instrument"
                    onChange={(e) => setInstrumentFilter(e.target.value)}
                  >
                    <MenuItem value="all">All Instruments</MenuItem>
                    {instruments.map((inst) => (
                      <MenuItem key={inst} value={inst}>
                        {inst}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <FormControl size="small" sx={{ minWidth: 150 }}>
                  <InputLabel>Direction</InputLabel>
                  <Select
                    value={directionFilter}
                    label="Direction"
                    onChange={(e) =>
                      setDirectionFilter(e.target.value as DirectionFilter)
                    }
                  >
                    <MenuItem value="all">All Directions</MenuItem>
                    <MenuItem value="long">Long</MenuItem>
                    <MenuItem value="short">Short</MenuItem>
                  </Select>
                </FormControl>

                <TextField
                  label="From Date"
                  type="date"
                  size="small"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  sx={{ minWidth: 150 }}
                />

                <TextField
                  label="To Date"
                  type="date"
                  size="small"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  sx={{ minWidth: 150 }}
                />

                <FormControl size="small" sx={{ minWidth: 150 }}>
                  <InputLabel>Sort By</InputLabel>
                  <Select
                    value={sortField}
                    label="Sort By"
                    onChange={(e) => setSortField(e.target.value as SortField)}
                  >
                    <MenuItem value="entry_time">Entry Time</MenuItem>
                    <MenuItem value="exit_time">Exit Time</MenuItem>
                    <MenuItem value="pnl">P&L</MenuItem>
                    <MenuItem value="duration">Duration</MenuItem>
                  </Select>
                </FormControl>

                <FormControl size="small" sx={{ minWidth: 120 }}>
                  <InputLabel>Order</InputLabel>
                  <Select
                    value={sortOrder}
                    label="Order"
                    onChange={(e) => setSortOrder(e.target.value as SortOrder)}
                  >
                    <MenuItem value="asc">Ascending</MenuItem>
                    <MenuItem value="desc">Descending</MenuItem>
                  </Select>
                </FormControl>

                {activeFiltersCount > 0 && (
                  <Button
                    variant="outlined"
                    startIcon={<ClearIcon />}
                    onClick={handleClearFilters}
                    size="small"
                  >
                    Clear Filters
                  </Button>
                )}
              </Box>

              <Typography variant="body2" color="text.secondary">
                Showing {filteredTrades.length} of {trades.length} trades
              </Typography>
            </Stack>
          </Box>
        )}

        <DataTable<Trade>
          columns={columns}
          data={filteredTrades}
          rowsPerPageOptions={[10, 25, 50, 100]}
          defaultRowsPerPage={25}
          emptyMessage="No trades available"
          stickyHeader
        />
      </CardContent>
    </Card>
  );
};
