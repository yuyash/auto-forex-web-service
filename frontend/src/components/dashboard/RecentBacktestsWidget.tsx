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
  Assessment as BacktestIcon,
  ArrowForward as ArrowIcon,
} from '@mui/icons-material';
import { useBacktestTasks } from '../../hooks/useBacktestTasks';
import { StatusBadge } from '../tasks/display/StatusBadge';
import { TaskStatus } from '../../types/common';
import { useTranslation } from 'react-i18next';
import { useDateTimeFormatter } from '../../hooks/useDateTimeFormatter';

const RecentBacktestsWidget = () => {
  const { t } = useTranslation('dashboard');
  const { formatDate } = useDateTimeFormatter();
  const navigate = useNavigate();

  // Fetch recent completed backtest tasks
  const { data, isLoading } = useBacktestTasks({
    status: TaskStatus.COMPLETED,
    ordering: '-updated_at',
    page: 1,
    page_size: 5,
  });

  const backtestTasks = data?.results || [];

  return (
    <Paper elevation={2} sx={{ p: { xs: 1, sm: 1.25 }, height: '100%' }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 1,
          mb: 0.75,
        }}
      >
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          {t('widgets.recentBacktests')}
        </Typography>
        <Button
          endIcon={<ArrowIcon />}
          onClick={() => navigate('/backtest-tasks')}
        >
          {t('widgets.quickActions')}
        </Button>
      </Box>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 1.5 }}>
          <CircularProgress size={24} />
        </Box>
      ) : backtestTasks.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
          {t('widgets.noCompletedBacktestsYet')}
        </Typography>
      ) : (
        <Stack spacing={0.75}>
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
              <CardContent sx={{ p: 1, '&:last-child': { pb: 1 } }}>
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    gap: 1,
                    mb: 0.25,
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <BacktestIcon color="secondary" fontSize="small" />
                    <Typography variant="subtitle2">{task.name}</Typography>
                  </Box>
                  <StatusBadge status={task.status} />
                </Box>
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <Typography variant="caption" color="text.secondary">
                    {task.config_name || task.name}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ fontSize: '0.7rem' }}
                  >
                    {formatDate(task.updated_at)}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}
    </Paper>
  );
};

export default RecentBacktestsWidget;
