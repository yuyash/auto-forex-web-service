import React, { useState, useEffect, useCallback } from 'react';
import { Paper, Typography, Box, Button, Chip } from '@mui/material';
import { Stop as StopIcon } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import DataTable, { type Column } from '../common/DataTable';
import ConfirmDialog from '../common/ConfirmDialog';
import type { RunningStrategy } from '../../types/admin';

interface RunningStrategyListProps {
  strategies: RunningStrategy[];
  onStop: (strategyId: number) => void;
  onRefresh?: () => void;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

const RunningStrategyList: React.FC<RunningStrategyListProps> = ({
  strategies,
  onStop,
  onRefresh,
  autoRefresh = true,
  refreshInterval = 5000,
}) => {
  const { t } = useTranslation('admin');
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    strategyId: number | null;
    strategyName: string;
    username: string;
  }>({
    open: false,
    strategyId: null,
    strategyName: '',
    username: '',
  });

  // Auto-refresh every 5 seconds (default)
  const handleRefresh = useCallback(() => {
    if (onRefresh) {
      onRefresh();
    }
  }, [onRefresh]);

  useEffect(() => {
    if (!autoRefresh || !onRefresh) {
      return;
    }

    const intervalId = setInterval(() => {
      handleRefresh();
    }, refreshInterval);

    return () => {
      clearInterval(intervalId);
    };
  }, [autoRefresh, refreshInterval, handleRefresh, onRefresh]);

  const handleStopClick = (
    strategyId: number,
    strategyName: string,
    username: string
  ) => {
    setConfirmDialog({
      open: true,
      strategyId,
      strategyName,
      username,
    });
  };

  const handleConfirmStop = () => {
    if (confirmDialog.strategyId) {
      onStop(confirmDialog.strategyId);
    }
    setConfirmDialog({
      open: false,
      strategyId: null,
      strategyName: '',
      username: '',
    });
  };

  const handleCancelStop = () => {
    setConfirmDialog({
      open: false,
      strategyId: null,
      strategyName: '',
      username: '',
    });
  };

  const formatDateTime = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const getRunningTime = (startTime: string): string => {
    const now = new Date();
    const start = new Date(startTime);
    const diffMs = now.getTime() - start.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 60)
      return t('strategies.minutesRunning', { count: diffMins });
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24)
      return t('strategies.hoursRunning', { count: diffHours });
    const diffDays = Math.floor(diffHours / 24);
    return t('strategies.daysRunning', { count: diffDays });
  };

  const getPnLColor = (pnl: number): string => {
    if (pnl > 0) return 'success.main';
    if (pnl < 0) return 'error.main';
    return 'text.secondary';
  };

  const formatPnL = (pnl: number): string => {
    const sign = pnl >= 0 ? '+' : '';
    return `${sign}${pnl.toFixed(2)}`;
  };

  const columns: Column<RunningStrategy & Record<string, unknown>>[] = [
    {
      id: 'username',
      label: t('strategies.username'),
      sortable: true,
      filterable: true,
      minWidth: 120,
    },
    {
      id: 'account_id',
      label: t('strategies.account'),
      sortable: true,
      filterable: true,
      minWidth: 150,
    },
    {
      id: 'strategy_name',
      label: t('strategies.strategyName'),
      sortable: true,
      filterable: true,
      minWidth: 150,
    },
    {
      id: 'instruments',
      label: t('strategies.instruments'),
      render: (row) => (
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
          {row.instruments.map((instrument: string) => (
            <Chip
              key={instrument}
              label={instrument}
              size="small"
              variant="outlined"
            />
          ))}
        </Box>
      ),
      minWidth: 200,
    },
    {
      id: 'start_time',
      label: t('strategies.startTime'),
      sortable: true,
      render: (row) => (
        <Box>
          <Typography variant="body2">
            {formatDateTime(row.start_time)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {getRunningTime(row.start_time)}
          </Typography>
        </Box>
      ),
      minWidth: 180,
    },
    {
      id: 'position_count',
      label: t('strategies.positions'),
      sortable: true,
      align: 'center',
      render: (row) => (
        <Chip
          label={row.position_count}
          color={row.position_count > 0 ? 'primary' : 'default'}
          size="small"
          sx={{ fontWeight: 'bold' }}
        />
      ),
      minWidth: 100,
    },
    {
      id: 'unrealized_pnl',
      label: t('strategies.unrealizedPnL'),
      sortable: true,
      align: 'right',
      render: (row) => (
        <Typography
          variant="body2"
          sx={{
            color: getPnLColor(row.unrealized_pnl),
            fontWeight: 'bold',
          }}
        >
          {formatPnL(row.unrealized_pnl)}
        </Typography>
      ),
      minWidth: 120,
    },
    {
      id: 'actions',
      label: '',
      align: 'center',
      render: (row) => (
        <Button
          variant="outlined"
          color="error"
          size="small"
          startIcon={<StopIcon />}
          onClick={(e) => {
            e.stopPropagation();
            handleStopClick(row.id, row.strategy_name, row.username);
          }}
        >
          {t('strategies.stop')}
        </Button>
      ),
      minWidth: 120,
    },
  ];

  // Calculate total P&L
  const totalPnL = strategies.reduce((sum, s) => sum + s.unrealized_pnl, 0);

  return (
    <>
      <Paper elevation={2} sx={{ p: 3, height: '100%' }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mb: 2,
          }}
        >
          <Typography variant="h6">{t('strategies.title')}</Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Chip
              label={strategies.length}
              color="primary"
              size="small"
              sx={{ fontWeight: 'bold' }}
            />
            {strategies.length > 0 && (
              <Chip
                label={formatPnL(totalPnL)}
                color={totalPnL >= 0 ? 'success' : 'error'}
                size="small"
                sx={{ fontWeight: 'bold' }}
              />
            )}
          </Box>
        </Box>

        {strategies.length === 0 ? (
          <Box
            sx={{
              py: 4,
              textAlign: 'center',
            }}
          >
            <Typography variant="body2" color="text.secondary">
              {t('strategies.noStrategies')}
            </Typography>
          </Box>
        ) : (
          <DataTable
            columns={columns}
            data={strategies as (RunningStrategy & Record<string, unknown>)[]}
            emptyMessage={t('strategies.noStrategies')}
            defaultRowsPerPage={5}
            rowsPerPageOptions={[5, 10, 25]}
            stickyHeader={false}
          />
        )}
      </Paper>

      <ConfirmDialog
        open={confirmDialog.open}
        title={t('strategies.confirmStopTitle')}
        message={t('strategies.confirmStopMessage', {
          strategyName: confirmDialog.strategyName,
          username: confirmDialog.username,
        })}
        onConfirm={handleConfirmStop}
        onCancel={handleCancelStop}
        confirmText={t('strategies.stop')}
        cancelText={t('common.cancel')}
        confirmColor="warning"
      />
    </>
  );
};

export default RunningStrategyList;
