import { Container, Typography, Box, Paper } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { Breadcrumbs } from '../components/common';
import { PreferencesForm } from '../components/settings';

const ProfilePage = () => {
  const { t } = useTranslation(['settings', 'common']);

  return (
    <Container maxWidth={false} sx={{ mt: 4, mb: 4, px: 3 }}>
      <Breadcrumbs />
      <Box>
        <Typography variant="h4" gutterBottom>
          {t('settings:profile.title', 'Profile')}
        </Typography>

        <Paper sx={{ p: 3, mt: 3 }}>
          <PreferencesForm />
        </Paper>
      </Box>
    </Container>
  );
};

export default ProfilePage;
