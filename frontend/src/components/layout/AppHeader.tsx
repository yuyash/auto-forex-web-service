import { useState, useEffect } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  IconButton,
  Menu,
  MenuItem,
  Select,
  FormControl,
  Divider,
  ListItemIcon,
  ListItemText,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  AccountCircle,
  Person,
  Settings,
  Logout,
  AdminPanelSettings,
} from '@mui/icons-material';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import LanguageSelector from '../common/LanguageSelector';
import NotificationCenter from '../admin/NotificationCenter';

interface OandaAccount {
  id: number;
  account_id: string;
  api_type: string;
  balance: string;
  currency: string;
}

const AppHeader = () => {
  const { t } = useTranslation('common');
  const { logout, user, token } = useAuth();
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [userMenuAnchorEl, setUserMenuAnchorEl] = useState<null | HTMLElement>(
    null
  );
  const [accounts, setAccounts] = useState<OandaAccount[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');

  // Fetch OANDA accounts
  useEffect(() => {
    const fetchAccounts = async () => {
      if (!token) return;

      try {
        const response = await fetch('/api/accounts/', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const data = await response.json();
          setAccounts(data);
          // Set first account as default if available
          if (data.length > 0 && !selectedAccountId) {
            setSelectedAccountId(data[0].id.toString());
          }
        }
      } catch (error) {
        console.error('Failed to fetch accounts:', error);
      }
    };

    fetchAccounts();
  }, [token, selectedAccountId]);

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

  const handleAccountChange = (event: { target: { value: string } }) => {
    setSelectedAccountId(String(event.target.value));
  };

  return (
    <AppBar position="static">
      <Toolbar>
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

        {/* Account Selector */}
        {accounts.length > 0 && (
          <FormControl
            size="small"
            sx={{
              minWidth: 200,
              mr: 2,
              '& .MuiOutlinedInput-root': {
                color: 'inherit',
                '& fieldset': {
                  borderColor: 'rgba(255, 255, 255, 0.3)',
                },
                '&:hover fieldset': {
                  borderColor: 'rgba(255, 255, 255, 0.5)',
                },
                '&.Mui-focused fieldset': {
                  borderColor: 'rgba(255, 255, 255, 0.7)',
                },
              },
              '& .MuiSelect-icon': {
                color: 'inherit',
              },
            }}
          >
            <Select
              value={selectedAccountId}
              onChange={handleAccountChange}
              displayEmpty
              inputProps={{ 'aria-label': 'Select OANDA Account' }}
            >
              {accounts.map((account) => (
                <MenuItem key={account.id} value={account.id.toString()}>
                  {account.account_id} ({account.api_type}) - {account.currency}{' '}
                  {Number(account.balance).toFixed(2)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}

        {/* Navigation Buttons - Hidden on mobile */}
        {!isMobile && (
          <Box
            sx={{ display: 'flex', gap: 1, alignItems: 'center', flexGrow: 1 }}
          >
            <Button color="inherit" component={RouterLink} to="/dashboard">
              {t('navigation.dashboard')}
            </Button>
            <Button color="inherit" component={RouterLink} to="/orders">
              {t('navigation.orders')}
            </Button>
            <Button color="inherit" component={RouterLink} to="/positions">
              {t('navigation.positions')}
            </Button>
            <Button color="inherit" component={RouterLink} to="/strategy">
              {t('navigation.strategy')}
            </Button>
            <Button color="inherit" component={RouterLink} to="/backtest">
              {t('navigation.backtest')}
            </Button>
            <Button color="inherit" component={RouterLink} to="/settings">
              {t('navigation.settings')}
            </Button>
          </Box>
        )}

        {/* Spacer for mobile to push right side icons to the right */}
        {isMobile && <Box sx={{ flexGrow: 1 }} />}

        {/* Right side icons */}
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          {/* Language Selector */}
          <LanguageSelector />

          {/* Notification Center (Admin only) */}
          <NotificationCenter />

          {/* User Menu */}
          <IconButton
            size="large"
            edge="end"
            aria-label="account of current user"
            aria-controls="user-menu"
            aria-haspopup="true"
            onClick={handleUserMenuOpen}
            color="inherit"
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
