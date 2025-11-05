import React, { useEffect } from 'react';
import { Container, Typography, Box, Grid } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Breadcrumbs } from '../components/common';
import SystemSettingsPanel from '../components/admin/SystemSettingsPanel';
import EmailTestPanel from '../components/admin/EmailTestPanel';

const AdminSettingsPage: React.FC = () => {
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isAuthenticated || !user?.is_staff) {
      navigate('/');
    }
  }, [isAuthenticated, user, navigate]);

  if (!user?.is_staff) {
    return null;
  }

  return (
    <Container maxWidth={false} sx={{ mt: 4, mb: 4, px: 3 }}>
      <Breadcrumbs />
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          Admin Settings
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Manage system settings and test email configuration
        </Typography>
      </Box>

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, lg: 6 }}>
          <SystemSettingsPanel />
        </Grid>
        <Grid size={{ xs: 12, lg: 6 }}>
          <EmailTestPanel />
        </Grid>
      </Grid>
    </Container>
  );
};

export default AdminSettingsPage;
