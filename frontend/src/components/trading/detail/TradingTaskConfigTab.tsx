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
import type { TradingTask } from '../../../types/tradingTask';
import { useConfiguration } from '../../../hooks/useConfigurations';

interface TradingTaskConfigTabProps {
  task: TradingTask;
}

export function TradingTaskConfigTab({ task }: TradingTaskConfigTabProps) {
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
    navigate(`/configurations/${task.config_id}/edit`);
    handleMenuClose();
  };

  const handleViewConfig = () => {
    navigate(`/configurations`);
    handleMenuClose();
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  return (
    <Box sx={{ px: 3 }}>
      {/* Trading Task Settings Section */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 3 }}>
          Trading Task Settings
        </Typography>

        <Grid container spacing={2}>
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
              Trading Account
            </Typography>
            <Typography variant="body1" fontWeight="medium">
              {task.account_name}
            </Typography>
          </Grid>

          {task.description && (
            <Grid size={{ xs: 12 }}>
              <Typography variant="body2" color="text.secondary">
                Description
              </Typography>
              <Typography variant="body1">{task.description}</Typography>
            </Grid>
          )}

          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary">
              Created At
            </Typography>
            <Typography variant="body1">
              {formatDate(task.created_at)}
            </Typography>
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }}>
            <Typography variant="body2" color="text.secondary">
              Last Updated
            </Typography>
            <Typography variant="body1">
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

        {config ? (
          <>
            <Grid container spacing={2} sx={{ mb: 2 }}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <Typography variant="body2" color="text.secondary">
                  Configuration Name
                </Typography>
                <Typography variant="body1" fontWeight="medium">
                  {config.name}
                </Typography>
              </Grid>

              <Grid size={{ xs: 12, sm: 6 }}>
                <Typography variant="body2" color="text.secondary">
                  Strategy Type
                </Typography>
                <Chip
                  label={config.strategy_type}
                  size="small"
                  color="primary"
                  sx={{ mt: 0.5 }}
                />
              </Grid>

              {config.description && (
                <Grid size={{ xs: 12 }}>
                  <Typography variant="body2" color="text.secondary">
                    Description
                  </Typography>
                  <Typography variant="body1">{config.description}</Typography>
                </Grid>
              )}
            </Grid>

            <Divider sx={{ my: 2 }} />

            <Typography variant="subtitle2" sx={{ mb: 2 }}>
              Strategy Parameters
            </Typography>

            <Box
              sx={{
                bgcolor: 'grey.50',
                p: 2,
                borderRadius: 1,
                fontFamily: 'monospace',
                fontSize: '0.875rem',
                overflow: 'auto',
              }}
            >
              <pre style={{ margin: 0 }}>
                {JSON.stringify(config.parameters, null, 2)}
              </pre>
            </Box>
          </>
        ) : (
          <Alert severity="warning">
            Configuration details could not be loaded.
          </Alert>
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
