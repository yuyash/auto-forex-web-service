import { useState, useEffect, useRef } from 'react';

import {
  Box,
  Container,
  Typography,
  Button,
  Tabs,
  Tab,
  TextField,
  InputAdornment,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Paper,
  Pagination,
  Alert,
  AlertTitle,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import {
  Add as AddIcon,
  Search as SearchIcon,
  Warning as WarningIcon,
  Settings as SettingsIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  useTradingTasks,
  invalidateTradingTasksCache,
} from '../hooks/useTradingTasks';
import { useConfigurations } from '../hooks/useConfigurations';
import { TaskStatus } from '../types/common';
import TradingTaskCard from '../components/trading/TradingTaskCard';
import { Breadcrumbs } from '../components/common';
import { LoadingSpinner } from '../components/common';
import { useStrategies, getStrategyDisplayName } from '../hooks/useStrategies';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`trading-tasks-tabpanel-${index}`}
      aria-labelledby={`trading-tasks-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
}

function a11yProps(index: number) {
  return {
    id: `trading-tasks-tab-${index}`,
    'aria-controls': `trading-tasks-tabpanel-${index}`,
  };
}

export default function TradingTasksPage() {
  const { t } = useTranslation(['trading', 'common']);
  const navigate = useNavigate();
  const location = useLocation();
  const [tabValue, setTabValue] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('-created_at');
  const [configFilter, setConfigFilter] = useState<string | ''>('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Force refetch when navigating back after a deletion
  useEffect(() => {
    if (location.state?.deleted) {
      invalidateTradingTasksCache();
      // Clear the state so it doesn't re-trigger on subsequent renders
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state?.deleted, navigate, location.pathname]);

  // Determine status filter based on active tab
  const getStatusFilter = (): TaskStatus | undefined => {
    switch (tabValue) {
      case 1:
        return TaskStatus.RUNNING;
      case 2:
        return TaskStatus.PAUSED;
      case 3:
        return TaskStatus.STOPPED;
      default:
        return undefined; // All tasks
    }
  };

  const { data, isLoading, error, refetch } = useTradingTasks({
    page,
    page_size: pageSize,
    search: searchQuery || undefined,
    status: getStatusFilter(),
    config_id: configFilter || undefined,
    ordering: sortBy,
  });

  // Auto-refresh every 10 seconds when there are running tasks
  // This ensures status changes are detected across all pages
  const autoRefreshIntervalRef = useRef<ReturnType<typeof setInterval> | null>(
    null
  );

  useEffect(() => {
    const hasRunningTasks = data?.results.some(
      (task) =>
        task.status === TaskStatus.RUNNING || task.status === TaskStatus.PAUSED
    );

    // Clear existing interval
    if (autoRefreshIntervalRef.current) {
      clearInterval(autoRefreshIntervalRef.current);
      autoRefreshIntervalRef.current = null;
    }

    // Set up auto-refresh if there are running tasks
    if (hasRunningTasks) {
      autoRefreshIntervalRef.current = setInterval(() => {
        console.log('[TradingTasksPage] Auto-refreshing task list');
        refetch();
      }, 10000); // 10 seconds
    }

    return () => {
      if (autoRefreshIntervalRef.current) {
        clearInterval(autoRefreshIntervalRef.current);
      }
    };
  }, [data?.results, refetch]);

  const handleRefresh = () => {
    refetch();
  };

  // Fetch configurations for filter dropdown and strategies
  const { data: configurationsData } = useConfigurations({
    page: 1,
    page_size: 100, // Get enough for dropdown
  });
  const { strategies } = useStrategies();

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
    setPage(1); // Reset to first page when changing tabs
  };

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value);
    setPage(1); // Reset to first page when searching
  };

  const handleSortChange = (event: { target: { value: string } }) => {
    setSortBy(event.target.value);
    setPage(1);
  };

  const handleConfigFilterChange = (event: {
    target: { value: string | '' };
  }) => {
    setConfigFilter(event.target.value);
    setPage(1);
  };

  const handlePageChange = (
    _event: React.ChangeEvent<unknown>,
    value: number
  ) => {
    setPage(value);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleCreateTask = () => {
    navigate('/trading-tasks/new');
  };

  const totalPages = data ? Math.ceil(data.count / pageSize) : 0;

  return (
    <Container maxWidth={false}>
      <Box sx={{ py: 4 }}>
        <Breadcrumbs />

        {/* Header */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 3,
            flexWrap: 'wrap',
            gap: 2,
          }}
        >
          <Typography variant="h4" component="h1">
            {t('trading:pages.title')}
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={handleRefresh}
              disabled={isLoading}
            >
              {t('common:actions.refresh')}
            </Button>
            <Button
              variant="outlined"
              startIcon={<SettingsIcon />}
              onClick={() => navigate('/settings?tab=accounts')}
            >
              {t('settings:accounts.title', 'Account Settings')}
            </Button>
            <Button
              variant="outlined"
              onClick={() => navigate('/configurations?from=trading-tasks')}
            >
              {t(
                'configuration:card.manageConfigurations',
                'Manage Configurations'
              )}
            </Button>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleCreateTask}
            >
              {t('common:actions.newTask')}
            </Button>
          </Box>
        </Box>

        {/* Warning about one-task-per-account rule */}
        <Alert severity="warning" icon={<WarningIcon />} sx={{ mb: 3 }}>
          <AlertTitle>
            {t('trading:warnings.oneTaskPerAccountTitle')}
          </AlertTitle>
          {t('trading:warnings.oneTaskPerAccountMessage')}
        </Alert>

        {/* Tabs */}
        <Paper sx={{ mb: 3 }}>
          <Tabs
            value={tabValue}
            onChange={handleTabChange}
            aria-label="trading tasks tabs"
            sx={{ borderBottom: 1, borderColor: 'divider' }}
          >
            <Tab label={t('trading:tabs.all')} {...a11yProps(0)} />
            <Tab label={t('trading:tabs.running')} {...a11yProps(1)} />
            <Tab label={t('trading:tabs.paused')} {...a11yProps(2)} />
            <Tab label={t('trading:tabs.stopped')} {...a11yProps(3)} />
          </Tabs>
        </Paper>

        {/* Filters */}
        <Paper sx={{ p: 2, mb: 3 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid size={{ xs: 12, md: 4 }}>
              <TextField
                fullWidth
                placeholder={t('trading:filters.searchTasks')}
                value={searchQuery}
                onChange={handleSearchChange}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon />
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <FormControl fullWidth>
                <InputLabel>{t('common:labels.configuration')}</InputLabel>
                <Select
                  value={configFilter}
                  onChange={handleConfigFilterChange}
                  label={t('common:labels.configuration')}
                >
                  <MenuItem value="">
                    {t('trading:filters.allConfigurations')}
                  </MenuItem>
                  {configurationsData?.results.map((config) => (
                    <MenuItem key={config.id} value={config.id}>
                      {config.name} (
                      {getStrategyDisplayName(strategies, config.strategy_type)}
                      )
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <FormControl fullWidth>
                <InputLabel>{t('trading:filters.sortBy')}</InputLabel>
                <Select
                  value={sortBy}
                  onChange={handleSortChange}
                  label={t('trading:filters.sortBy')}
                >
                  <MenuItem value="-created_at">
                    {t('trading:filters.newestFirst')}
                  </MenuItem>
                  <MenuItem value="created_at">
                    {t('trading:filters.oldestFirst')}
                  </MenuItem>
                  <MenuItem value="name">
                    {t('trading:filters.nameAZ')}
                  </MenuItem>
                  <MenuItem value="-name">
                    {t('trading:filters.nameZA')}
                  </MenuItem>
                  <MenuItem value="-updated_at">
                    {t('trading:filters.recentlyUpdated')}
                  </MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </Paper>

        {/* Tab Panels */}
        <TabPanel value={tabValue} index={0}>
          {isLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
              <LoadingSpinner />
            </Box>
          ) : error ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography color="error">{error.message}</Typography>
            </Paper>
          ) : !data || data.results.length === 0 ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography variant="h6" color="text.secondary" gutterBottom>
                {t('trading:empty.noTasksFound')}
              </Typography>
              <Typography color="text.secondary" sx={{ mb: 2 }}>
                {t('trading:empty.createFirstTask')}
              </Typography>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={handleCreateTask}
              >
                {t('common:actions.createTask')}
              </Button>
            </Paper>
          ) : (
            <>
              <Grid container spacing={3}>
                {data.results.map((task) => (
                  <Grid size={{ xs: 12 }} key={task.id}>
                    <TradingTaskCard task={task} onRefresh={handleRefresh} />
                  </Grid>
                ))}
              </Grid>
              {totalPages > 1 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                  <Pagination
                    count={totalPages}
                    page={page}
                    onChange={handlePageChange}
                    color="primary"
                  />
                </Box>
              )}
            </>
          )}
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          {isLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
              <LoadingSpinner />
            </Box>
          ) : error ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography color="error">{error.message}</Typography>
            </Paper>
          ) : !data || data.results.length === 0 ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography variant="h6" color="text.secondary">
                {t('trading:empty.noRunningTasks')}
              </Typography>
            </Paper>
          ) : (
            <>
              <Grid container spacing={3}>
                {data.results.map((task) => (
                  <Grid size={{ xs: 12 }} key={task.id}>
                    <TradingTaskCard task={task} onRefresh={handleRefresh} />
                  </Grid>
                ))}
              </Grid>
              {totalPages > 1 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                  <Pagination
                    count={totalPages}
                    page={page}
                    onChange={handlePageChange}
                    color="primary"
                  />
                </Box>
              )}
            </>
          )}
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          {isLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
              <LoadingSpinner />
            </Box>
          ) : error ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography color="error">{error.message}</Typography>
            </Paper>
          ) : !data || data.results.length === 0 ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography variant="h6" color="text.secondary">
                {t('trading:empty.noPausedTasks')}
              </Typography>
            </Paper>
          ) : (
            <>
              <Grid container spacing={3}>
                {data.results.map((task) => (
                  <Grid size={{ xs: 12 }} key={task.id}>
                    <TradingTaskCard task={task} onRefresh={handleRefresh} />
                  </Grid>
                ))}
              </Grid>
              {totalPages > 1 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                  <Pagination
                    count={totalPages}
                    page={page}
                    onChange={handlePageChange}
                    color="primary"
                  />
                </Box>
              )}
            </>
          )}
        </TabPanel>

        <TabPanel value={tabValue} index={3}>
          {isLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
              <LoadingSpinner />
            </Box>
          ) : error ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography color="error">{error.message}</Typography>
            </Paper>
          ) : !data || data.results.length === 0 ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography variant="h6" color="text.secondary">
                {t('trading:empty.noStoppedTasks')}
              </Typography>
            </Paper>
          ) : (
            <>
              <Grid container spacing={3}>
                {data.results.map((task) => (
                  <Grid size={{ xs: 12 }} key={task.id}>
                    <TradingTaskCard task={task} onRefresh={handleRefresh} />
                  </Grid>
                ))}
              </Grid>
              {totalPages > 1 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                  <Pagination
                    count={totalPages}
                    page={page}
                    onChange={handlePageChange}
                    color="primary"
                  />
                </Box>
              )}
            </>
          )}
        </TabPanel>
      </Box>
    </Container>
  );
}
