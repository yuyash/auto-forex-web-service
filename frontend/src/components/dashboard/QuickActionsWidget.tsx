import { useNavigate } from 'react-router-dom';
import { Paper, Typography, Button, Stack } from '@mui/material';
import {
  Tune as ConfigIcon,
  Assessment as BacktestIcon,
  PlayCircleOutline as TradingIcon,
  AccountBalanceWallet as AccountIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';

const QuickActionsWidget = () => {
  const { t } = useTranslation('dashboard');
  const navigate = useNavigate();

  const actions = [
    {
      label: t('quickActions.addAccount'),
      icon: <AccountIcon />,
      path: '/oanda-accounts',
      color: 'info' as const,
    },
    {
      label: t('quickActions.newConfiguration'),
      icon: <ConfigIcon />,
      path: '/configurations/new',
      color: 'primary' as const,
    },
    {
      label: t('quickActions.newBacktestTask'),
      icon: <BacktestIcon />,
      path: '/backtest-tasks/new',
      color: 'secondary' as const,
    },
    {
      label: t('quickActions.newTradingTask'),
      icon: <TradingIcon />,
      path: '/trading-tasks/new',
      color: 'success' as const,
    },
  ];

  return (
    <Paper elevation={2} sx={{ p: { xs: 1, sm: 1.25 }, height: '100%' }}>
      <Typography variant="subtitle1" sx={{ mb: 0.75, fontWeight: 600 }}>
        {t('widgets.quickActions')}
      </Typography>

      <Stack spacing={0.75}>
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
              py: 0.5,
            }}
          >
            {action.label}
          </Button>
        ))}
      </Stack>
    </Paper>
  );
};

export default QuickActionsWidget;
