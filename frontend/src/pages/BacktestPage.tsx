import { Container, Typography, Box } from '@mui/material';

const BacktestPage = () => {
  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Backtesting
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Backtesting functionality will be implemented in a future task
        </Typography>
      </Box>
    </Container>
  );
};

export default BacktestPage;
