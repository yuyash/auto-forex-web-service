import { Container, Typography, Box } from '@mui/material';

const PositionsPage = () => {
  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Positions
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Positions management will be implemented in a future task
        </Typography>
      </Box>
    </Container>
  );
};

export default PositionsPage;
