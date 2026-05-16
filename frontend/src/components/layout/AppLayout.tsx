import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Box, useTheme, useMediaQuery } from '@mui/material';
import AppHeader from './AppHeader';
import AppFooter from './AppFooter';
import ResponsiveNavigation from './ResponsiveNavigation';
import Sidebar from './Sidebar';
import SkipLinks from '../common/SkipLinks';
import GlobalKeyboardShortcuts from '../common/GlobalKeyboardShortcuts';
import { DRAWER_WIDTH, MOBILE_BOTTOM_NAV_HEIGHT } from './constants';
import { useAppSettings } from '../../hooks/useAppSettings';
import { useActiveScreenRefetch } from '../../hooks/useActiveScreenRefetch';
import { layoutTokens } from '../../theme/density';

const AppLayout = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm')); // < 600px
  const isTablet = useMediaQuery(theme.breakpoints.between('sm', 'md')); // 600px - 900px
  const { settings, updateSetting } = useAppSettings();
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);
  useActiveScreenRefetch();

  const handleDrawerToggle = () => {
    setMobileDrawerOpen(!mobileDrawerOpen);
  };

  // Show sidebar only on tablet (not on mobile or desktop)
  const showSidebar = isTablet;
  const mobileBottomInset = `calc(${MOBILE_BOTTOM_NAV_HEIGHT}px + env(safe-area-inset-bottom) + 8px)`;

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
          height: '100vh',
          overflow: 'hidden',
        }}
      >
        <AppHeader
          onMenuClick={handleDrawerToggle}
          constrainContentWidth={settings.constrainContentWidth}
          onToggleContentWidth={() =>
            updateSetting(
              'constrainContentWidth',
              !settings.constrainContentWidth
            )
          }
        />
        <Box
          sx={{
            display: 'flex',
            flexGrow: 1,
            overflow: 'hidden',
          }}
        >
          {/* Sidebar navigation - only shown on tablet */}
          {showSidebar && (
            <Sidebar
              id="navigation"
              mobileOpen={mobileDrawerOpen}
              onMobileClose={handleDrawerToggle}
            />
          )}

          {/* Main content area */}
          <Box
            component="main"
            id="main-content"
            tabIndex={-1}
            sx={{
              flexGrow: 1,
              display: 'flex',
              flexDirection: 'column',
              overflowY: 'auto',
              pb: isMobile ? mobileBottomInset : 0,
              scrollPaddingBottom: isMobile ? mobileBottomInset : 0,
              width: showSidebar ? `calc(100% - ${DRAWER_WIDTH}px)` : '100%',
              '--app-content-max-width': settings.constrainContentWidth
                ? `${layoutTokens.contentMaxWidth}px`
                : 'none',
              '&:focus': {
                outline: 'none',
              },
            }}
          >
            <Outlet />
          </Box>
        </Box>

        {/* Footer */}
        <Box
          sx={{
            position: isMobile ? 'fixed' : 'relative',
            bottom: isMobile ? '56px' : 'auto',
            left: 0,
            right: 0,
            zIndex: isMobile ? 1000 : 'auto',
            marginLeft: showSidebar ? `${DRAWER_WIDTH}px` : 0,
            display: isMobile ? 'none' : 'block',
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
