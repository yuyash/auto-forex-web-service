import { useNavigate, useLocation } from 'react-router-dom';
import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Divider,
  Box,
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
  Tune as ConfigIcon,
  Assignment as BacktestTaskIcon,
  PlayCircleOutline as TradingTaskIcon,
} from '@mui/icons-material';
import { useAuth } from '../../contexts/AuthContext';
import { DRAWER_WIDTH } from './constants';

interface NavigationItem {
  path: string;
  label: string;
  icon: React.ReactElement;
  adminOnly?: boolean;
  dividerAfter?: boolean;
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
    dividerAfter: true,
  },
  {
    path: '/configurations',
    label: 'Configurations',
    icon: <ConfigIcon />,
  },
  {
    path: '/backtest-tasks',
    label: 'Backtest Tasks',
    icon: <BacktestTaskIcon />,
  },
  {
    path: '/trading-tasks',
    label: 'Trading Tasks',
    icon: <TradingTaskIcon />,
  },
  {
    path: '/backtest',
    label: 'Backtest (Legacy)',
    icon: <BacktestIcon />,
    dividerAfter: true,
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

interface SidebarProps {
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

const Sidebar = ({ mobileOpen = false, onMobileClose }: SidebarProps) => {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const { user } = useAuth();

  // Filter navigation items based on user role
  const filteredItems = navigationItems.filter(
    (item) => !item.adminOnly || user?.is_staff
  );

  const handleNavigation = (path: string) => {
    navigate(path);
    if (isMobile && onMobileClose) {
      onMobileClose();
    }
  };

  // Check if current path matches or is a child of the nav item path
  const isActive = (path: string) => {
    if (path === '/dashboard') {
      return location.pathname === '/dashboard';
    }
    return location.pathname.startsWith(path);
  };

  const drawerContent = (
    <Box>
      <Toolbar />
      <List>
        {filteredItems.map((item) => (
          <Box key={item.path}>
            <ListItem disablePadding>
              <ListItemButton
                selected={isActive(item.path)}
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
                    color: isActive(item.path)
                      ? theme.palette.primary.contrastText
                      : 'inherit',
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                <ListItemText primary={item.label} />
              </ListItemButton>
            </ListItem>
            {item.dividerAfter && <Divider sx={{ my: 1 }} />}
          </Box>
        ))}
      </List>
    </Box>
  );

  return (
    <>
      {/* Mobile drawer */}
      {isMobile && (
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={onMobileClose}
          ModalProps={{
            keepMounted: true, // Better open performance on mobile
          }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
            },
          }}
        >
          {drawerContent}
        </Drawer>
      )}

      {/* Desktop drawer */}
      {!isMobile && (
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
            },
          }}
          open
        >
          {drawerContent}
        </Drawer>
      )}
    </>
  );
};

export default Sidebar;
