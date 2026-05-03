import { useState, useEffect } from 'react';

import {
  Box,
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
  type SelectChangeEvent,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import {
  Add as AddIcon,
  Search as SearchIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { shouldPollTaskStatus } from '../hooks/taskResourceQueries';
import { useBacktestTasks } from '../hooks/useBacktestTasks';
import { TaskStatus } from '../types/common';
import BacktestTaskCard from '../components/backtest/BacktestTaskCard';
import {
  LoadingSpinner,
  Breadcrumbs,
  PageContainer,
} from '../components/common';
import { useSequentialPolling } from '../hooks/useSequentialPolling';
import { usePollingPolicy } from '../hooks/usePollingPolicy';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import { useAppSettings } from '../hooks/useAppSettings';
import { logger } from '../utils/logger';

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
      id={`backtest-tasks-tabpanel-${index}`}
      aria-labelledby={`backtest-tasks-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
}

function a11yProps(index: number) {
  return {
    id: `backtest-tasks-tab-${index}`,
    'aria-controls': `backtest-tasks-tabpanel-${index}`,
  };
}

export default function BacktestTasksPage() {
  const { t } = useTranslation(['backtest', 'common']);
  const { settings: appSettings } = useAppSettings();
  const navigate = useNavigate();
  const location = useLocation();
  const [tabValue, setTabValue] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('-created_at');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const debouncedSearchQuery = useDebouncedValue(searchQuery, 400);

  // Determine status filter based on active tab
  const getStatusFilter = (): TaskStatus | undefined => {
    switch (tabValue) {
      case 1:
        return TaskStatus.RUNNING;
      case 2:
        return TaskStatus.COMPLETED;
      case 3:
        return TaskStatus.FAILED;
      default:
        return undefined; // All tasks
    }
  };

  const { data, isLoading, error, refresh } = useBacktestTasks({
    page,
    page_size: pageSize,
    search: debouncedSearchQuery || undefined,
    status: getStatusFilter(),
    ordering: sortBy,
  });

  useEffect(() => {
    if (location.state?.deleted) {
      void refresh();
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.pathname, location.state?.deleted, navigate, refresh]);

  const hasActiveTasks = !!data?.results.some((task) =>
    shouldPollTaskStatus(task.status)
  );
  const activePollingIntervalMs = Math.min(
    appSettings.taskPollingIntervalSeconds * 1000,
    2_000
  );
  const pollingPolicy = usePollingPolicy({
    enabled: true,
    baseIntervalMs: hasActiveTasks
      ? activePollingIntervalMs
      : appSettings.taskPollingIntervalSeconds * 1000 * 6,
  });

  const [pollingError, setPollingError] = useState<string | null>(null);

  useSequentialPolling(
    async () => {
      logger.debug('Auto-refreshing backtest task list');
      const result = await refresh();
      if (
        result &&
        typeof result === 'object' &&
        'error' in result &&
        (result as { error?: unknown }).error
      ) {
        pollingPolicy.registerFailure();
      } else {
        pollingPolicy.resetFailures();
        setPollingError(null);
      }
      return result;
    },
    {
      enabled: pollingPolicy.isActive,
      intervalMs: pollingPolicy.intervalMs,
      onError: (err) => {
        pollingPolicy.registerFailure();
        const msg = err instanceof Error ? err.message : String(err);
        logger.warn('Backtest task auto-refresh failed', { error: msg });
        setPollingError(msg);
      },
    }
  );

  const handleRefresh = () => {
    void refresh();
  };

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
    setPage(1); // Reset to first page when changing tabs
  };

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value);
    setPage(1); // Reset to first page when searching
  };

  const handleSortChange = (event: SelectChangeEvent<string>) => {
    setSortBy(event.target.value);
    setPage(1);
  };

  const handlePageSizeChange = (event: SelectChangeEvent<string>) => {
    setPageSize(Number(event.target.value));
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
    navigate('/backtest-tasks/new');
  };

  const totalPages = data ? Math.ceil(data.count / pageSize) : 0;

  return (
    <PageContainer>
      <Box sx={{ py: { xs: 2, sm: 4 } }}>
        <Breadcrumbs />

        {/* Header */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: { xs: 2, sm: 3 },
            flexWrap: 'wrap',
            gap: 1,
          }}
        >
          <Typography
            variant="h4"
            component="h1"
            sx={{ fontSize: { xs: '1.5rem', sm: '2.125rem' } }}
          >
            {t('backtest:pages.title')}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
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
              onClick={() => navigate('/configurations?from=backtest-tasks')}
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

        {/* Tabs */}
        <Paper sx={{ mb: 3 }}>
          <Tabs
            value={tabValue}
            onChange={handleTabChange}
            aria-label="backtest tasks tabs"
            sx={{ borderBottom: 1, borderColor: 'divider' }}
          >
            <Tab label={t('backtest:tabs.all')} {...a11yProps(0)} />
            <Tab label={t('backtest:tabs.running')} {...a11yProps(1)} />
            <Tab label={t('backtest:tabs.completed')} {...a11yProps(2)} />
            <Tab label={t('backtest:tabs.failed')} {...a11yProps(3)} />
          </Tabs>
        </Paper>

        {/* Filters */}
        <Paper sx={{ p: 2, mb: 3 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                placeholder={t(
                  'trading:filters.searchTasks',
                  'Search tasks...'
                )}
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
            <Grid size={{ xs: 12, md: 3 }}>
              <FormControl fullWidth>
                <InputLabel>
                  {t('trading:filters.sortBy', 'Sort By')}
                </InputLabel>
                <Select
                  value={sortBy}
                  onChange={handleSortChange}
                  label={t('trading:filters.sortBy', 'Sort By')}
                >
                  <MenuItem value="-created_at">
                    {t('trading:filters.newestFirst', 'Newest First')}
                  </MenuItem>
                  <MenuItem value="created_at">
                    {t('trading:filters.oldestFirst', 'Oldest First')}
                  </MenuItem>
                  <MenuItem value="name">
                    {t('trading:filters.nameAZ', 'Name (A-Z)')}
                  </MenuItem>
                  <MenuItem value="-name">
                    {t('trading:filters.nameZA', 'Name (Z-A)')}
                  </MenuItem>
                  <MenuItem value="-updated_at">
                    {t('trading:filters.recentlyUpdated', 'Recently Updated')}
                  </MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <FormControl fullWidth>
                <InputLabel>
                  {t('common:labels.pageSize', 'Page size')}
                </InputLabel>
                <Select
                  value={String(pageSize)}
                  onChange={handlePageSizeChange}
                  label={t('common:labels.pageSize', 'Page size')}
                >
                  {[10, 20, 50, 100].map((size) => (
                    <MenuItem key={size} value={String(size)}>
                      {size}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </Paper>

        {pollingError && (
          <Alert
            severity="warning"
            sx={{ mb: 2 }}
            onClose={() => setPollingError(null)}
          >
            {t('common:errors.refreshFailed')}: {pollingError}
          </Alert>
        )}

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
                {t('backtest:empty.noTasksFound')}
              </Typography>
              <Typography color="text.secondary" sx={{ mb: 2 }}>
                {t('backtest:empty.createFirstTask')}
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
                  <Grid key={task.id} size={{ xs: 12 }}>
                    <BacktestTaskCard task={task} onRefresh={handleRefresh} />
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
                {t('backtest:empty.noRunningTasks')}
              </Typography>
            </Paper>
          ) : (
            <>
              <Grid container spacing={3}>
                {data.results.map((task) => (
                  <Grid key={task.id} size={{ xs: 12 }}>
                    <BacktestTaskCard task={task} onRefresh={handleRefresh} />
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
                {t('backtest:empty.noCompletedTasks')}
              </Typography>
            </Paper>
          ) : (
            <>
              <Grid container spacing={3}>
                {data.results.map((task) => (
                  <Grid key={task.id} size={{ xs: 12 }}>
                    <BacktestTaskCard task={task} onRefresh={handleRefresh} />
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
                {t('backtest:empty.noFailedTasks')}
              </Typography>
            </Paper>
          ) : (
            <>
              <Grid container spacing={3}>
                {data.results.map((task) => (
                  <Grid key={task.id} size={{ xs: 12 }}>
                    <BacktestTaskCard task={task} onRefresh={handleRefresh} />
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
    </PageContainer>
  );
}
