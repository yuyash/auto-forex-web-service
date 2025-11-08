import { useState, useEffect } from 'react';
import { Box, Chip, Stack } from '@mui/material';
import {
  Circle as CircleIcon,
  TrendingUp as TrendingUpIcon,
  Schedule as ScheduleIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { useOandaAccounts } from '../../hooks/useOandaAccounts';

interface StrategyStatus {
  isActive: boolean;
  strategyName?: string;
}

const AppFooter = () => {
  const { t } = useTranslation('common');
  const { user } = useAuth();
  const [currentTime, setCurrentTime] = useState<string>('');

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

  // Use shared hook with caching to prevent duplicate requests
  const { accounts, hasAccounts, error } = useOandaAccounts();

  // Derive connection status from accounts (no useEffect needed)
  const derivedConnectionStatus: 'connected' | 'disconnected' = error
    ? 'disconnected'
    : hasAccounts
      ? 'connected'
      : 'disconnected';

  // Derive strategy status from accounts (no useEffect needed)
  const derivedStrategyStatus: StrategyStatus = (() => {
    if (!hasAccounts) {
      return { isActive: false };
    }

    const activeStrategy = accounts.find((account) => account.active_strategy);

    if (activeStrategy) {
      return {
        isActive: true,
        strategyName: activeStrategy.active_strategy,
      };
    }

    return { isActive: false };
  })();

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
            derivedConnectionStatus === 'connected'
              ? t('status.connected')
              : t('status.disconnected')
          }
          color={derivedConnectionStatus === 'connected' ? 'success' : 'error'}
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
