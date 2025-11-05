import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  BottomNavigation,
  BottomNavigationAction,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Receipt as OrdersIcon,
  AccountBalance as PositionsIcon,
  TrendingUp as StrategyIcon,
  Assessment as BacktestIcon,
  Settings as SettingsIcon,
  AdminPanelSettings as AdminIcon,
} from '@mui/icons-material';
import { useAuth } from '../../contexts/AuthContext';

export const DRAWER_WIDTH = 240;

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
    path: '/strategy',
    label: 'Strategy',
    icon: <StrategyIcon />,
  },
  {
    path: '/backtest',
    label: 'Backtest',
    icon: <BacktestIcon />,
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

interface ResponsiveNavigationProps {
  open?: boolean;
  onClose?: () => void;
}

const ResponsiveNavigation = ({
  open = false,
  onClose,
}: ResponsiveNavigationProps) => {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm')); // < 600px
  const { user } = useAuth();

  // Filter navigation items based on user role
  const filteredItems = navigationItems.filter(
    (item) => !item.adminOnly || user?.is_staff
  );

  // Get current active path
  const currentPath = location.pathname;

  const handleNavigation = (path: string) => {
    navigate(path);
  };

  // Desktop sidebar navigation
  if (!isMobile) {
    return (
      <Drawer
        variant="persistent"
        open={open}
        onClose={onClose}
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: DRAWER_WIDTH,
            boxSizing: 'border-box',
            top: '64px', // Height of AppHeader
            height: 'calc(100% - 64px)',
          },
        }}
      >
        <List>
          {filteredItems.map((item) => (
            <ListItem key={item.path} disablePadding>
              <ListItemButton
                selected={currentPath === item.path}
                onClick={() => handleNavigation(item.path)}
                sx={{
                  '&.Mui-selected': {
                    backgroundColor: theme.palette.primary.main,
                    color: theme.palette.primary.contrastText,
                    '&:hover': {
                      backgroundColor: theme.palette.primary.dark,
                    },
                    '& .MuiListItemIcon-root': {
                      color: theme.palette.primary.contrastText,
                    },
                  },
                }}
              >
                <ListItemIcon
                  sx={{
                    color:
                      currentPath === item.path
                        ? theme.palette.primary.contrastText
                        : 'inherit',
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                <ListItemText primary={item.label} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Drawer>
    );
  }

  // Mobile bottom navigation
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
          />
        ))}
      </BottomNavigation>
    </Box>
  );
};

export default ResponsiveNavigation;
