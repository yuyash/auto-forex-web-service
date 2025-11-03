import { Outlet } from 'react-router-dom';
import { Box, useTheme, useMediaQuery } from '@mui/material';
import AppHeader from './AppHeader';
import AppFooter from './AppFooter';
import ResponsiveNavigation from './ResponsiveNavigation';

const DRAWER_WIDTH = 240;

const AppLayout = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm')); // < 600px

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        minHeight: '100vh',
      }}
    >
      <AppHeader />
      <Box
        sx={{
          display: 'flex',
          flexGrow: 1,
        }}
      >
        {/* Desktop sidebar navigation */}
        {!isMobile && <ResponsiveNavigation />}

        {/* Main content area */}
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            display: 'flex',
            flexDirection: 'column',
            marginLeft: isMobile ? 0 : `${DRAWER_WIDTH}px`,
            marginBottom: isMobile ? '56px' : 0, // Space for mobile bottom nav
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
