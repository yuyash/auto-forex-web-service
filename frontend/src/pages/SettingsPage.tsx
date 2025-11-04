import { Container, Typography, Box } from '@mui/material';

const SettingsPage = () => {
  return (
    <Container maxWidth={false} sx={{ mt: 4, mb: 4, px: 3 }}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Settings
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Settings page will be implemented in a future task
        </Typography>
      </Box>
    </Container>
  );
};

export default SettingsPage;
