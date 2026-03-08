import { useState } from 'react';
import { Container, Typography, Box, Tabs, Tab, Paper } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { Breadcrumbs } from '../components/common';
import {
  AccountManagement,
  GeneralSettings,
  DisplaySettings,
  DataSettings,
} from '../components/settings';

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

        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs
            value={tabValue}
            onChange={handleTabChange}
            aria-label="settings tabs"
            variant="scrollable"
            scrollButtons="auto"
          >
            <Tab
              label={t('tabs.general')}
              id="settings-tab-0"
              aria-controls="settings-tabpanel-0"
            />
            <Tab
              label={t('tabs.display')}
              id="settings-tab-1"
              aria-controls="settings-tabpanel-1"
            />
            <Tab
              label={t('tabs.data')}
              id="settings-tab-2"
              aria-controls="settings-tabpanel-2"
            />
            <Tab
              label={t('tabs.accounts')}
              id="settings-tab-3"
              aria-controls="settings-tabpanel-3"
            />
          </Tabs>
        </Box>

        {/* General Tab */}
        <TabPanel value={tabValue} index={0}>
          <Paper sx={{ p: 3 }}>
            <GeneralSettings />
          </Paper>
        </TabPanel>

        {/* Display Tab */}
        <TabPanel value={tabValue} index={1}>
          <Paper sx={{ p: 3 }}>
            <DisplaySettings />
          </Paper>
        </TabPanel>

        {/* Data Tab */}
        <TabPanel value={tabValue} index={2}>
          <Paper sx={{ p: 3 }}>
            <DataSettings />
          </Paper>
        </TabPanel>

        {/* Accounts Tab */}
        <TabPanel value={tabValue} index={3}>
          <Paper sx={{ p: 3 }}>
            <AccountManagement />
          </Paper>
        </TabPanel>
      </Box>
    </Container>
  );
};

export default SettingsPage;
