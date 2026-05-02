import { Box, Chip, Stack, Tooltip } from '@mui/material';
import {
  Circle as CircleIcon,
  TrendingUp as TrendingUpIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { useAppSettings } from '../../hooks/useAppSettings';
import { useOandaAccounts } from '../../hooks/useOandaAccounts';
import { useOandaHealthStatus } from '../../hooks/useOandaHealthStatus';
import { useTradingTasks } from '../../hooks/useTradingTasks';
import { TaskStatus } from '../../types/common';
import { usePollingPolicy } from '../../hooks/usePollingPolicy';
import { useSequentialPolling } from '../../hooks/useSequentialPolling';
import { useDateTimeFormatter } from '../../hooks/useDateTimeFormatter';

interface StrategyStatus {
  isActive: boolean;
  strategyName?: string;
}

type OandaConnectionState = 'connected' | 'disconnected' | 'checking' | 'empty';

interface OandaHealthStatus {
  state: OandaConnectionState;
  message: string;
  lastChecked?: Date;
}

const AppFooter = () => {
  const { t } = useTranslation('common');
  const { settings: appSettings } = useAppSettings();
  const { formatDateTime } = useDateTimeFormatter();
  const { hasAccounts } = useOandaAccounts();
  const { data: oandaData } = useOandaHealthStatus({
    enabled: hasAccounts,
    refreshIntervalMs: appSettings.healthCheckIntervalSeconds * 1000,
    activeCheck: false,
  });
  const { data: activeTradingTasks, refresh: refreshTradingTasks } =
    useTradingTasks({
      page: 1,
      page_size: 3,
      status: TaskStatus.RUNNING,
    });

  // Poll for active trading task updates
  const hasActiveTasks =
    activeTradingTasks != null && activeTradingTasks.count > 0;
  const footerPollingPolicy = usePollingPolicy({
    enabled: hasActiveTasks,
    baseIntervalMs: 15_000,
  });

  useSequentialPolling(
    async () => {
      await refreshTradingTasks();
    },
    {
      enabled: footerPollingPolicy.isActive,
      intervalMs: footerPollingPolicy.intervalMs,
    }
  );

  const oandaHealth: OandaHealthStatus | null = !hasAccounts
    ? {
        state: 'empty',
        message: t('status.noOandaAccount'),
      }
    : oandaData?.status && typeof oandaData.status === 'object'
      ? (() => {
          const status = oandaData.status as {
            is_available?: unknown;
            error_message?: unknown;
            checked_at?: unknown;
          };
          const isAvailable = !!status.is_available;

          return {
            state: isAvailable ? 'connected' : 'disconnected',
            message: isAvailable
              ? 'OANDA API is reachable'
              : String(status.error_message ?? 'OANDA API is unavailable'),
            lastChecked:
              typeof status.checked_at === 'string'
                ? new Date(status.checked_at)
                : undefined,
          };
        })()
      : null;

  const derivedConnectionStatus: OandaConnectionState =
    oandaHealth === null ? 'checking' : oandaHealth.state;

  const formatLastChecked = (date?: Date): string => {
    if (!date) return 'Never';
    return formatDateTime(date, {
      includeSeconds: true,
      includeTimezone: true,
    });
  };

  const connectionTooltip = oandaHealth
    ? `${oandaHealth.message}\nLast checked: ${formatLastChecked(oandaHealth.lastChecked)}`
    : 'Checking connection...';

  const derivedStrategyStatus: StrategyStatus =
    activeTradingTasks && activeTradingTasks.count > 0
      ? {
          isActive: true,
          strategyName:
            activeTradingTasks.count === 1 && activeTradingTasks.results[0]
              ? activeTradingTasks.results[0].name
              : t('status.activeTasks', {
                  count: activeTradingTasks.count,
                  defaultValue: `${activeTradingTasks.count} active tasks`,
                }),
        }
      : { isActive: false };

  return (
    <Box
      component="footer"
      sx={{
        py: 0.75,
        px: 2,
        mt: 'auto',
        backgroundColor: (theme) =>
          theme.palette.mode === 'light'
            ? theme.palette.grey[200]
            : theme.palette.grey[800],
        borderTop: (theme) => `1px solid ${theme.palette.divider}`,
      }}
    >
      <Stack
        direction="row"
        spacing={2}
        alignItems="center"
        justifyContent="flex-start"
        flexWrap="wrap"
      >
        {/* Connection Status */}
        <Tooltip title={connectionTooltip} arrow>
          <Chip
            icon={<CircleIcon />}
            label={
              derivedConnectionStatus === 'connected'
                ? t('status.connected')
                : derivedConnectionStatus === 'checking'
                  ? 'Checking...'
                  : derivedConnectionStatus === 'empty'
                    ? t('status.noOandaAccount')
                    : t('status.disconnected')
            }
            color={
              derivedConnectionStatus === 'connected'
                ? 'success'
                : derivedConnectionStatus === 'checking'
                  ? 'default'
                  : derivedConnectionStatus === 'empty'
                    ? 'default'
                    : 'error'
            }
            sx={{
              '& .MuiChip-icon': {
                fontSize: '0.75rem',
              },
            }}
          />
        </Tooltip>

        {/* Strategy Status */}
        <Chip
          icon={<TrendingUpIcon />}
          label={
            derivedStrategyStatus.isActive
              ? `${t('status.active')}: ${derivedStrategyStatus.strategyName || 'Strategy'}`
              : t('status.inactive')
          }
          color={derivedStrategyStatus.isActive ? 'primary' : 'default'}
        />
      </Stack>
    </Box>
  );
};

export default AppFooter;
