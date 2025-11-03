import { Outlet } from 'react-router-dom';
import { Box } from '@mui/material';
import AppHeader from './AppHeader';
import AppFooter from './AppFooter';

const AppLayout = () => {
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
        component="main"
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Outlet />
      </Box>
      <AppFooter />
    </Box>
  );
};

export default AppLayout;
