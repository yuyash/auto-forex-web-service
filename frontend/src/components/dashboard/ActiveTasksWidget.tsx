import { useNavigate } from 'react-router-dom';
import {
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
  CircularProgress,
  Stack,
  Button,
} from '@mui/material';
import {
  PlayCircleOutline as TradingIcon,
  Assessment as BacktestIcon,
  ArrowForward as ArrowIcon,
} from '@mui/icons-material';
import { useBacktestTasks } from '../../hooks/useBacktestTasks';
import { useTradingTasks } from '../../hooks/useTradingTasks';
import { StatusBadge } from '../tasks/display/StatusBadge';
import { TaskStatus } from '../../types/common';
import { useTranslation } from 'react-i18next';

const ActiveTasksWidget = () => {
  const { t } = useTranslation('dashboard');
  const navigate = useNavigate();

  // Fetch running backtest tasks
  const { data: backtestData, isLoading: backtestLoading } = useBacktestTasks({
    status: TaskStatus.RUNNING,
    page: 1,
    page_size: 3,
  });

  // Fetch running trading tasks
  const { data: tradingData, isLoading: tradingLoading } = useTradingTasks({
    status: TaskStatus.RUNNING,
    page: 1,
    page_size: 3,
  });

  const backtestTasks = backtestData?.results || [];
  const tradingTasks = tradingData?.results || [];
  const totalActive = backtestTasks.length + tradingTasks.length;

  const isLoading = backtestLoading || tradingLoading;

  return (
    <Paper elevation={2} sx={{ p: 3, height: '100%' }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 2,
        }}
      >
        <Typography variant="h6">
          {t('widgets.activeTasks')} ({totalActive})
        </Typography>
        <Button
          endIcon={<ArrowIcon />}
          onClick={() => navigate('/backtest-tasks')}
        >
          {t('widgets.quickActions')}
        </Button>
      </Box>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
          <CircularProgress size={32} />
        </Box>
      ) : totalActive === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
          {t('widgets.noActiveTasksRunning')}
        </Typography>
      ) : (
        <Stack spacing={2}>
          {/* Trading Tasks */}
          {tradingTasks.map((task) => (
            <Card
              key={task.id}
              variant="outlined"
              sx={{
                cursor: 'pointer',
                '&:hover': {
                  boxShadow: 2,
                },
              }}
              onClick={() => navigate(`/trading-tasks/${task.id}`)}
            >
              <CardContent>
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    mb: 1,
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <TradingIcon color="primary" fontSize="small" />
                    <Typography variant="subtitle2">{task.name}</Typography>
                  </Box>
                  <StatusBadge status={task.status} />
                </Box>
                <Typography variant="caption" color="text.secondary">
                  {t('widgets.tradingTask')} • {task.config_name || task.name}
                </Typography>
              </CardContent>
            </Card>
          ))}

          {/* Backtest Tasks */}
          {backtestTasks.map((task) => (
            <Card
              key={task.id}
              variant="outlined"
              sx={{
                cursor: 'pointer',
                '&:hover': {
                  boxShadow: 2,
                },
              }}
              onClick={() => navigate(`/backtest-tasks/${task.id}`)}
            >
              <CardContent>
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    mb: 1,
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <BacktestIcon color="secondary" fontSize="small" />
                    <Typography variant="subtitle2">{task.name}</Typography>
                  </Box>
                  <StatusBadge status={task.status} />
                </Box>
                <Typography variant="caption" color="text.secondary">
                  {t('widgets.backtestTask')} • {task.config_name || task.name}
                </Typography>
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}
    </Paper>
  );
};

export default ActiveTasksWidget;
