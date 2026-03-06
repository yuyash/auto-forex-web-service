import { useState } from 'react';
import { Container, Typography, Box, Tabs, Tab, Paper } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { Breadcrumbs } from '../components/common';
import { AccountManagement } from '../components/settings';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = (props: TabPanelProps) => {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`settings-tabpanel-${index}`}
      aria-labelledby={`settings-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
};

const SettingsPage = () => {
  const { t } = useTranslation('settings');
  const [tabValue, setTabValue] = useState(0);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  return (
    <Container maxWidth={false} sx={{ mt: 4, mb: 4, px: 3 }}>
      <Breadcrumbs />
      <Box>
        <Typography variant="h4" gutterBottom>
          {t('title')}
        </Typography>

        {/* Tabs for different settings sections */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs
            value={tabValue}
            onChange={handleTabChange}
            aria-label="settings tabs"
          >
            <Tab
              label={t('tabs.accounts')}
              id="settings-tab-0"
              aria-controls="settings-tabpanel-0"
            />
            <Tab
              label={t('tabs.security')}
              id="settings-tab-1"
              aria-controls="settings-tabpanel-1"
            />
          </Tabs>
        </Box>

        {/* Accounts Tab */}
        <TabPanel value={tabValue} index={0}>
          <Paper sx={{ p: 3 }}>
            <AccountManagement />
          </Paper>
        </TabPanel>

        {/* Security Tab */}
        <TabPanel value={tabValue} index={1}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              {t('security.title')}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t('security.placeholder')}
            </Typography>
          </Paper>
        </TabPanel>
      </Box>
    </Container>
  );
};

export default SettingsPage;
