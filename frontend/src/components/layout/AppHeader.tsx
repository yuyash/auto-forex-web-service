import { AppBar, Toolbar, Typography, Button, Box } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import LanguageSelector from '../common/LanguageSelector';

const AppHeader = () => {
  const { t } = useTranslation('common');

  return (
    <AppBar position="static">
      <Toolbar>
        <Typography
          variant="h6"
          component={RouterLink}
          to="/"
          sx={{
            flexGrow: 1,
            textDecoration: 'none',
            color: 'inherit',
          }}
        >
          {t('app.name')}
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <Button color="inherit" component={RouterLink} to="/dashboard">
            {t('navigation.dashboard')}
          </Button>
          <Button color="inherit" component={RouterLink} to="/orders">
            {t('navigation.orders')}
          </Button>
          <Button color="inherit" component={RouterLink} to="/positions">
            {t('navigation.positions')}
          </Button>
          <Button color="inherit" component={RouterLink} to="/strategy">
            {t('navigation.strategy')}
          </Button>
          <Button color="inherit" component={RouterLink} to="/backtest">
            {t('navigation.backtest')}
          </Button>
          <Button color="inherit" component={RouterLink} to="/settings">
            {t('navigation.settings')}
          </Button>
          <LanguageSelector />
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default AppHeader;
