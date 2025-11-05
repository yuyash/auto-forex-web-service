import React from 'react';
import {
  Paper,
  Typography,
  Box,
  Grid,
  Chip,
  LinearProgress,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Storage as StorageIcon,
  Memory as MemoryIcon,
  Cloud as CloudIcon,
  Speed as SpeedIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import type { SystemHealth } from '../../types/admin';

interface SystemHealthPanelProps {
  health?: SystemHealth;
}

const SystemHealthPanel: React.FC<SystemHealthPanelProps> = ({ health }) => {
  const { t } = useTranslation('admin');

  // Guard against undefined health object
  if (!health) {
    return (
      <Paper elevation={2} sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          {t('health.title')}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Loading system health data...
        </Typography>
      </Paper>
    );
  }

  const getStatusIcon = (status: string) => {
    return status === 'connected' ? (
      <CheckCircleIcon color="success" />
    ) : (
      <ErrorIcon color="error" />
    );
  };

  const getStatusColor = (
    status: string
  ):
    | 'success'
    | 'error'
    | 'default'
    | 'primary'
    | 'secondary'
    | 'info'
    | 'warning' => {
    return status === 'connected' ? 'success' : 'error';
  };

  const getUsageColor = (usage: number): 'success' | 'warning' | 'error' => {
    if (usage < 70) return 'success';
    if (usage < 90) return 'warning';
    return 'error';
  };

  return (
    <Paper elevation={2} sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        {t('health.title')}
      </Typography>

      <Grid container spacing={3}>
        {/* CPU Usage */}
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Box>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                mb: 1,
              }}
            >
              <SpeedIcon color="action" />
              <Typography variant="body2" color="text.secondary">
                {t('health.cpuUsage')}
              </Typography>
            </Box>
            <Typography variant="h5" sx={{ mb: 1 }}>
              {health.cpu_usage?.toFixed(1) ?? 0}%
            </Typography>
            <LinearProgress
              variant="determinate"
              value={health.cpu_usage ?? 0}
              color={getUsageColor(health.cpu_usage ?? 0)}
              sx={{ height: 8, borderRadius: 1 }}
            />
          </Box>
        </Grid>

        {/* Memory Usage */}
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Box>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                mb: 1,
              }}
            >
              <MemoryIcon color="action" />
              <Typography variant="body2" color="text.secondary">
                {t('health.memoryUsage')}
              </Typography>
            </Box>
            <Typography variant="h5" sx={{ mb: 1 }}>
              {health.memory_usage?.toFixed(1) ?? 0}%
            </Typography>
            <LinearProgress
              variant="determinate"
              value={health.memory_usage ?? 0}
              color={getUsageColor(health.memory_usage ?? 0)}
              sx={{ height: 8, borderRadius: 1 }}
            />
          </Box>
        </Grid>

        {/* Active Streams */}
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Box>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                mb: 1,
              }}
            >
              <CloudIcon color="action" />
              <Typography variant="body2" color="text.secondary">
                {t('health.activeStreams')}
              </Typography>
            </Box>
            <Typography variant="h5">{health.active_streams ?? 0}</Typography>
            <Typography variant="caption" color="text.secondary">
              {t('health.v20Connections')}
            </Typography>
          </Box>
        </Grid>

        {/* Celery Tasks */}
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Box>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                mb: 1,
              }}
            >
              <StorageIcon color="action" />
              <Typography variant="body2" color="text.secondary">
                {t('health.celeryTasks')}
              </Typography>
            </Box>
            <Typography variant="h5">{health.celery_tasks ?? 0}</Typography>
            <Typography variant="caption" color="text.secondary">
              {t('health.activeTasks')}
            </Typography>
          </Box>
        </Grid>

        {/* Connection Status */}
        <Grid size={{ xs: 12 }}>
          <Box
            sx={{
              display: 'flex',
              gap: 2,
              flexWrap: 'wrap',
              pt: 2,
              borderTop: 1,
              borderColor: 'divider',
            }}
          >
            <Chip
              icon={getStatusIcon(health.database_status ?? 'disconnected')}
              label={t('health.database')}
              color={getStatusColor(health.database_status ?? 'disconnected')}
              variant="outlined"
            />
            <Chip
              icon={getStatusIcon(health.redis_status ?? 'disconnected')}
              label={t('health.redis')}
              color={getStatusColor(health.redis_status ?? 'disconnected')}
              variant="outlined"
            />
            <Chip
              icon={getStatusIcon(health.oanda_api_status ?? 'disconnected')}
              label={t('health.oandaApi')}
              color={getStatusColor(health.oanda_api_status ?? 'disconnected')}
              variant="outlined"
            />
          </Box>
        </Grid>
      </Grid>

      <Box sx={{ mt: 2, textAlign: 'right' }}>
        <Typography variant="caption" color="text.secondary">
          {t('health.lastUpdate')}:{' '}
          {health.timestamp
            ? new Date(health.timestamp).toLocaleString()
            : 'N/A'}
        </Typography>
      </Box>
    </Paper>
  );
};

export default SystemHealthPanel;
