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
import type { Granularity } from '../types/chart';

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
  const handleInstrumentChange = (event: SelectChangeEvent<string>) => {
    updatePreference('instrument', event.target.value);
  };

  // Handle granularity change
  const handleGranularityChange = (event: SelectChangeEvent<string>) => {
    updatePreference('granularity', event.target.value as Granularity);
  };

  return (
    <Container
      maxWidth={false}
      sx={{
        mt: 4,
        mb: 4,
        px: 3,
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - 64px)',
        overflow: 'hidden',
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
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          overflow: 'hidden',
        }}
      >
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'row',
            alignItems: 'center',
            gap: 1.5,
            flexWrap: 'wrap',
            mb: 1,
            flexShrink: 0,
          }}
        >
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mr: 'auto' }}>
            Market Chart
          </Typography>

          <FormControl
            size="small"
            sx={{
              minWidth: 110,
              '& .MuiInputLabel-root': { fontSize: '0.8rem' },
              '& .MuiSelect-select': { fontSize: '0.8rem', py: 0.5 },
            }}
          >
            <InputLabel id="instrument-label">Instrument</InputLabel>
            <Select
              labelId="instrument-label"
              value={preferences.instrument}
              label="Instrument"
              onChange={handleInstrumentChange}
            >
              {[
                'USD_JPY',
                'EUR_USD',
                'GBP_USD',
                'AUD_USD',
                'EUR_JPY',
                'GBP_JPY',
              ].map((v) => (
                <MenuItem key={v} value={v} sx={{ fontSize: '0.8rem' }}>
                  {v.replace('_', '/')}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl
            size="small"
            sx={{
              minWidth: 100,
              '& .MuiInputLabel-root': { fontSize: '0.8rem' },
              '& .MuiSelect-select': { fontSize: '0.8rem', py: 0.5 },
            }}
          >
            <InputLabel id="granularity-label">Granularity</InputLabel>
            <Select
              labelId="granularity-label"
              value={preferences.granularity}
              label="Granularity"
              onChange={handleGranularityChange}
            >
              {(
                [
                  'M1',
                  'M5',
                  'M15',
                  'M30',
                  'H1',
                  'H4',
                  'D',
                  'W',
                ] as Granularity[]
              ).map((v) => (
                <MenuItem key={v} value={v} sx={{ fontSize: '0.8rem' }}>
                  {v}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControlLabel
            control={
              <Switch
                checked={autoRefreshEnabled}
                onChange={handleAutoRefreshToggle}
                size="small"
              />
            }
            label="Auto-refresh"
            sx={{
              ml: 0.5,
              '& .MuiFormControlLabel-label': { fontSize: '0.8rem' },
            }}
          />

          <FormControl
            size="small"
            sx={{
              minWidth: 100,
              '& .MuiInputLabel-root': { fontSize: '0.8rem' },
              '& .MuiSelect-select': { fontSize: '0.8rem', py: 0.5 },
            }}
          >
            <InputLabel id="refresh-interval-label">Interval</InputLabel>
            <Select
              labelId="refresh-interval-label"
              value={refreshInterval}
              label="Interval"
              onChange={handleRefreshIntervalChange}
              disabled={!autoRefreshEnabled}
            >
              <MenuItem value={10} sx={{ fontSize: '0.8rem' }}>
                10s
              </MenuItem>
              <MenuItem value={30} sx={{ fontSize: '0.8rem' }}>
                30s
              </MenuItem>
              <MenuItem value={60} sx={{ fontSize: '0.8rem' }}>
                1min
              </MenuItem>
              <MenuItem value={120} sx={{ fontSize: '0.8rem' }}>
                2min
              </MenuItem>
              <MenuItem value={300} sx={{ fontSize: '0.8rem' }}>
                5min
              </MenuItem>
            </Select>
          </FormControl>
        </Box>

        <Box
          sx={{
            width: '100%',
            position: 'relative',
            flex: 1,
            minHeight: 0,
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
              fillHeight
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
