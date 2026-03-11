import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  BottomNavigation,
  BottomNavigationAction,
  useTheme,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Settings as SettingsIcon,
  Tune as ConfigIcon,
  Assignment as TaskIcon,
  PlayCircleOutline as TradingTaskIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';

interface NavigationItem {
  path: string;
  labelKey: string;
  icon: React.ReactElement;
  adminOnly?: boolean;
}

const navigationItems: NavigationItem[] = [
  {
    path: '/dashboard',
    labelKey: 'navigation.dashboard',
    icon: <DashboardIcon />,
  },
  {
    path: '/configurations',
    labelKey: 'navigation.configurations',
    icon: <ConfigIcon />,
  },
  {
    path: '/backtest-tasks',
    labelKey: 'navigation.backtest',
    icon: <TaskIcon />,
  },
  {
    path: '/trading-tasks',
    labelKey: 'navigation.trading',
    icon: <TradingTaskIcon />,
  },
  {
    path: '/settings',
    labelKey: 'navigation.settings',
    icon: <SettingsIcon />,
  },
];

const ResponsiveNavigation = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const { user } = useAuth();
  const { t } = useTranslation('common');

  // Filter navigation items based on user role and exclude Settings/Admin from mobile
  const filteredItems = navigationItems.filter(
    (item) =>
      // Exclude Settings from mobile bottom navigation
      item.path !== '/settings' && (!item.adminOnly || user?.is_staff)
  );

  // Get current active path
  const currentPath = location.pathname;

  const handleNavigation = (path: string) => {
    navigate(path);
  };

  // Mobile bottom navigation only
  return (
    <Box
      sx={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: theme.zIndex.appBar,
      }}
    >
      <BottomNavigation
        value={currentPath}
        onChange={(_, newValue) => {
          handleNavigation(newValue);
        }}
        showLabels
        sx={{
          borderTop: `1px solid ${theme.palette.divider}`,
        }}
      >
        {filteredItems.map((item) => (
          <BottomNavigationAction
            key={item.path}
            label={t(item.labelKey)}
            value={item.path}
            icon={item.icon}
            sx={{
              minWidth: 0,
              px: 0.5,
              '& .MuiBottomNavigationAction-label': {
                fontSize: '0.6rem',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                maxWidth: '100%',
                '&.Mui-selected': {
                  fontSize: '0.65rem',
                },
              },
            }}
          />
        ))}
      </BottomNavigation>
    </Box>
  );
};

export default ResponsiveNavigation;
