import { useState, useEffect } from 'react';

import {
  Container,
  Typography,
  Box,
  Paper,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import type { SelectChangeEvent } from '@mui/material/Select';
import { useTranslation } from 'react-i18next';
import { useOandaAccounts } from '../hooks/useOandaAccounts';
import { useChartPreferences } from '../hooks/useChartPreferences';
import { Breadcrumbs } from '../components/common';
import ActiveTasksWidget from '../components/dashboard/ActiveTasksWidget';
import RecentBacktestsWidget from '../components/dashboard/RecentBacktestsWidget';
import QuickActionsWidget from '../components/dashboard/QuickActionsWidget';
import MarketChart from '../components/dashboard/MarketChart';

const DashboardPage = () => {
  const { t } = useTranslation('dashboard');

  // Chart preferences with localStorage persistence
  const { preferences, updatePreference } = useChartPreferences();
  const { autoRefreshEnabled, refreshInterval } = preferences;

  // Data state
  const [error] = useState<string | null>(null);

  // OANDA account state - using shared hook with caching
  const {
    accounts: oandaAccounts,
    hasAccounts: hasOandaAccount,
    isLoading: accountsLoading,
  } = useOandaAccounts();

  // Log account state
  useEffect(() => {
    console.log('[DashboardPage] OANDA accounts state', {
      accountCount: oandaAccounts.length,
      hasOandaAccount,
      isLoading: accountsLoading,
      accounts: oandaAccounts.map((a) => ({
        id: a.id,
        account_id: a.account_id,
        is_default: a.is_default,
      })),
    });
  }, [oandaAccounts, hasOandaAccount, accountsLoading]);

  // Use default account or first account
  const defaultAccount =
    oandaAccounts.find((acc) => acc.is_default) || oandaAccounts[0];
  const oandaAccountId = defaultAccount?.account_id;

  console.log('[DashboardPage] Selected account', {
    hasDefaultAccount: !!defaultAccount,
    accountId: oandaAccountId,
  });

  // Handle refresh interval change
  const handleRefreshIntervalChange = (event: SelectChangeEvent<number>) => {
    updatePreference('refreshInterval', Number(event.target.value));
  };

  // Handle auto-refresh toggle
  const handleAutoRefreshToggle = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    updatePreference('autoRefreshEnabled', event.target.checked);
  };

  // Handle instrument change
  // const handleInstrumentChange = (newInstrument: string) => {
  //   updatePreference('instrument', newInstrument);
  // };

  // Handle granularity change
  // const handleGranularityChange = (newGranularity: Granularity) => {
  //   updatePreference('granularity', newGranularity);
  // };

  return (
    <Container maxWidth={false} sx={{ mt: 4, mb: 4, px: 3 }}>
      <Breadcrumbs />

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Task Widgets */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
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
      <Paper elevation={2} sx={{ p: { xs: 2, sm: 3 }, mb: 3 }}>
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', sm: 'row' },
            justifyContent: 'space-between',
            alignItems: { xs: 'flex-start', sm: 'center' },
            gap: 2,
            mb: 2,
          }}
        >
          <Box>
            <Typography variant="h6">Market Chart</Typography>
          </Box>

          {/* Auto-refresh controls */}
          <Box
            sx={{
              display: 'flex',
              flexDirection: { xs: 'column', sm: 'row' },
              gap: 2,
              alignItems: { xs: 'stretch', sm: 'center' },
              width: { xs: '100%', sm: 'auto' },
            }}
          >
            <FormControlLabel
              control={
                <Switch
                  checked={autoRefreshEnabled}
                  onChange={handleAutoRefreshToggle}
                  size="small"
                />
              }
              label="Auto-refresh"
              sx={{ '& .MuiFormControlLabel-label': { fontSize: '0.875rem' } }}
            />

            <FormControl
              size="small"
              sx={{
                minWidth: { xs: '100%', sm: 120 },
                '& .MuiInputLabel-root': { fontSize: '0.875rem' },
                '& .MuiSelect-select': { fontSize: '0.875rem' },
              }}
            >
              <InputLabel id="refresh-interval-label">Interval</InputLabel>
              <Select
                labelId="refresh-interval-label"
                id="refresh-interval-select"
                value={refreshInterval}
                label="Interval"
                onChange={handleRefreshIntervalChange}
                disabled={!autoRefreshEnabled}
              >
                <MenuItem value={10} sx={{ fontSize: '0.875rem' }}>
                  10 seconds
                </MenuItem>
                <MenuItem value={30} sx={{ fontSize: '0.875rem' }}>
                  30 seconds
                </MenuItem>
                <MenuItem value={60} sx={{ fontSize: '0.875rem' }}>
                  1 minute
                </MenuItem>
                <MenuItem value={120} sx={{ fontSize: '0.875rem' }}>
                  2 minutes
                </MenuItem>
                <MenuItem value={300} sx={{ fontSize: '0.875rem' }}>
                  5 minutes
                </MenuItem>
              </Select>
            </FormControl>
          </Box>
        </Box>

        <Box
          sx={{
            display: 'flex',
            flexDirection: 'row',
            alignItems: 'center',
            gap: 2,
            flexWrap: 'wrap',
            mb: 1.25,
          }}
        >
          {/* TODO: Implement ChartControls with new chart components */}
          {/* <ChartControls
            instrument={instrument}
            granularity={granularity}
            onInstrumentChange={handleInstrumentChange}
            onGranularityChange={handleGranularityChange}
            onResetView={handleChartResetView}
            onUpdateView={handleChartUpdateView}
            showResetButton={hasOandaAccount}
            showUpdateButton={hasOandaAccount}
          /> */}
        </Box>

        <Box
          sx={{
            width: '100%',
            position: 'relative',
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
                {t('chart.noOandaAccount')}
              </Typography>
            </Box>
          ) : (
            <MarketChart
              instrument={preferences.instrument}
              granularity={preferences.granularity}
              accountId={oandaAccountId}
              height={500}
              autoRefresh={autoRefreshEnabled}
              refreshInterval={refreshInterval}
            />
          )}
        </Box>
      </Paper>
    </Container>
  );
};

export default DashboardPage;
