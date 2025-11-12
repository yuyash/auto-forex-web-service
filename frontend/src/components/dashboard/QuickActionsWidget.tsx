import { useNavigate } from 'react-router-dom';
import { Paper, Typography, Box, Button, Stack } from '@mui/material';
import {
  Tune as ConfigIcon,
  Assessment as BacktestIcon,
  PlayCircleOutline as TradingIcon,
  AccountBalanceWallet as AccountIcon,
} from '@mui/icons-material';

const QuickActionsWidget = () => {
  const navigate = useNavigate();

  const actions = [
    {
      label: 'Add Account',
      icon: <AccountIcon />,
      path: '/settings',
      color: 'info' as const,
    },
    {
      label: 'New Configuration',
      icon: <ConfigIcon />,
      path: '/configurations/new',
      color: 'primary' as const,
    },
    {
      label: 'New Backtest Task',
      icon: <BacktestIcon />,
      path: '/backtest-tasks/new',
      color: 'secondary' as const,
    },
    {
      label: 'New Trading Task',
      icon: <TradingIcon />,
      path: '/trading-tasks/new',
      color: 'success' as const,
    },
  ];

  return (
    <Paper elevation={2} sx={{ p: 3, height: '100%' }}>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Quick Actions
      </Typography>

      <Stack spacing={2}>
        {actions.map((action) => (
          <Button
            key={action.path}
            variant="outlined"
            color={action.color}
            startIcon={action.icon}
            fullWidth
            onClick={() => navigate(action.path)}
            sx={{
              justifyContent: 'flex-start',
              py: 1.5,
            }}
          >
            {action.label}
          </Button>
        ))}
      </Stack>

      <Box sx={{ mt: 3 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Getting Started
        </Typography>
        <Typography variant="caption" color="text.secondary">
          1. Create a strategy configuration
          <br />
          2. Create a backtest or trading task
          <br />
          3. Start the task and monitor results
        </Typography>
      </Box>
    </Paper>
  );
};

export default QuickActionsWidget;
