import React, { useEffect } from 'react';
import { Container, Typography, Box } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Breadcrumbs } from '../components/common';
import UserManagement from '../components/admin/UserManagement';

const UserManagementPage: React.FC = () => {
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  // Check if user is admin
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
          User Management
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Manage system users, create new accounts, and control access
        </Typography>
      </Box>

      <UserManagement />
    </Container>
  );
};

export default UserManagementPage;
