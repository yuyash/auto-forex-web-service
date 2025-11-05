import { useState, useEffect } from 'react';
import { Box, Typography, Chip, Stack } from '@mui/material';
import {
  Circle as CircleIcon,
  TrendingUp as TrendingUpIcon,
  Schedule as ScheduleIcon,
  Store as StoreIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';

interface StrategyStatus {
  isActive: boolean;
  strategyName?: string;
}

const AppFooter = () => {
  const { t } = useTranslation('common');
  const { user, token } = useAuth();
  const [connectionStatus, setConnectionStatus] = useState<
    'connected' | 'disconnected'
  >('disconnected');
  const [strategyStatus, setStrategyStatus] = useState<StrategyStatus>({
    isActive: false,
  });
  const [currentTime, setCurrentTime] = useState<string>('');
  const [marketStatus, setMarketStatus] = useState<'open' | 'closed'>('closed');

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

  // Check OANDA API connection status
  useEffect(() => {
    const checkConnectionStatus = async () => {
      if (!token) {
        setConnectionStatus('disconnected');
        return;
      }

      try {
        const response = await fetch('/api/accounts/', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.ok) {
          setConnectionStatus('connected');
        } else {
          setConnectionStatus('disconnected');
        }
      } catch {
        setConnectionStatus('disconnected');
      }
    };

    checkConnectionStatus();
    // Check connection status every 30 seconds
    const interval = setInterval(checkConnectionStatus, 30000);

    return () => clearInterval(interval);
  }, [token]);

  // Check active strategy status
  useEffect(() => {
    const checkStrategyStatus = async () => {
      if (!token) {
        setStrategyStatus({ isActive: false });
        return;
      }

      try {
        const response = await fetch('/api/accounts/', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const accounts = await response.json();
          // Check if any account has an active strategy
          const activeStrategy = accounts.find(
            (account: { active_strategy?: string }) => account.active_strategy
          );

          if (activeStrategy) {
            setStrategyStatus({
              isActive: true,
              strategyName: activeStrategy.active_strategy,
            });
          } else {
            setStrategyStatus({ isActive: false });
          }
        }
      } catch {
        setStrategyStatus({ isActive: false });
      }
    };

    checkStrategyStatus();
    // Check strategy status every 10 seconds
    const interval = setInterval(checkStrategyStatus, 10000);

    return () => clearInterval(interval);
  }, [token]);

  // Determine market status (simplified - forex market is open 24/5)
  useEffect(() => {
    const checkMarketStatus = () => {
      const now = new Date();
      const day = now.getUTCDay(); // 0 = Sunday, 6 = Saturday
      const hour = now.getUTCHours();

      // Forex market is closed on weekends
      // Closes Friday 22:00 UTC, opens Sunday 22:00 UTC
      if (day === 6 || (day === 5 && hour >= 22)) {
        setMarketStatus('closed');
      } else if (day === 0 && hour < 22) {
        setMarketStatus('closed');
      } else {
        setMarketStatus('open');
      }
    };

    checkMarketStatus();
    // Check market status every minute
    const interval = setInterval(checkMarketStatus, 60000);

    return () => clearInterval(interval);
  }, []);

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
        <Chip
          icon={<CircleIcon />}
          label={
            connectionStatus === 'connected'
              ? t('status.connected')
              : t('status.disconnected')
          }
          color={connectionStatus === 'connected' ? 'success' : 'error'}
          size="small"
          sx={{
            '& .MuiChip-icon': {
              fontSize: '0.75rem',
            },
          }}
        />

        {/* Strategy Status */}
        <Chip
          icon={<TrendingUpIcon />}
          label={
            strategyStatus.isActive
              ? `${t('status.active')}: ${strategyStatus.strategyName || 'Strategy'}`
              : t('status.inactive')
          }
          color={strategyStatus.isActive ? 'primary' : 'default'}
          size="small"
        />

        {/* System Time */}
        <Chip
          icon={<ScheduleIcon />}
          label={`${currentTime} ${user?.timezone || 'UTC'}`}
          size="small"
          variant="outlined"
        />

        {/* Market Status */}
        <Chip
          icon={<StoreIcon />}
          label={marketStatus === 'open' ? 'Market Open' : 'Market Closed'}
          color={marketStatus === 'open' ? 'success' : 'default'}
          size="small"
        />

        {/* Copyright */}
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ ml: 'auto' }}
        >
          © {new Date().getFullYear()} Auto Forex Trader
        </Typography>
      </Stack>
    </Box>
  );
};

export default AppFooter;
