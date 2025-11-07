import { Outlet } from 'react-router-dom';
import { Box, useTheme, useMediaQuery } from '@mui/material';
import AppHeader from './AppHeader';
import AppFooter from './AppFooter';
import ResponsiveNavigation from './ResponsiveNavigation';

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
        {/* Main content area */}
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            display: 'flex',
            flexDirection: 'column',
            marginBottom: isMobile ? '112px' : 0, // Space for footer + bottom nav on mobile
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
        }}
      >
        <AppFooter />
      </Box>

      {/* Mobile bottom navigation */}
      {isMobile && <ResponsiveNavigation />}
    </Box>
  );
};

export default AppLayout;
