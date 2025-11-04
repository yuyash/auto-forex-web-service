import React, { useEffect } from 'react';
import { Container } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import EventViewer from '../components/admin/EventViewer';

const EventViewerPage: React.FC = () => {
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
      <EventViewer />
    </Container>
  );
};

export default EventViewerPage;
