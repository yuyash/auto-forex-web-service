import { Container, Typography, Box } from '@mui/material';
import { useTranslation } from 'react-i18next';

const DashboardPage = () => {
  const { t } = useTranslation('dashboard');

  return (
    <Container maxWidth={false} sx={{ mt: 4, mb: 4, px: 3 }}>
      <Box>
        <Typography variant="h4" gutterBottom>
          {t('title')}
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {t('welcome')}
        </Typography>
      </Box>
    </Container>
  );
};

export default DashboardPage;
