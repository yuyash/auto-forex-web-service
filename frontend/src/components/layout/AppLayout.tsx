import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Box, useTheme, useMediaQuery } from '@mui/material';
import AppHeader from './AppHeader';
import AppFooter from './AppFooter';
import ResponsiveNavigation from './ResponsiveNavigation';
import Sidebar from './Sidebar';
import SkipLinks from '../common/SkipLinks';
import GlobalKeyboardShortcuts from '../common/GlobalKeyboardShortcuts';
import { DRAWER_WIDTH } from './constants';

const AppLayout = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm')); // < 600px
  const isTabletOrDesktop = useMediaQuery(theme.breakpoints.up('md')); // >= 900px
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);

  const handleDrawerToggle = () => {
    setMobileDrawerOpen(!mobileDrawerOpen);
  };

  return (
    <>
      {/* Skip links for keyboard navigation */}
      <SkipLinks />

      {/* Global keyboard shortcuts */}
      <GlobalKeyboardShortcuts />

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
          {/* Sidebar navigation */}
          <Sidebar
            id="navigation"
            mobileOpen={mobileDrawerOpen}
            onMobileClose={handleDrawerToggle}
          />

          {/* Main content area */}
          <Box
            component="main"
            id="main-content"
            tabIndex={-1}
            sx={{
              flexGrow: 1,
              display: 'flex',
              flexDirection: 'column',
              marginBottom: isMobile ? '112px' : 0, // Space for footer + bottom nav on mobile
              width: isTabletOrDesktop
                ? `calc(100% - ${DRAWER_WIDTH}px)`
                : '100%',
              '&:focus': {
                outline: 'none',
              },
            }}
          >
            <Outlet />
          </Box>
        </Box>

        {/* Footer - positioned above bottom nav on mobile */}
        <Box
          sx={{
            position: isMobile ? 'fixed' : 'relative',
            bottom: isMobile ? '56px' : 'auto',
            left: 0,
            right: 0,
            zIndex: isMobile ? 1000 : 'auto',
            marginLeft: isTabletOrDesktop ? `${DRAWER_WIDTH}px` : 0,
          }}
        >
          <AppFooter />
        </Box>

        {/* Mobile bottom navigation */}
        {isMobile && <ResponsiveNavigation />}
      </Box>
    </>
  );
};

export default AppLayout;
