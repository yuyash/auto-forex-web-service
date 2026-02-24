import { useState, useEffect } from 'react';

import {
  Container,
  Typography,
  Box,
  Paper,
  Alert,
  MenuItem,
  Switch,
  IconButton,
  Popover,
  MenuList,
  ListItemText,
  Tooltip,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import CurrencyExchangeIcon from '@mui/icons-material/CurrencyExchange';
import BarChartIcon from '@mui/icons-material/BarChart';
import TimerIcon from '@mui/icons-material/Timer';
import { useTranslation } from 'react-i18next';
import { useOandaAccounts } from '../hooks/useOandaAccounts';
import { useChartPreferences } from '../hooks/useChartPreferences';
import { Breadcrumbs } from '../components/common';
import ActiveTasksWidget from '../components/dashboard/ActiveTasksWidget';
import RecentBacktestsWidget from '../components/dashboard/RecentBacktestsWidget';
import QuickActionsWidget from '../components/dashboard/QuickActionsWidget';
import MarketChart from '../components/dashboard/MarketChart';
import ChartOverlayControls, {
  DEFAULT_OVERLAY_SETTINGS,
  type OverlaySettings,
} from '../components/dashboard/ChartOverlayControls';
import type { Granularity } from '../types/chart';

const DashboardPage = () => {
  const { t } = useTranslation('dashboard');

  // Chart preferences with localStorage persistence
  const { preferences, updatePreference } = useChartPreferences();
  const { autoRefreshEnabled, refreshInterval } = preferences;

  // Data state
  const [error] = useState<string | null>(null);
  const [overlays, setOverlays] = useState<OverlaySettings>(
    DEFAULT_OVERLAY_SETTINGS
  );

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

  // Popover anchors
  const [instrumentAnchor, setInstrumentAnchor] =
    useState<HTMLButtonElement | null>(null);
  const [granularityAnchor, setGranularityAnchor] =
    useState<HTMLButtonElement | null>(null);
  const [intervalAnchor, setIntervalAnchor] =
    useState<HTMLButtonElement | null>(null);

  // Handle refresh interval change
  const handleRefreshIntervalChange = (val: number) => {
    updatePreference('refreshInterval', val);
    setIntervalAnchor(null);
  };

  // Handle auto-refresh toggle
  const handleAutoRefreshToggle = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    updatePreference('autoRefreshEnabled', event.target.checked);
  };

  // Handle instrument change
  const handleInstrumentChange = (val: string) => {
    updatePreference('instrument', val);
    setInstrumentAnchor(null);
  };

  // Handle granularity change
  const handleGranularityChange = (val: string) => {
    updatePreference('granularity', val as Granularity);
    setGranularityAnchor(null);
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

          <ChartOverlayControls settings={overlays} onChange={setOverlays} />

          {/* Instrument */}
          <Tooltip
            title={`Instrument: ${preferences.instrument.replace('_', '/')}`}
          >
            <IconButton
              size="small"
              onClick={(e) => setInstrumentAnchor(e.currentTarget)}
              aria-label="Select instrument"
            >
              <CurrencyExchangeIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Popover
            open={Boolean(instrumentAnchor)}
            anchorEl={instrumentAnchor}
            onClose={() => setInstrumentAnchor(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          >
            <MenuList dense>
              {[
                'USD_JPY',
                'EUR_USD',
                'GBP_USD',
                'AUD_USD',
                'EUR_JPY',
                'GBP_JPY',
              ].map((v) => (
                <MenuItem
                  key={v}
                  selected={v === preferences.instrument}
                  onClick={() => handleInstrumentChange(v)}
                >
                  <ListItemText>{v.replace('_', '/')}</ListItemText>
                </MenuItem>
              ))}
            </MenuList>
          </Popover>

          {/* Granularity */}
          <Tooltip title={`Granularity: ${preferences.granularity}`}>
            <IconButton
              size="small"
              onClick={(e) => setGranularityAnchor(e.currentTarget)}
              aria-label="Select granularity"
            >
              <BarChartIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Popover
            open={Boolean(granularityAnchor)}
            anchorEl={granularityAnchor}
            onClose={() => setGranularityAnchor(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          >
            <MenuList dense>
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
                <MenuItem
                  key={v}
                  selected={v === preferences.granularity}
                  onClick={() => handleGranularityChange(v)}
                >
                  <ListItemText>{v}</ListItemText>
                </MenuItem>
              ))}
            </MenuList>
          </Popover>

          {/* Auto-refresh toggle */}
          <Switch
            size="small"
            checked={autoRefreshEnabled}
            onChange={handleAutoRefreshToggle}
            inputProps={{ 'aria-label': 'Auto-refresh' }}
          />

          {/* Refresh interval */}
          <Tooltip title={`Interval: ${refreshInterval}s`}>
            <span>
              <IconButton
                size="small"
                onClick={(e) => setIntervalAnchor(e.currentTarget)}
                disabled={!autoRefreshEnabled}
                aria-label="Select refresh interval"
              >
                <TimerIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Popover
            open={Boolean(intervalAnchor)}
            anchorEl={intervalAnchor}
            onClose={() => setIntervalAnchor(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          >
            <MenuList dense>
              {[
                { v: 10, l: '10s' },
                { v: 30, l: '30s' },
                { v: 60, l: '1min' },
                { v: 120, l: '2min' },
                { v: 300, l: '5min' },
              ].map(({ v, l }) => (
                <MenuItem
                  key={v}
                  selected={v === refreshInterval}
                  onClick={() => handleRefreshIntervalChange(v)}
                >
                  <ListItemText>{l}</ListItemText>
                </MenuItem>
              ))}
            </MenuList>
          </Popover>
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
              overlays={overlays}
            />
          )}
        </Box>
      </Paper>
    </Container>
  );
};

export default DashboardPage;
