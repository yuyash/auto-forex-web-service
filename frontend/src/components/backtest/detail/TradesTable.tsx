/**
 * TradesTable Component
 *
 * Displays trade logs in table format with sorting and pagination.
 * Fetches from GET /executions/<execution_id>/trades/ using generated client.
 *
 * Requirements: 11.7
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Chip, Typography } from '@mui/material';
import DataTable, { type Column } from '../../common/DataTable';
import { ExecutionsService } from '../../../api/generated/services/ExecutionsService';
import { useToast } from '../../common';

type TradeDirection = 'buy' | 'sell';

interface Trade {
  id: number;
  timestamp: string;
  sequence: number;
  instrument: string;
  direction: TradeDirection;
  units: number;
  price: number;
  pnl?: number;
  commission?: number;
  reason?: string;
}

interface TradesTableProps {
  executionId: number;
  enableRealTimeUpdates?: boolean;
}

/**
 * TradesTable Component
 *
 * Displays trade history for an execution with sorting and pagination.
 *
 * @param executionId - The execution ID to fetch trades for
 * @param enableRealTimeUpdates - Enable automatic refresh every 5 seconds
 */
export const TradesTable: React.FC<TradesTableProps> = ({
  executionId,
  enableRealTimeUpdates = false,
}) => {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const { showError } = useToast();

  const fetchTrades = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await ExecutionsService.getExecutionTrades(executionId);
      setTrades(response.trades || []);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load trades';
      setError(new Error(errorMessage));
      showError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [executionId, showError]);

  useEffect(() => {
    fetchTrades();
  }, [executionId, fetchTrades]);

  const formatTimestamp = (timestamp: string): string => {
    return new Date(timestamp).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const formatCurrency = (value: number | undefined): string => {
    if (value === undefined) return '-';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatPrice = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 5,
      maximumFractionDigits: 5,
    }).format(value);
  };

  const getDirectionColor = (
    direction: TradeDirection
  ): 'success' | 'error' => {
    return direction === 'buy' ? 'success' : 'error';
  };

  const getPnLColor = (pnl: number | undefined): string => {
    if (pnl === undefined) return 'text.primary';
    return pnl >= 0 ? 'success.main' : 'error.main';
  };

  const columns: Column<Trade>[] = [
    {
      id: 'sequence',
      label: 'Seq',
      sortable: true,
      align: 'right',
      minWidth: 80,
    },
    {
      id: 'timestamp',
      label: 'Timestamp',
      sortable: true,
      minWidth: 200,
      render: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          {formatTimestamp(row.timestamp)}
        </Typography>
      ),
    },
    {
      id: 'instrument',
      label: 'Instrument',
      sortable: true,
      filterable: true,
      minWidth: 120,
      render: (row) => (
        <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
          {row.instrument}
        </Typography>
      ),
    },
    {
      id: 'direction',
      label: 'Direction',
      sortable: true,
      minWidth: 100,
      render: (row) => (
        <Chip
          label={row.direction.toUpperCase()}
          size="small"
          color={getDirectionColor(row.direction)}
        />
      ),
    },
    {
      id: 'units',
      label: 'Units',
      sortable: true,
      align: 'right',
      minWidth: 100,
      render: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          {row.units.toLocaleString()}
        </Typography>
      ),
    },
    {
      id: 'price',
      label: 'Price',
      sortable: true,
      align: 'right',
      minWidth: 120,
      render: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          {formatPrice(row.price)}
        </Typography>
      ),
    },
    {
      id: 'pnl',
      label: 'P&L',
      sortable: true,
      align: 'right',
      minWidth: 120,
      render: (row) => (
        <Typography
          variant="body2"
          sx={{
            fontFamily: 'monospace',
            fontWeight: 'medium',
            color: getPnLColor(row.pnl),
          }}
        >
          {formatCurrency(row.pnl)}
        </Typography>
      ),
    },
    {
      id: 'commission',
      label: 'Commission',
      sortable: true,
      align: 'right',
      minWidth: 120,
      render: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          {formatCurrency(row.commission)}
        </Typography>
      ),
    },
    {
      id: 'reason',
      label: 'Reason',
      filterable: true,
      minWidth: 200,
      render: (row) => (
        <Typography variant="body2" color="text.secondary">
          {row.reason || '-'}
        </Typography>
      ),
    },
  ];

  return (
    <DataTable
      columns={columns}
      data={trades}
      isLoading={isLoading}
      error={error}
      emptyMessage="No trades found"
      enableRealTimeUpdates={enableRealTimeUpdates}
      onRefresh={fetchTrades}
      ariaLabel="Trade history table"
      defaultRowsPerPage={25}
      rowsPerPageOptions={[10, 25, 50, 100]}
    />
  );
};

export default TradesTable;
