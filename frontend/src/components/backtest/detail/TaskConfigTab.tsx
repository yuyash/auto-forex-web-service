import {
  Box,
  Paper,
  Typography,
  Chip,
  Divider,
  Button,
  Alert,
  IconButton,
  Menu,
  MenuItem,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import {
  Edit as EditIcon,
  OpenInNew as OpenInNewIcon,
  MoreVert as MoreVertIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import type { BacktestTask } from '../../../types/backtestTask';
import { useConfiguration } from '../../../hooks/useConfigurations';

interface TaskConfigTabProps {
  task: BacktestTask;
}

export function TaskConfigTab({ task }: TaskConfigTabProps) {
  const navigate = useNavigate();
  const { data: config } = useConfiguration(task.config_id);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleEditConfig = () => {
    navigate(`/configurations/${task.config_id}/edit`, {
      state: { from: 'backtest-tasks', taskId: task.id, taskName: task.name },
    });
    handleMenuClose();
  };

  const handleViewConfig = () => {
    navigate(`/configurations`);
    handleMenuClose();
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const formatCurrency = (value: string) => {
    return `$${parseFloat(value).toFixed(2)}`;
  };

  return (
    <Box sx={{ px: 3 }}>
      {/* Task-Specific Settings Section */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 3 }}>
          Task-Specific Settings
        </Typography>

        <Grid container spacing={3}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary">
              Task Name
            </Typography>
            <Typography variant="body1" fontWeight="medium">
              {task.name}
            </Typography>
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary">
              Data Source
            </Typography>
            <Chip
              label={task.data_source.toUpperCase()}
              size="small"
              color="primary"
              variant="outlined"
            />
          </Grid>

          {task.description && (
            <Grid size={{ xs: 12 }}>
              <Typography variant="body2" color="text.secondary">
                Task Description
              </Typography>
              <Typography variant="body1">{task.description}</Typography>
            </Grid>
          )}

          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary">
              Backtest Period Start
            </Typography>
            <Typography variant="body1">
              {formatDate(task.start_time)}
            </Typography>
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary">
              Backtest Period End
            </Typography>
            <Typography variant="body1">{formatDate(task.end_time)}</Typography>
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary">
              Initial Balance
            </Typography>
            <Typography variant="body1" fontWeight="medium">
              {formatCurrency(task.initial_balance)}
            </Typography>
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary">
              Commission per Trade
            </Typography>
            <Typography variant="body1">
              {formatCurrency(task.commission_per_trade)}
            </Typography>
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary">
              Pip Size
            </Typography>
            <Typography variant="body1">
              {task.pip_size || 'Auto (from OANDA account)'}
            </Typography>
          </Grid>

          <Grid size={{ xs: 12 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Instrument
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              <Chip label={task.instrument} size="small" variant="outlined" />
            </Box>
          </Grid>
        </Grid>

        <Divider sx={{ my: 3 }} />

        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary">
              Task Created
            </Typography>
            <Typography variant="body2">
              {formatDate(task.created_at)}
            </Typography>
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary">
              Last Updated
            </Typography>
            <Typography variant="body2">
              {formatDate(task.updated_at)}
            </Typography>
          </Grid>
        </Grid>
      </Paper>

      {/* Strategy Configuration Section */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 3,
          }}
        >
          <Typography variant="h6">Strategy Configuration</Typography>
          {isMobile ? (
            <IconButton onClick={handleMenuOpen} size="small">
              <MoreVertIcon />
            </IconButton>
          ) : (
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="outlined"
                size="small"
                startIcon={<OpenInNewIcon />}
                onClick={handleViewConfig}
              >
                View All Configs
              </Button>
              <Button
                variant="contained"
                size="small"
                startIcon={<EditIcon />}
                onClick={handleEditConfig}
              >
                Edit Configuration
              </Button>
            </Box>
          )}
        </Box>

        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleMenuClose}
        >
          <MenuItem onClick={handleEditConfig}>
            <EditIcon sx={{ mr: 1, fontSize: 20 }} />
            Edit Configuration
          </MenuItem>
          <MenuItem onClick={handleViewConfig}>
            <OpenInNewIcon sx={{ mr: 1, fontSize: 20 }} />
            View All Configs
          </MenuItem>
        </Menu>

        <Grid container spacing={3}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary">
              Configuration Name
            </Typography>
            <Typography variant="body1" fontWeight="medium">
              {task.config_name}
            </Typography>
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary">
              Strategy Type
            </Typography>
            <Typography variant="body1" fontWeight="medium">
              {task.strategy_type}
            </Typography>
          </Grid>

          {config?.description && (
            <Grid size={{ xs: 12 }}>
              <Typography variant="body2" color="text.secondary">
                Description
              </Typography>
              <Typography variant="body1">{config.description}</Typography>
            </Grid>
          )}
        </Grid>

        {config?.parameters && (
          <>
            <Divider sx={{ my: 3 }} />
            <Typography variant="subtitle2" sx={{ mb: 2 }}>
              Strategy Parameters
            </Typography>

            <Box
              sx={{
                bgcolor: 'grey.50',
                p: 2,
                borderRadius: 1,
                border: 1,
                borderColor: 'grey.200',
              }}
            >
              <Box
                component="pre"
                sx={{
                  m: 0,
                  fontFamily: 'monospace',
                  fontSize: '0.875rem',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {JSON.stringify(config.parameters, null, 2)}
              </Box>
            </Box>
          </>
        )}

        {config && (
          <>
            <Divider sx={{ my: 3 }} />
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <Typography variant="body2" color="text.secondary">
                  Configuration Created
                </Typography>
                <Typography variant="body2">
                  {formatDate(config.created_at)}
                </Typography>
              </Grid>

              <Grid size={{ xs: 12, sm: 6 }}>
                <Typography variant="body2" color="text.secondary">
                  Last Updated
                </Typography>
                <Typography variant="body2">
                  {formatDate(config.updated_at)}
                </Typography>
              </Grid>
            </Grid>
          </>
        )}
      </Paper>

      {/* Information Alert */}
      <Alert severity="info">
        <Typography variant="body2">
          <strong>Note:</strong> Changes to the strategy configuration will only
          affect new executions. Existing execution results remain unchanged.
        </Typography>
      </Alert>
    </Box>
  );
}
