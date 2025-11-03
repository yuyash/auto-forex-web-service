import { Container, Typography, Box } from '@mui/material';

const StrategyPage = () => {
  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Strategy Configuration
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Strategy configuration will be implemented in a future task
        </Typography>
      </Box>
    </Container>
  );
};

export default StrategyPage;
