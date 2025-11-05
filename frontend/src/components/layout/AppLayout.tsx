import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Box, useTheme, useMediaQuery } from '@mui/material';
import AppHeader from './AppHeader';
import AppFooter from './AppFooter';
import ResponsiveNavigation, { DRAWER_WIDTH } from './ResponsiveNavigation';

const AppLayout = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm')); // < 600px
  const [drawerOpen, setDrawerOpen] = useState(false);

  const handleDrawerToggle = () => {
    setDrawerOpen(!drawerOpen);
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        minHeight: '100vh',
      }}
    >
      <AppHeader onMenuClick={handleDrawerToggle} />
      <Box
        sx={{
          display: 'flex',
          flexGrow: 1,
        }}
      >
        {/* Desktop sidebar navigation */}
        {!isMobile && (
          <ResponsiveNavigation
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
          />
        )}

        {/* Main content area */}
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            display: 'flex',
            flexDirection: 'column',
            marginLeft: !isMobile && drawerOpen ? `${DRAWER_WIDTH}px` : 0,
            marginBottom: isMobile ? '56px' : 0, // Space for mobile bottom nav
            transition: theme.transitions.create(['margin'], {
              easing: theme.transitions.easing.sharp,
              duration: theme.transitions.duration.leavingScreen,
            }),
          }}
        >
          <Outlet />
        </Box>
      </Box>

      {/* Mobile bottom navigation */}
      {isMobile && <ResponsiveNavigation />}

      <AppFooter />
    </Box>
  );
};

export default AppLayout;
