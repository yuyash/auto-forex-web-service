import { Box, Chip, Stack, Tooltip } from '@mui/material';
import {
  Circle as CircleIcon,
  TrendingUp as TrendingUpIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { useAppSettings } from '../../hooks/useAppSettings';
import { useBackendHealth } from '../../hooks/useBackendHealth';
import { useOandaAccounts } from '../../hooks/useOandaAccounts';
import { useOandaHealthStatus } from '../../hooks/useOandaHealthStatus';
import { useTradingTasks } from '../../hooks/useTradingTasks';
import { TaskStatus } from '../../types/common';

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
  const { hasAccounts } = useOandaAccounts();
  const { data: backendHealth } = useBackendHealth();
  const { data: oandaData } = useOandaHealthStatus({
    enabled: hasAccounts,
    refreshIntervalMs: appSettings.healthCheckIntervalSeconds * 1000,
    activeCheck: false,
  });
  const { data: activeTradingTasks } = useTradingTasks({
    page: 1,
    page_size: 3,
    status: TaskStatus.RUNNING,
  });

  const backendVersion = backendHealth?.version ?? '';

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

  // Derive connection status from OANDA health
  const derivedConnectionStatus: OandaConnectionState =
    oandaHealth === null ? 'checking' : oandaHealth.state;

  // Format last checked time for tooltip
  const formatLastChecked = (date?: Date): string => {
    if (!date) return 'Never';
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  };

  // Build tooltip text for connection status
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
        {/* Version Info */}
        {(() => {
          const versionLabel = backendVersion
            ? `v${__APP_VERSION__} / v${backendVersion}`
            : `v${__APP_VERSION__}`;
          const tooltipText = backendVersion
            ? `Frontend v${__APP_VERSION__} / Backend v${backendVersion}`
            : `Frontend v${__APP_VERSION__}`;
          return (
            <Tooltip title={tooltipText} arrow>
              <Chip
                icon={<InfoIcon />}
                label={versionLabel}
                variant="outlined"
                size="small"
              />
            </Tooltip>
          );
        })()}

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
