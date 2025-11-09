import React, { useState, useEffect, useCallback } from 'react';

import {
  Typography,
  Box,
  Alert,
  CircularProgress,
  Button,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Breadcrumbs } from '../common';
import type { AdminDashboardData } from '../../types/admin';
import SystemHealthPanel from './SystemHealthPanel';
import UserSessionList from './UserSessionList';
import RunningStrategyList from './RunningStrategyList';
import RecentEventsPanel from './RecentEventsPanel';

const AdminDashboard: React.FC = () => {
  const { t } = useTranslation('admin');
  const { user, token, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [dashboardData, setDashboardData] = useState<AdminDashboardData | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Check if user is admin
  useEffect(() => {
    if (!isAuthenticated || !user?.is_staff) {
      navigate('/');
    }
  }, [isAuthenticated, user, navigate]);

  // Fetch initial dashboard data
  const fetchDashboardData = useCallback(async () => {
    if (!token) return;

    try {
      const response = await fetch('/api/admin/dashboard', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch dashboard data');
      }

      const data = await response.json();
      setDashboardData(data);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load dashboard data'
      );
    } finally {
      setLoading(false);
    }
  }, [token]);

  // Set up WebSocket connection for real-time updates
  useEffect(() => {
    if (!token || !user?.is_staff) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/admin/dashboard/?token=${token}`;

    const websocket = new WebSocket(wsUrl);

    websocket.onopen = () => {
      console.log('Admin dashboard WebSocket connected');
    };

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Update dashboard data based on message type
        if (data.type === 'dashboard_update') {
          setDashboardData((prev) => {
            const incoming = data.data as AdminDashboardData;

            if (!prev) {
              return incoming;
            }

            return {
              ...prev,
              ...incoming,
              recent_events: incoming.recent_events ?? prev.recent_events ?? [],
              online_users: incoming.online_users ?? prev.online_users,
              running_strategies:
                incoming.running_strategies ?? prev.running_strategies,
              health: incoming.health ?? prev.health,
            };
          });
        } else if (data.type === 'metrics') {
          // Handle system metrics updates from backend
          setDashboardData((prev) => {
            if (!prev) return null;
            return {
              ...prev,
              health: {
                ...prev.health,
                cpu_usage: data.data.cpu_usage,
                memory_usage: data.data.memory_usage,
                disk_usage: data.data.disk_usage,
                timestamp: data.data.timestamp,
              },
            };
          });
        } else if (data.type === 'health_update') {
          setDashboardData((prev) =>
            prev ? { ...prev, health: data.data } : null
          );
        } else if (data.type === 'users_update') {
          setDashboardData((prev) =>
            prev ? { ...prev, online_users: data.data } : null
          );
        } else if (data.type === 'strategies_update') {
          setDashboardData((prev) =>
            prev ? { ...prev, running_strategies: data.data } : null
          );
        } else if (data.type === 'event') {
          setDashboardData((prev) => {
            if (!prev) return null;
            return {
              ...prev,
              recent_events: [data.data, ...(prev.recent_events ?? [])].slice(
                0,
                50
              ),
            };
          });
        } else if (data.type === 'pong') {
          // Ignore pong responses
        } else {
          console.warn('Unknown WebSocket message type:', data.type);
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    websocket.onclose = () => {
      console.log('Admin dashboard WebSocket disconnected');
    };

    return () => {
      websocket.close();
    };
  }, [token, user]);

  // Fetch initial data on mount
  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  // Handle user kick-off
  const handleKickOffUser = async (userId: number) => {
    if (!token) return;

    try {
      const response = await fetch(`/api/admin/users/${userId}/kickoff`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to kick off user');
      }

      // Refresh dashboard data
      await fetchDashboardData();
    } catch (err) {
      console.error('Failed to kick off user:', err);
      setError(err instanceof Error ? err.message : 'Failed to kick off user');
    }
  };

  // Handle strategy stop
  const handleStopStrategy = async (strategyId: number) => {
    if (!token) return;

    try {
      const response = await fetch(`/api/admin/strategies/${strategyId}/stop`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to stop strategy');
      }

      // Refresh dashboard data
      await fetchDashboardData();
    } catch (err) {
      console.error('Failed to stop strategy:', err);
      setError(err instanceof Error ? err.message : 'Failed to stop strategy');
    }
  };

  if (!user?.is_staff) {
    return null;
  }

  if (loading) {
    return (
      <Box
        sx={{
          width: '100%',
          maxWidth: '100vw',
          px: { xs: 2, sm: 3 },
          py: { xs: 2, sm: 4 },
          boxSizing: 'border-box',
        }}
      >
        <Box
          display="flex"
          justifyContent="center"
          alignItems="center"
          minHeight="60vh"
        >
          <CircularProgress />
        </Box>
      </Box>
    );
  }

  if (error) {
    return (
      <Box
        sx={{
          width: '100%',
          maxWidth: '100vw',
          px: { xs: 2, sm: 3 },
          py: { xs: 2, sm: 4 },
          boxSizing: 'border-box',
        }}
      >
        <Alert severity="error" sx={{ mb: 2, width: '100%' }}>
          {error}
        </Alert>
      </Box>
    );
  }

  if (!dashboardData) {
    return (
      <Box
        sx={{
          width: '100%',
          maxWidth: '100vw',
          px: { xs: 2, sm: 3 },
          py: { xs: 2, sm: 4 },
          boxSizing: 'border-box',
        }}
      >
        <Alert severity="info" sx={{ width: '100%' }}>
          {t('dashboard.noData')}
        </Alert>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: '100%',
        maxWidth: '100vw',
        px: { xs: 2, sm: 3 },
        py: { xs: 2, sm: 4 },
        boxSizing: 'border-box',
      }}
    >
      <Breadcrumbs />
      <Box sx={{ mb: 4, width: '100%' }}>
        <Typography variant="h4" gutterBottom>
          {t('dashboard.title')}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {t('dashboard.subtitle')}
        </Typography>
      </Box>

      <Grid container spacing={3}>
        {/* System Health Panel */}
        <Grid size={{ xs: 12 }}>
          <SystemHealthPanel health={dashboardData.health} />
        </Grid>

        {/* User Sessions and Running Strategies */}
        <Grid size={{ xs: 12, lg: 6 }}>
          <UserSessionList
            sessions={dashboardData.online_users ?? []}
            onKickOff={handleKickOffUser}
          />
        </Grid>

        <Grid size={{ xs: 12, lg: 6 }}>
          <RunningStrategyList
            strategies={dashboardData.running_strategies ?? []}
            onStop={handleStopStrategy}
          />
        </Grid>

        {/* Recent Events */}
        <Grid size={{ xs: 12 }}>
          <RecentEventsPanel events={dashboardData.recent_events ?? []} />
        </Grid>

        {/* Admin Actions */}
        <Grid size={{ xs: 12 }}>
          <Box
            sx={{
              display: 'flex',
              gap: 2,
              justifyContent: 'center',
              mt: 2,
              flexWrap: 'wrap',
            }}
          >
            <Button variant="outlined" onClick={() => navigate('/admin/users')}>
              User Management
            </Button>
            <Button
              variant="outlined"
              onClick={() => navigate('/admin/settings')}
            >
              System Settings
            </Button>
            <Button
              variant="outlined"
              onClick={() => navigate('/admin/whitelist')}
            >
              Email Whitelist
            </Button>
            <Button
              variant="outlined"
              onClick={() => navigate('/admin/events')}
            >
              {t('events.viewAll', 'View All Events')}
            </Button>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};

export default AdminDashboard;
