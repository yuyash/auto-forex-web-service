import { Container, Typography, Box } from '@mui/material';

const OrdersPage = () => {
  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Orders History
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Orders history will be implemented in a future task
        </Typography>
      </Box>
    </Container>
  );
};

export default OrdersPage;
