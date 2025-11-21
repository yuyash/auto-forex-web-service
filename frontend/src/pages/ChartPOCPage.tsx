import React from 'react';
import { Container } from '@mui/material';
import FinancialChartPOC from '../components/chart/FinancialChartPOC';

const ChartPOCPage: React.FC = () => {
  return (
    <Container maxWidth="xl">
      <FinancialChartPOC />
    </Container>
  );
};

export default ChartPOCPage;
