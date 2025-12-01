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
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
} from '@mui/icons-material';

interface Position {
  id: number;
  instrument: string;
  direction: 'long' | 'short';
  units: number;
  entry_price: string;
  current_price: string;
  unrealized_pnl: string;
  entry_time: string;
}

interface OpenPositionsTableProps {
  taskId: number;
}

export function OpenPositionsTable({ taskId }: OpenPositionsTableProps) {
  const [positions] = useState<Position[]>([]);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  useEffect(() => {
    const interval = setInterval(() => {
      setLastUpdate(new Date());
    }, 5000);

    return () => clearInterval(interval);
  }, [taskId]);

  const formatDuration = (entryTime: string) => {
    const entry = new Date(entryTime);
    const now = new Date();
    const diff = now.getTime() - entry.getTime();

    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else {
      return `${minutes}m`;
    }
  };

  if (positions.length === 0) {
    return (
      <Alert severity="info">
        No open positions. The strategy will open positions when trading
        conditions are met.
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
              <TableCell>Instrument</TableCell>
              <TableCell>Direction</TableCell>
              <TableCell align="right">Units</TableCell>
              <TableCell align="right">Entry Price</TableCell>
              <TableCell align="right">Current Price</TableCell>
              <TableCell align="right">Unrealized P&L</TableCell>
              <TableCell align="right">Duration</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {positions.map((position) => {
              const pnl = parseFloat(position.unrealized_pnl);
              const isProfitable = pnl >= 0;

              return (
                <TableRow key={position.id} hover>
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {position.instrument.replace('_', '/')}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={position.direction.toUpperCase()}
                      size="small"
                      color={
                        position.direction === 'long' ? 'success' : 'error'
                      }
                      icon={
                        position.direction === 'long' ? (
                          <TrendingUpIcon />
                        ) : (
                          <TrendingDownIcon />
                        )
                      }
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2">
                      {position.units.toLocaleString()}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2">
                      {parseFloat(position.entry_price).toFixed(4)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" fontWeight="medium">
                      {parseFloat(position.current_price).toFixed(4)}
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
                      {formatDuration(position.entry_time)}
                    </Typography>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between' }}>
        <Typography variant="body2" color="text.secondary">
          Total Open Positions: {positions.length}
        </Typography>
        <Typography
          variant="body2"
          fontWeight="bold"
          color={
            positions.reduce(
              (sum, p) => sum + parseFloat(p.unrealized_pnl),
              0
            ) >= 0
              ? 'success.main'
              : 'error.main'
          }
        >
          Total Unrealized P&L: $
          {positions
            .reduce((sum, p) => sum + parseFloat(p.unrealized_pnl), 0)
            .toFixed(2)}
        </Typography>
      </Box>
    </Box>
  );
}
