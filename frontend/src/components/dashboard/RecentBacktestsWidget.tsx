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

const RecentBacktestsWidget = () => {
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
    <Paper elevation={2} sx={{ p: 3, height: '100%' }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 2,
        }}
      >
        <Typography variant="h6">Recent Backtests</Typography>
        <Button
          size="small"
          endIcon={<ArrowIcon />}
          onClick={() => navigate('/backtest-tasks')}
        >
          View All
        </Button>
      </Box>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
          <CircularProgress size={32} />
        </Box>
      ) : backtestTasks.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
          No completed backtests yet
        </Typography>
      ) : (
        <Stack spacing={2}>
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
                    {new Date(task.updated_at).toLocaleDateString()}
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
