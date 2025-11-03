import { Container, Typography, Box } from '@mui/material';

const AdminDashboardPage = () => {
  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Admin Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Admin dashboard will be implemented in a future task
        </Typography>
      </Box>
    </Container>
  );
};

export default AdminDashboardPage;
