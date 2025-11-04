import { useMemo } from 'react';
import { Box, Button, Chip, Paper, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import DownloadIcon from '@mui/icons-material/Download';
import DataTable, { type Column } from '../common/DataTable';

interface Trade extends Record<string, unknown> {
  timestamp: string;
  instrument: string;
  direction: string;
  entry_price: number;
  exit_price: number;
  units: number;
  pnl: number;
  duration: number;
}

interface TradeLogTableProps {
  trades: Trade[];
}

const TradeLogTable = ({ trades }: TradeLogTableProps) => {
  const { t } = useTranslation(['backtest', 'common']);

  // Format duration from seconds to human-readable format
  const formatDuration = (seconds: number): string => {
    if (seconds < 60) {
      return `${seconds}s`;
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = seconds % 60;
      return remainingSeconds > 0
        ? `${minutes}m ${remainingSeconds}s`
        : `${minutes}m`;
    } else if (seconds < 86400) {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
    } else {
      const days = Math.floor(seconds / 86400);
      const hours = Math.floor((seconds % 86400) / 3600);
      return hours > 0 ? `${days}d ${hours}h` : `${days}d`;
    }
  };

  // Format timestamp to readable date/time
  const formatTimestamp = (timestamp: string): string => {
    const date = new Date(timestamp);
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  // Export trades to CSV
  const exportToCSV = () => {
    const headers = [
      'Date',
      'Instrument',
      'Direction',
      'Entry Price',
      'Exit Price',
      'Units',
      'P&L',
      'Duration (seconds)',
    ];

    const csvRows = [
      headers.join(','),
      ...trades.map((trade) =>
        [
          trade.timestamp,
          trade.instrument,
          trade.direction,
          trade.entry_price,
          trade.exit_price,
          trade.units,
          trade.pnl,
          trade.duration,
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
      `trade_log_${new Date().toISOString().split('T')[0]}.csv`
    );
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Define table columns
  const columns = useMemo<Column<Trade>[]>(
    () => [
      {
        id: 'timestamp',
        label: t('backtest:tradeLog.date', 'Date'),
        sortable: true,
        filterable: true,
        minWidth: 180,
        render: (row) => (
          <Typography variant="body2" sx={{ whiteSpace: 'nowrap' }}>
            {formatTimestamp(row.timestamp)}
          </Typography>
        ),
      },
      {
        id: 'instrument',
        label: t('backtest:tradeLog.instrument', 'Instrument'),
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
        label: t('backtest:tradeLog.direction', 'Direction'),
        sortable: true,
        filterable: true,
        minWidth: 100,
        align: 'center',
        render: (row) => (
          <Chip
            label={row.direction.toUpperCase()}
            size="small"
            color={row.direction.toLowerCase() === 'long' ? 'success' : 'error'}
            sx={{ fontWeight: 'bold', minWidth: 60 }}
          />
        ),
      },
      {
        id: 'entry_price',
        label: t('backtest:tradeLog.entryPrice', 'Entry Price'),
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
        label: t('backtest:tradeLog.exitPrice', 'Exit Price'),
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
        id: 'units',
        label: t('backtest:tradeLog.units', 'Units'),
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
        id: 'pnl',
        label: t('backtest:tradeLog.pnl', 'P&L'),
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
            {row.pnl.toFixed(2)}
          </Typography>
        ),
      },
      {
        id: 'duration',
        label: t('backtest:tradeLog.duration', 'Duration'),
        sortable: true,
        minWidth: 100,
        align: 'right',
        render: (row) => (
          <Typography variant="body2" fontFamily="monospace">
            {formatDuration(row.duration)}
          </Typography>
        ),
      },
    ],
    [t]
  );

  return (
    <Paper sx={{ p: 2 }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 2,
        }}
      >
        <Typography variant="h6">
          {t('backtest:tradeLog.title', 'Trade Log')}
        </Typography>
        <Button
          variant="outlined"
          startIcon={<DownloadIcon />}
          onClick={exportToCSV}
          disabled={trades.length === 0}
          size="small"
        >
          {t('common:exportCSV', 'Export CSV')}
        </Button>
      </Box>

      <DataTable<Trade>
        columns={columns}
        data={trades}
        rowsPerPageOptions={[10, 25, 50, 100]}
        defaultRowsPerPage={25}
        emptyMessage={t(
          'backtest:tradeLog.noTrades',
          'No trades available. Run a backtest to see trade history.'
        )}
        stickyHeader
      />
    </Paper>
  );
};

export default TradeLogTable;
