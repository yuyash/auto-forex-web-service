import React from 'react';
import { Container, Typography, Box } from '@mui/material';
import { DashboardChart } from '../components/chart/DashboardChart';

const ChartPOCPage: React.FC = () => {
  return (
    <Container maxWidth="xl" sx={{ mt: 4 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          Chart POC
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Proof of concept page for testing chart functionality
        </Typography>
      </Box>
      <DashboardChart instrument="EUR_USD" granularity="H1" height={600} />
    </Container>
  );
};

export default ChartPOCPage;
