import { Container, Typography, Box, Button } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';

const NotFoundPage = () => {
  return (
    <Container maxWidth="sm">
      <Box
        sx={{
          marginTop: 8,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
        }}
      >
        <Typography variant="h1" component="h1" gutterBottom>
          404
        </Typography>
        <Typography variant="h5" gutterBottom>
          Page Not Found
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          The page you are looking for does not exist.
        </Typography>
        <Button
          variant="contained"
          component={RouterLink}
          to="/"
          sx={{ mt: 2 }}
        >
          Go to Home
        </Button>
      </Box>
    </Container>
  );
};

export default NotFoundPage;
