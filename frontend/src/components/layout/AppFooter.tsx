import { useState, useEffect } from 'react';
import { Box, Chip, Stack, Tooltip } from '@mui/material';
import {
  Circle as CircleIcon,
  TrendingUp as TrendingUpIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { useAppSettings } from '../../hooks/useAppSettings';
import { healthApi } from '../../services/api';
import { useOandaAccounts } from '../../hooks/useOandaAccounts';
import { useOandaHealthStatus } from '../../hooks/useOandaHealthStatus';

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
  const [backendVersion, setBackendVersion] = useState<string>('');
  const { hasAccounts } = useOandaAccounts();
  const { data: oandaData } = useOandaHealthStatus({
    enabled: hasAccounts,
    refreshIntervalMs: appSettings.healthCheckIntervalSeconds * 1000,
    activeCheck: false,
  });

  // Fetch backend version from health endpoint
  useEffect(() => {
    const fetchBackendVersion = async () => {
      try {
        const data = await healthApi.backend();
        if (data?.version) {
          setBackendVersion(data.version);
        }
      } catch {
        // Silently ignore - version display is non-critical
      }
    };
    fetchBackendVersion();
  }, []);

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

  // Strategy status - currently not tracking active strategies
  // TODO: Implement by checking for running trading tasks
  const derivedStrategyStatus: StrategyStatus = { isActive: false };

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
          const versionMismatch =
            backendVersion !== '' && backendVersion !== __APP_VERSION__;
          const versionDetail = backendVersion
            ? `Frontend v${__APP_VERSION__} / Backend v${backendVersion}`
            : `Frontend v${__APP_VERSION__}`;
          const tooltipText = versionMismatch
            ? t('status.versionMismatch', {
                frontend: __APP_VERSION__,
                backend: backendVersion,
                defaultValue: `Version mismatch: ${versionDetail}`,
              })
            : versionDetail;
          return (
            <Tooltip title={tooltipText} arrow>
              <Chip
                icon={<InfoIcon />}
                label={`v${__APP_VERSION__}`}
                variant="outlined"
                size="small"
                sx={
                  versionMismatch
                    ? {
                        color: 'error.main',
                        borderColor: 'error.main',
                        '& .MuiChip-icon': { color: 'error.main' },
                      }
                    : undefined
                }
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
