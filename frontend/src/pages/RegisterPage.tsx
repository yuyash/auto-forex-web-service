import { Container, Box, Typography, Paper } from '@mui/material';

const RegisterPage = () => {
  return (
    <Container maxWidth="sm">
      <Box
        sx={{
          marginTop: 8,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
        }}
      >
        <Paper elevation={3} sx={{ p: 4, width: '100%' }}>
          <Typography component="h1" variant="h5" align="center" gutterBottom>
            Sign Up
          </Typography>
          <Typography variant="body2" color="text.secondary" align="center">
            Registration functionality will be implemented in a future task
          </Typography>
        </Paper>
      </Box>
    </Container>
  );
};

export default RegisterPage;
