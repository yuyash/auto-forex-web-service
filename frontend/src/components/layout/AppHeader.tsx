import { AppBar, Toolbar, Typography, Button, Box } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';

const AppHeader = () => {
  return (
    <AppBar position="static">
      <Toolbar>
        <Typography
          variant="h6"
          component={RouterLink}
          to="/"
          sx={{
            flexGrow: 1,
            textDecoration: 'none',
            color: 'inherit',
          }}
        >
          Auto Forex Trading System
        </Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button color="inherit" component={RouterLink} to="/dashboard">
            Dashboard
          </Button>
          <Button color="inherit" component={RouterLink} to="/orders">
            Orders
          </Button>
          <Button color="inherit" component={RouterLink} to="/positions">
            Positions
          </Button>
          <Button color="inherit" component={RouterLink} to="/strategy">
            Strategy
          </Button>
          <Button color="inherit" component={RouterLink} to="/backtest">
            Backtest
          </Button>
          <Button color="inherit" component={RouterLink} to="/settings">
            Settings
          </Button>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default AppHeader;
