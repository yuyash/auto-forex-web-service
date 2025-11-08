import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  BottomNavigation,
  BottomNavigationAction,
  useTheme,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Receipt as OrdersIcon,
  AccountBalance as PositionsIcon,
  Settings as SettingsIcon,
  AdminPanelSettings as AdminIcon,
  Assignment as TaskIcon,
  PlayCircleOutline as TradingTaskIcon,
} from '@mui/icons-material';
import { useAuth } from '../../contexts/AuthContext';

interface NavigationItem {
  path: string;
  label: string;
  icon: React.ReactElement;
  adminOnly?: boolean;
}

const navigationItems: NavigationItem[] = [
  {
    path: '/dashboard',
    label: 'Dashboard',
    icon: <DashboardIcon />,
  },
  {
    path: '/orders',
    label: 'Orders',
    icon: <OrdersIcon />,
  },
  {
    path: '/positions',
    label: 'Positions',
    icon: <PositionsIcon />,
  },
  {
    path: '/backtest-tasks',
    label: 'Backtest',
    icon: <TaskIcon />,
  },
  {
    path: '/trading-tasks',
    label: 'Trading',
    icon: <TradingTaskIcon />,
  },
  {
    path: '/settings',
    label: 'Settings',
    icon: <SettingsIcon />,
  },
  {
    path: '/admin',
    label: 'Admin',
    icon: <AdminIcon />,
    adminOnly: true,
  },
];

const ResponsiveNavigation = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const { user } = useAuth();

  // Filter navigation items based on user role and exclude Settings/Admin from mobile
  const filteredItems = navigationItems.filter(
    (item) =>
      // Exclude Settings and Admin from mobile bottom navigation
      item.path !== '/settings' &&
      item.path !== '/admin' &&
      (!item.adminOnly || user?.is_staff)
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
            label={item.label}
            value={item.path}
            icon={item.icon}
            sx={{
              '& .MuiBottomNavigationAction-label': {
                fontSize: '0.65rem',
                '&.Mui-selected': {
                  fontSize: '0.7rem',
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
