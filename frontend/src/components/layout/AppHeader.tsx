import { useState } from 'react';
import {
  AppBar,
  Toolbar,
  Box,
  IconButton,
  Menu,
  MenuItem,
  Divider,
  ListItemIcon,
  ListItemText,
  useTheme,
  useMediaQuery,
  Button,
} from '@mui/material';
import {
  AccountCircle,
  Person,
  Settings,
  Logout,
  AdminPanelSettings,
  Menu as MenuIcon,
  Receipt as OrdersIcon,
  AccountBalance as PositionsIcon,
  Assignment as BacktestTaskIcon,
  PlayCircleOutline as TradingTaskIcon,
} from '@mui/icons-material';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import LanguageSelector from '../common/LanguageSelector';
import NotificationCenter from '../admin/NotificationCenter';
import Typography from '@mui/material/Typography';

interface AppHeaderProps {
  onMenuClick?: () => void;
}

const AppHeader = ({ onMenuClick }: AppHeaderProps) => {
  const { t } = useTranslation('common');
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [userMenuAnchorEl, setUserMenuAnchorEl] = useState<null | HTMLElement>(
    null
  );

  const handleUserMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setUserMenuAnchorEl(event.currentTarget);
  };

  const handleUserMenuClose = () => {
    setUserMenuAnchorEl(null);
  };

  const handleProfileClick = () => {
    handleUserMenuClose();
    navigate('/profile');
  };

  const handleSettingsClick = () => {
    handleUserMenuClose();
    navigate('/settings');
  };

  const handleAdminClick = () => {
    handleUserMenuClose();
    navigate('/admin');
  };

  const handleLogout = async () => {
    handleUserMenuClose();
    await logout();
    navigate('/login');
  };

  const isTablet = useMediaQuery(theme.breakpoints.between('sm', 'md')); // 600px - 900px
  const isDesktop = useMediaQuery(theme.breakpoints.up('md'));

  return (
    <AppBar
      position="fixed"
      sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}
    >
      <Toolbar>
        {/* Menu button for tablet only (not mobile) */}
        {isTablet && (
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={onMenuClick}
            sx={{ mr: 2 }}
          >
            <MenuIcon />
          </IconButton>
        )}

        {/* Logo */}
        <Box
          component={RouterLink}
          to="/"
          sx={{
            display: 'flex',
            alignItems: 'center',
            mr: 3,
            textDecoration: 'none',
          }}
        >
          <img
            src="/logo.svg"
            alt="Logo"
            style={{
              height: '40px',
              width: 'auto',
            }}
          />
        </Box>

        {/* Desktop Navigation Buttons */}
        {isDesktop && (
          <Box sx={{ display: 'flex', gap: 1, mr: 2 }}>
            <Button
              color="inherit"
              startIcon={<OrdersIcon />}
              component={RouterLink}
              to="/orders"
              sx={{ textTransform: 'none' }}
            >
              Orders
            </Button>
            <Button
              color="inherit"
              startIcon={<PositionsIcon />}
              component={RouterLink}
              to="/positions"
              sx={{ textTransform: 'none' }}
            >
              Positions
            </Button>
            <Button
              color="inherit"
              startIcon={<BacktestTaskIcon />}
              component={RouterLink}
              to="/backtest-tasks"
              sx={{ textTransform: 'none' }}
            >
              Backtest
            </Button>
            <Button
              color="inherit"
              startIcon={<TradingTaskIcon />}
              component={RouterLink}
              to="/trading-tasks"
              sx={{ textTransform: 'none' }}
            >
              Trading
            </Button>
          </Box>
        )}

        {/* Spacer to push right side icons to the right */}
        <Box sx={{ flexGrow: 1 }} />

        {/* Right side icons */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            columnGap: { xs: 0.5, sm: 1 },
            flexShrink: 0,
          }}
        >
          {/* Language Selector */}
          <LanguageSelector
            buttonSize="small"
            buttonSx={{ p: { xs: 0.5, sm: 1 } }}
          />

          {/* Notification Center (Admin only) */}
          <NotificationCenter
            buttonSize="small"
            buttonSx={{ p: { xs: 0.5, sm: 1 } }}
          />

          {/* User Menu */}
          <IconButton
            size="small"
            edge="end"
            aria-label="account of current user"
            aria-controls="user-menu"
            aria-haspopup="true"
            onClick={handleUserMenuOpen}
            color="inherit"
            sx={{ p: { xs: 0.5, sm: 1 } }}
          >
            <AccountCircle />
          </IconButton>
          <Menu
            id="user-menu"
            anchorEl={userMenuAnchorEl}
            open={Boolean(userMenuAnchorEl)}
            onClose={handleUserMenuClose}
            anchorOrigin={{
              vertical: 'bottom',
              horizontal: 'right',
            }}
            transformOrigin={{
              vertical: 'top',
              horizontal: 'right',
            }}
            slotProps={{
              paper: {
                sx: {
                  mt: 1,
                  ...(isMobile && {
                    right: 8,
                    left: 'auto !important',
                  }),
                },
              },
            }}
          >
            <MenuItem disabled>
              <Typography variant="body2" color="text.secondary">
                {user?.email}
              </Typography>
            </MenuItem>
            <Divider />
            <MenuItem onClick={handleProfileClick}>
              <ListItemIcon>
                <Person fontSize="small" />
              </ListItemIcon>
              <ListItemText>Profile</ListItemText>
            </MenuItem>
            <MenuItem onClick={handleSettingsClick}>
              <ListItemIcon>
                <Settings fontSize="small" />
              </ListItemIcon>
              <ListItemText>{t('navigation.settings')}</ListItemText>
            </MenuItem>
            {user?.is_staff && (
              <>
                <Divider />
                <MenuItem onClick={handleAdminClick}>
                  <ListItemIcon>
                    <AdminPanelSettings fontSize="small" />
                  </ListItemIcon>
                  <ListItemText>{t('navigation.admin')}</ListItemText>
                </MenuItem>
              </>
            )}
            <Divider />
            <MenuItem onClick={handleLogout}>
              <ListItemIcon>
                <Logout fontSize="small" />
              </ListItemIcon>
              <ListItemText>{t('navigation.logout')}</ListItemText>
            </MenuItem>
          </Menu>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default AppHeader;
