import { useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  Stack,
  Grid,
  Divider,
  Alert,
  LinearProgress,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Pause as PauseIcon,
  HourglassEmpty as IdleIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import type { StrategyStatus as StrategyStatusType } from '../../types/strategy';
import type { Position } from '../../types/position';

interface StrategyStatusProps {
  strategyStatus: StrategyStatusType | null;
  positions?: Position[];
  loading?: boolean;
}

interface PerformanceMetrics {
  totalPnL: number;
  openPositions: number;
  activeLayers: Set<number>;
  longPositions: number;
  shortPositions: number;
  averageEntryPrice: number;
  totalUnits: number;
}

const StrategyStatus = ({
  strategyStatus,
  positions = [],
  loading = false,
}: StrategyStatusProps) => {
  const { t } = useTranslation('strategy');

  // Calculate performance metrics from positions
  const metrics = useMemo<PerformanceMetrics>(() => {
    const openPositions = positions.filter((p) => p.status === 'OPEN');
    const activeLayers = new Set(
      openPositions
        .map((p) => p.layer)
        .filter((l): l is number => l !== undefined)
    );
    const longPositions = openPositions.filter((p) => p.direction === 'LONG');
    const shortPositions = openPositions.filter((p) => p.direction === 'SHORT');

    const totalPnL = openPositions.reduce(
      (sum, p) => sum + (p.unrealized_pnl || 0),
      0
    );

    const totalUnits = openPositions.reduce((sum, p) => sum + p.units, 0);
    const weightedEntryPrice = openPositions.reduce(
      (sum, p) => sum + p.entry_price * p.units,
      0
    );
    const averageEntryPrice =
      totalUnits > 0 ? weightedEntryPrice / totalUnits : 0;

    return {
      totalPnL,
      openPositions: openPositions.length,
      activeLayers,
      longPositions: longPositions.length,
      shortPositions: shortPositions.length,
      averageEntryPrice,
      totalUnits,
    };
  }, [positions]);

  // Determine status from strategy state
  const status = strategyStatus?.state?.status || 'idle';
  const isActive = strategyStatus?.is_active ?? false;

  // Get status icon and color
  const getStatusConfig = () => {
    if (!isActive) {
      return {
        icon: <IdleIcon />,
        color: 'default' as const,
        label: t('status.idle', { defaultValue: 'Idle' }),
        severity: 'info' as const,
      };
    }

    switch (status) {
      case 'trading':
      case 'running':
        return {
          icon: <CheckCircleIcon />,
          color: 'success' as const,
          label: t('status.trading', { defaultValue: 'Trading' }),
          severity: 'success' as const,
        };
      case 'paused':
        return {
          icon: <PauseIcon />,
          color: 'warning' as const,
          label: t('status.paused', { defaultValue: 'Paused' }),
          severity: 'warning' as const,
        };
      case 'error':
        return {
          icon: <ErrorIcon />,
          color: 'error' as const,
          label: t('status.error', { defaultValue: 'Error' }),
          severity: 'error' as const,
        };
      default:
        return {
          icon: <IdleIcon />,
          color: 'default' as const,
          label: t('status.idle', { defaultValue: 'Idle' }),
          severity: 'info' as const,
        };
    }
  };

  const statusConfig = getStatusConfig();

  // Format currency
  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  // Format number
  const formatNumber = (value: number, decimals: number = 2): string => {
    return value.toFixed(decimals);
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {t('status.title', { defaultValue: 'Strategy Status' })}
          </Typography>
          <LinearProgress />
        </CardContent>
      </Card>
    );
  }

  if (!strategyStatus) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {t('status.title', { defaultValue: 'Strategy Status' })}
          </Typography>
          <Alert severity="info">
            {t('status.noStrategy', {
              defaultValue: 'No strategy configured',
            })}
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        {/* Header */}
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={2}
        >
          <Typography variant="h6">
            {t('status.title', { defaultValue: 'Strategy Status' })}
          </Typography>
          <Chip
            icon={statusConfig.icon}
            label={statusConfig.label}
            color={statusConfig.color}
            size="small"
          />
        </Box>

        {/* Status Alert */}
        <Alert severity={statusConfig.severity} sx={{ mb: 2 }}>
          <Typography variant="body2">
            {isActive
              ? t('status.activeMessage', {
                  defaultValue:
                    'Strategy is currently active and monitoring the market',
                })
              : t('status.inactiveMessage', {
                  defaultValue: 'Strategy is not active',
                })}
          </Typography>
          {strategyStatus.strategy_type && (
            <Typography variant="caption" color="text.secondary">
              {t('status.strategyType', {
                defaultValue: 'Type: {{type}}',
                type: strategyStatus.strategy_type,
              })}
            </Typography>
          )}
        </Alert>

        <Divider sx={{ my: 2 }} />

        {/* Performance Metrics */}
        <Typography variant="subtitle2" gutterBottom>
          {t('status.performance', { defaultValue: 'Performance Metrics' })}
        </Typography>

        <Grid container spacing={2} sx={{ mb: 2 }}>
          {/* Total P&L */}
          <Grid size={{ xs: 6, sm: 3 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('status.totalPnL', { defaultValue: 'Total P&L' })}
              </Typography>
              <Box display="flex" alignItems="center" gap={0.5}>
                {metrics.totalPnL >= 0 ? (
                  <TrendingUpIcon fontSize="small" color="success" />
                ) : (
                  <TrendingDownIcon fontSize="small" color="error" />
                )}
                <Typography
                  variant="h6"
                  color={metrics.totalPnL >= 0 ? 'success.main' : 'error.main'}
                >
                  {formatCurrency(metrics.totalPnL)}
                </Typography>
              </Box>
            </Box>
          </Grid>

          {/* Open Positions */}
          <Grid size={{ xs: 6, sm: 3 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('status.openPositions', { defaultValue: 'Open Positions' })}
              </Typography>
              <Typography variant="h6">{metrics.openPositions}</Typography>
            </Box>
          </Grid>

          {/* Active Layers */}
          <Grid size={{ xs: 6, sm: 3 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('status.activeLayers', { defaultValue: 'Active Layers' })}
              </Typography>
              <Typography variant="h6">{metrics.activeLayers.size}</Typography>
            </Box>
          </Grid>

          {/* Total Units */}
          <Grid size={{ xs: 6, sm: 3 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('status.totalUnits', { defaultValue: 'Total Units' })}
              </Typography>
              <Typography variant="h6">
                {formatNumber(metrics.totalUnits, 0)}
              </Typography>
            </Box>
          </Grid>
        </Grid>

        <Divider sx={{ my: 2 }} />

        {/* Position Breakdown */}
        <Typography variant="subtitle2" gutterBottom>
          {t('status.positions', { defaultValue: 'Positions' })}
        </Typography>

        <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
          <Box flex={1}>
            <Typography variant="caption" color="text.secondary">
              {t('status.longPositions', { defaultValue: 'Long' })}
            </Typography>
            <Typography variant="body1" color="success.main">
              {metrics.longPositions}
            </Typography>
          </Box>
          <Box flex={1}>
            <Typography variant="caption" color="text.secondary">
              {t('status.shortPositions', { defaultValue: 'Short' })}
            </Typography>
            <Typography variant="body1" color="error.main">
              {metrics.shortPositions}
            </Typography>
          </Box>
          {metrics.averageEntryPrice > 0 && (
            <Box flex={1}>
              <Typography variant="caption" color="text.secondary">
                {t('status.avgEntry', { defaultValue: 'Avg Entry' })}
              </Typography>
              <Typography variant="body1">
                {formatNumber(metrics.averageEntryPrice, 5)}
              </Typography>
            </Box>
          )}
        </Stack>

        {/* Active Layers Display */}
        {metrics.activeLayers.size > 0 && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" gutterBottom>
              {t('status.layersTitle', { defaultValue: 'Active Layers' })}
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {Array.from(metrics.activeLayers)
                .sort((a, b) => a - b)
                .map((layer) => {
                  const layerPositions = positions.filter(
                    (p) => p.layer === layer && p.status === 'OPEN'
                  );
                  const layerPnL = layerPositions.reduce(
                    (sum, p) => sum + (p.unrealized_pnl || 0),
                    0
                  );

                  return (
                    <Chip
                      key={layer}
                      label={`Layer ${layer}: ${formatCurrency(layerPnL)}`}
                      size="small"
                      color={layerPnL >= 0 ? 'success' : 'error'}
                      variant="outlined"
                    />
                  );
                })}
            </Stack>
          </>
        )}

        {/* Last Update Time */}
        {strategyStatus.state?.last_tick_time && (
          <Box mt={2}>
            <Typography variant="caption" color="text.secondary">
              {t('status.lastUpdate', { defaultValue: 'Last Update' })}:{' '}
              {new Date(strategyStatus.state.last_tick_time).toLocaleString()}
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default StrategyStatus;
