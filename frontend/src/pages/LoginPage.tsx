import { Container, Box, Typography, Paper } from '@mui/material';
import { useTranslation } from 'react-i18next';

const LoginPage = () => {
  const { t } = useTranslation('common');

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
            {t('auth.login')}
          </Typography>
          <Typography variant="body2" color="text.secondary" align="center">
            Login functionality will be implemented in a future task
          </Typography>
        </Paper>
      </Box>
    </Container>
  );
};

export default LoginPage;
