import { useState, useEffect } from 'react';
import { Box, Chip, Stack, Tooltip } from '@mui/material';
import {
  Circle as CircleIcon,
  TrendingUp as TrendingUpIcon,
  Schedule as ScheduleIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';

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
  const { user, token } = useAuth();
  const [currentTime, setCurrentTime] = useState<string>('');
  const [oandaHealth, setOandaHealth] = useState<OandaHealthStatus | null>(
    null
  );

  // Update current time in user's timezone
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const timezone = user?.timezone || 'UTC';

      try {
        const timeString = now.toLocaleTimeString('en-US', {
          timeZone: timezone,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        });
        setCurrentTime(timeString);
      } catch {
        // Fallback to UTC if timezone is invalid
        const timeString = now.toLocaleTimeString('en-US', {
          timeZone: 'UTC',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        });
        setCurrentTime(timeString);
      }
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);

    return () => clearInterval(interval);
  }, [user?.timezone]);

  // Check OANDA API health periodically
  useEffect(() => {
    // Early return if no token - don't set state
    if (!token) {
      return;
    }

    const checkAccountExists = async (): Promise<boolean> => {
      try {
        const response = await fetch('/api/market/accounts/', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          return false;
        }

        const data = await response.json().catch(() => null);
        
        // Check if accounts array exists and has at least one account
        if (data && typeof data === 'object' && 'results' in data) {
          const results = (data as { results?: unknown }).results;
          return Array.isArray(results) && results.length > 0;
        }
        
        // If response is an array directly
        return Array.isArray(data) && data.length > 0;
      } catch {
        return false;
      }
    };

    const fetchLatest = async () => {
      const response = await fetch('/api/market/health/oanda/', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await response.json().catch(() => null as unknown);

      return { response, data };
    };

    const runCheck = async () => {
      const response = await fetch('/api/market/health/oanda/', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await response.json().catch(() => null as unknown);

      return { response, data };
    };

    const checkHealth = async () => {
      try {
        // First check if any OANDA account exists
        const hasAccount = await checkAccountExists();
        
        if (!hasAccount) {
          setOandaHealth({
            state: 'empty',
            message: t('status.noOandaAccount'),
          });
          return;
        }

        const { response: latestResp, data: latestData } = await fetchLatest();

        if (!latestResp.ok) {
          setOandaHealth({
            state: 'disconnected',
            message: 'Failed to check OANDA health',
            lastChecked: new Date(),
          });
          return;
        }

        // Backend shape: { account: {...}, status: {...} | null }
        const status =
          latestData && typeof latestData === 'object' && 'status' in latestData
            ? (latestData as { status?: unknown }).status
            : null;

        // If there's no prior status, trigger a live check via POST.
        if (!status) {
          const { response: checkResp, data: checkData } = await runCheck();
          if (!checkResp.ok) {
            setOandaHealth({
              state: 'disconnected',
              message: 'Failed to check OANDA health',
              lastChecked: new Date(),
            });
            return;
          }

          const checkedStatus =
            checkData && typeof checkData === 'object' && 'status' in checkData
              ? (checkData as { status?: unknown }).status
              : null;

          if (!checkedStatus || typeof checkedStatus !== 'object') {
            setOandaHealth({
              state: 'disconnected',
              message: 'Failed to check OANDA health',
              lastChecked: new Date(),
            });
            return;
          }

          const isAvailable = Boolean(
            (checkedStatus as { is_available?: unknown }).is_available
          );
          const checkedAtRaw = (checkedStatus as { checked_at?: unknown })
            .checked_at;
          const checkedAt =
            typeof checkedAtRaw === 'string'
              ? new Date(checkedAtRaw)
              : new Date();
          const errorMessage = String(
            (checkedStatus as { error_message?: unknown }).error_message ?? ''
          );

          setOandaHealth({
            state: isAvailable ? 'connected' : 'disconnected',
            message: isAvailable
              ? 'OANDA API is reachable'
              : errorMessage || 'OANDA API is unavailable',
            lastChecked: checkedAt,
          });
          return;
        }

        if (typeof status !== 'object') {
          setOandaHealth({
            state: 'disconnected',
            message: 'Failed to check OANDA health',
            lastChecked: new Date(),
          });
          return;
        }

        const checkedAtRaw = (status as { checked_at?: unknown }).checked_at;
        const checkedAt =
          typeof checkedAtRaw === 'string' ? new Date(checkedAtRaw) : undefined;
        const isStale = checkedAt
          ? Date.now() - checkedAt.getTime() > 30_000
          : true;

        if (isStale) {
          // Refresh via POST when the latest saved status is stale.
          const { response: checkResp, data: checkData } = await runCheck();
          if (
            checkResp.ok &&
            checkData &&
            typeof checkData === 'object' &&
            'status' in checkData
          ) {
            const refreshed = (checkData as { status?: unknown }).status;
            if (refreshed && typeof refreshed === 'object') {
              const isAvailable = Boolean(
                (refreshed as { is_available?: unknown }).is_available
              );
              const refreshedAtRaw = (refreshed as { checked_at?: unknown })
                .checked_at;
              const refreshedAt =
                typeof refreshedAtRaw === 'string'
                  ? new Date(refreshedAtRaw)
                  : new Date();
              const errorMessage = String(
                (refreshed as { error_message?: unknown }).error_message ?? ''
              );
              setOandaHealth({
                state: isAvailable ? 'connected' : 'disconnected',
                message: isAvailable
                  ? 'OANDA API is reachable'
                  : errorMessage || 'OANDA API is unavailable',
                lastChecked: refreshedAt,
              });
              return;
            }
          }
        }

        const isAvailable = Boolean(
          (status as { is_available?: unknown }).is_available
        );
        const errorMessage = String(
          (status as { error_message?: unknown }).error_message ?? ''
        );

        setOandaHealth({
          state: isAvailable ? 'connected' : 'disconnected',
          message: isAvailable
            ? 'OANDA API is reachable'
            : errorMessage || 'OANDA API is unavailable',
          lastChecked: checkedAt,
        });
      } catch (error) {
        console.error('Error checking OANDA health:', error);
        setOandaHealth({
          state: 'disconnected',
          message: 'Health check failed',
          lastChecked: new Date(),
        });
      }
    };

    // Check immediately
    checkHealth();

    // Check every 30 seconds
    const interval = setInterval(checkHealth, 30000);

    return () => clearInterval(interval);
  }, [token, t]);

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
        justifyContent="space-between"
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
            size="small"
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
          size="small"
        />

        {/* System Time */}
        <Chip
          icon={<ScheduleIcon />}
          label={`${currentTime}`}
          size="small"
          variant="outlined"
        />
      </Stack>
    </Box>
  );
};

export default AppFooter;
