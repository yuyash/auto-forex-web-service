import { Container, Typography, Box, Button } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

const NotFoundPage = () => {
  const { t } = useTranslation('common');

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
          {t('notFound.title')}
        </Typography>
        <Typography variant="h5" gutterBottom>
          {t('notFound.heading')}
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          {t('notFound.message')}
        </Typography>
        <Button
          variant="contained"
          component={RouterLink}
          to="/"
          sx={{ mt: 2 }}
        >
          {t('notFound.goHome')}
        </Button>
      </Box>
    </Container>
  );
};

export default NotFoundPage;
