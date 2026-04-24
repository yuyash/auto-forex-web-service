import { useState } from 'react';

import { Box, Paper, Alert, Typography } from '@mui/material';
import Grid from '@mui/material/Grid';
import { useTranslation } from 'react-i18next';
import { useDefaultOandaAccount } from '../hooks/useOandaAccounts';
import { useChartPreferences } from '../hooks/useChartPreferences';
import { useAppSettings } from '../hooks/useAppSettings';
import { useOandaHealthStatus } from '../hooks/useOandaHealthStatus';
import {
  useSupportedGranularities,
  useSupportedInstruments,
} from '../hooks/useMarketConfig';
import { Breadcrumbs, PageContainer } from '../components/common';
import ActiveTasksWidget from '../components/dashboard/ActiveTasksWidget';
import RecentBacktestsWidget from '../components/dashboard/RecentBacktestsWidget';
import QuickActionsWidget from '../components/dashboard/QuickActionsWidget';
import DashboardChartToolbar from '../components/dashboard/DashboardChartToolbar';
import MarketChart from '../components/dashboard/MarketChart';
import {
  DEFAULT_OVERLAY_SETTINGS,
  type OverlaySettings,
} from '../components/dashboard/chartOverlaySettings';
import type { Granularity } from '../types/chart';

const DashboardPage = () => {
  const { t } = useTranslation(['dashboard', 'common']);
  const { settings: appSettings } = useAppSettings();
  const { instruments, usingFallback: usingInstrumentFallback } =
    useSupportedInstruments();
  const { granularities, usingFallback: usingGranularityFallback } =
    useSupportedGranularities();

  // Chart preferences with localStorage persistence
  const { preferences, updatePreference } = useChartPreferences();
  const { autoRefreshEnabled, refreshInterval } = preferences;

  // Data state
  const [error] = useState<string | null>(null);
  const [overlays, setOverlays] = useState<OverlaySettings>(
    DEFAULT_OVERLAY_SETTINGS
  );

  // OANDA account state - using shared hook with caching
  const { defaultAccount, hasAccounts: hasOandaAccount } =
    useDefaultOandaAccount();

  useOandaHealthStatus({
    enabled: hasOandaAccount,
    refreshIntervalMs: appSettings.healthCheckIntervalSeconds * 1000,
    activeCheck: true,
  });

  // Use default account or first account
  const oandaAccountId = defaultAccount?.account_id;

  const instrumentOptions = Array.from(
    new Set([preferences.instrument, ...instruments].filter(Boolean))
  );
  const granularityOptions = Array.from(
    new Map(
      [
        { value: preferences.granularity, label: preferences.granularity },
        ...granularities,
      ].map((granularity) => [granularity.value, granularity])
    ).values()
  );

  // Handle refresh interval change
  const handleRefreshIntervalChange = (val: number) => {
    updatePreference('refreshInterval', val);
  };

  // Handle auto-refresh toggle
  const handleAutoRefreshToggle = (checked: boolean) => {
    updatePreference('autoRefreshEnabled', checked);
  };

  // Handle instrument change
  const handleInstrumentChange = (val: string) => {
    updatePreference('instrument', val);
  };

  // Handle granularity change
  const handleGranularityChange = (val: string) => {
    updatePreference('granularity', val as Granularity);
  };

  return (
    <PageContainer
      sx={{
        mt: 4,
        mb: 4,
        display: 'flex',
        flexDirection: 'column',
        height: { xs: 'auto', md: 'calc(100vh - 64px)' },
        overflow: { xs: 'auto', md: 'hidden' },
      }}
    >
      <Breadcrumbs />

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Task Widgets */}
      <Grid container spacing={3} sx={{ mb: 3, flexShrink: 0 }}>
        <Grid size={{ xs: 12, md: 4 }}>
          <ActiveTasksWidget />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <RecentBacktestsWidget />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <QuickActionsWidget />
        </Grid>
      </Grid>

      {/* Chart Section */}
      <Paper
        elevation={2}
        sx={{
          p: { xs: 1.5, sm: 2 },
          mb: 3,
          flex: { xs: 'none', md: 1 },
          display: 'flex',
          flexDirection: 'column',
          minHeight: { xs: 'auto', md: 0 },
          overflow: 'hidden',
        }}
      >
        <DashboardChartToolbar
          instrument={preferences.instrument}
          granularity={preferences.granularity}
          autoRefreshEnabled={autoRefreshEnabled}
          refreshInterval={refreshInterval}
          instruments={instrumentOptions}
          granularities={granularityOptions}
          intervals={[
            { value: 10, label: '10s' },
            { value: 30, label: '30s' },
            { value: 60, label: '1min' },
            { value: 120, label: '2min' },
            { value: 300, label: '5min' },
          ]}
          usingInstrumentFallback={usingInstrumentFallback}
          usingGranularityFallback={usingGranularityFallback}
          overlays={overlays}
          onOverlaysChange={setOverlays}
          onInstrumentChange={handleInstrumentChange}
          onGranularityChange={handleGranularityChange}
          onAutoRefreshToggle={handleAutoRefreshToggle}
          onRefreshIntervalChange={handleRefreshIntervalChange}
        />

        <Box
          sx={{
            width: '100%',
            position: 'relative',
            flex: { xs: 'none', md: 1 },
            height: { xs: 360, sm: 440, md: 'auto' },
            minHeight: { xs: 360, sm: 440, md: 0 },
          }}
        >
          {!hasOandaAccount ? (
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                height: '100%',
                border: '1px solid #e1e1e1',
                borderRadius: 1,
                backgroundColor: '#f5f5f5',
              }}
            >
              <Typography variant="body1" color="text.secondary">
                {t('dashboard:chart.noOandaAccount')}
              </Typography>
            </Box>
          ) : (
            <MarketChart
              instrument={preferences.instrument}
              granularity={preferences.granularity}
              accountId={oandaAccountId}
              fillHeight
              autoRefresh={autoRefreshEnabled}
              refreshInterval={refreshInterval}
              overlays={overlays}
            />
          )}
        </Box>
      </Paper>
    </PageContainer>
  );
};

export default DashboardPage;
