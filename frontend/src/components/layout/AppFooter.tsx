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

interface OandaHealthStatus {
  healthy: boolean;
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

    const checkHealth = async () => {
      try {
        const response = await fetch('/api/health/oanda/', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const data = await response.json();
          setOandaHealth({
            healthy: data.healthy,
            message: data.message,
            lastChecked: new Date(),
          });
        } else {
          setOandaHealth({
            healthy: false,
            message: 'Failed to check OANDA health',
            lastChecked: new Date(),
          });
        }
      } catch (error) {
        console.error('Error checking OANDA health:', error);
        setOandaHealth({
          healthy: false,
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
  }, [token]);

  // Derive connection status from OANDA health
  const derivedConnectionStatus: 'connected' | 'disconnected' | 'checking' =
    oandaHealth === null
      ? 'checking'
      : oandaHealth.healthy
        ? 'connected'
        : 'disconnected';

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
        py: 1.5,
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
        spacing={3}
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
                  : t('status.disconnected')
            }
            color={
              derivedConnectionStatus === 'connected'
                ? 'success'
                : derivedConnectionStatus === 'checking'
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
