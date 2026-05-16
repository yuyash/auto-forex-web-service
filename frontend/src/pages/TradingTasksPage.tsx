import { useEffect, useMemo, useState } from 'react';

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
  AlertTitle,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import {
  Add as AddIcon,
  Search as SearchIcon,
  Warning as WarningIcon,
  Settings as SettingsIcon,
  Refresh as RefreshIcon,
  CompareArrows as CompareArrowsIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { shouldPollTaskStatus } from '../hooks/taskResourceQueries';
import { refreshTaskSummary } from '../hooks/taskResourceCache';
import { useTradingTasks } from '../hooks/useTradingTasks';
import { TaskStatus, TaskType } from '../types/common';
import TradingTaskCard from '../components/trading/TradingTaskCard';
import {
  Breadcrumbs,
  LoadingSpinner,
  PageContainer,
} from '../components/common';
import { ConfigurationSelector } from '../components/tasks/forms/ConfigurationSelector';
import { useSequentialPolling } from '../hooks/useSequentialPolling';
import { usePollingPolicy } from '../hooks/usePollingPolicy';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import { useAppSettings } from '../hooks/useAppSettings';
import { logger } from '../utils/logger';
import { buildCompareUrl } from '../utils/compareParams';

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
      {value === index && <Box sx={{ py: 1 }}>{children}</Box>}
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
  const { settings: appSettings } = useAppSettings();
  const navigate = useNavigate();
  const location = useLocation();
  const [tabValue, setTabValue] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('-created_at');
  const [configFilter, setConfigFilter] = useState<string | ''>('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const debouncedSearchQuery = useDebouncedValue(searchQuery, 400);

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

  const { data, isLoading, error, refresh } = useTradingTasks({
    page,
    page_size: pageSize,
    search: debouncedSearchQuery || undefined,
    status: getStatusFilter(),
    config_id: configFilter || undefined,
    ordering: sortBy,
  });

  useEffect(() => {
    if (location.state?.deleted) {
      void refresh();
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.pathname, location.state?.deleted, navigate, refresh]);

  const visibleIdSet = useMemo(
    () => new Set(data?.results.map((task) => task.id) ?? []),
    [data?.results]
  );
  const visibleSelectedIds = useMemo(
    () => selectedIds.filter((id) => visibleIdSet.has(id)),
    [selectedIds, visibleIdSet]
  );

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
      logger.debug('Auto-refreshing trading task list');
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
        logger.warn('Trading task auto-refresh failed', { error: msg });
        setPollingError(msg);
      },
    }
  );

  const handleRefresh = () => {
    const visibleTaskIds = data?.results.map((task) => String(task.id)) ?? [];
    void Promise.all([
      refresh(),
      ...visibleTaskIds.map((taskId) =>
        refreshTaskSummary(taskId, TaskType.TRADING)
      ),
    ]);
  };

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

  const handlePageSizeChange = (event: { target: { value: string } }) => {
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
    navigate('/trading-tasks/new');
  };

  const handleCompare = () => {
    navigate(buildCompareUrl('/trading-tasks/compare', visibleSelectedIds));
  };

  const handleSelectedChange = (id: string, selected: boolean) => {
    setSelectedIds((current) => {
      if (selected) return current.includes(id) ? current : [...current, id];
      return current.filter((currentId) => currentId !== id);
    });
  };

  const totalPages = data ? Math.ceil(data.count / pageSize) : 0;

  return (
    <PageContainer>
      <Box sx={{ py: { xs: 1, sm: 1.5 } }}>
        <Breadcrumbs />

        {/* Header */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 1,
            flexWrap: 'wrap',
            gap: 1,
          }}
        >
          <Typography
            variant="h4"
            component="h1"
            sx={{
              fontSize: { xs: '1.25rem', sm: '1.5rem' },
              lineHeight: 1.2,
              fontWeight: 600,
            }}
          >
            {t('trading:pages.title')}
          </Typography>
          <Box
            sx={{
              display: { xs: 'grid', sm: 'flex' },
              gridTemplateColumns: {
                xs: 'repeat(2, minmax(0, 1fr))',
                '@media (max-width: 340px)': '1fr',
              },
              gap: 0.75,
              width: { xs: '100%', sm: 'auto' },
              flexWrap: { sm: 'wrap' },
              justifyContent: { sm: 'flex-end' },
              '& .MuiButton-root': {
                minWidth: 0,
                width: { xs: '100%', sm: 'auto' },
                px: { xs: 1, sm: 1.25 },
                whiteSpace: 'nowrap',
              },
            }}
          >
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
              startIcon={<CompareArrowsIcon />}
              disabled={visibleSelectedIds.length < 2}
              onClick={handleCompare}
            >
              {t('common:actions.compare')} ({visibleSelectedIds.length})
            </Button>
            <Button
              variant="outlined"
              startIcon={<SettingsIcon />}
              onClick={() => navigate('/oanda-accounts')}
            >
              {t('settings:accounts.title', 'OANDA Accounts')}
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
        <Alert
          severity="warning"
          icon={<WarningIcon />}
          sx={{
            mb: 1,
            py: 0.5,
            '& .MuiAlert-message': { py: 0.25 },
          }}
        >
          <AlertTitle>
            {t('trading:warnings.oneTaskPerAccountTitle')}
          </AlertTitle>
          {t('trading:warnings.oneTaskPerAccountMessage')}
        </Alert>

        {/* Tabs */}
        <Paper sx={{ mb: 1 }}>
          <Tabs
            value={tabValue}
            onChange={handleTabChange}
            aria-label="trading tasks tabs"
            sx={{
              minHeight: 34,
              borderBottom: 1,
              borderColor: 'divider',
              '& .MuiTab-root': {
                minHeight: 34,
                px: { xs: 1, sm: 1.25 },
                py: 0.5,
                fontSize: '0.8125rem',
              },
            }}
          >
            <Tab label={t('trading:tabs.all')} {...a11yProps(0)} />
            <Tab label={t('trading:tabs.running')} {...a11yProps(1)} />
            <Tab label={t('trading:tabs.paused')} {...a11yProps(2)} />
            <Tab label={t('trading:tabs.stopped')} {...a11yProps(3)} />
          </Tabs>
        </Paper>

        {/* Filters */}
        <Paper sx={{ p: 1, mb: 1 }}>
          <Grid container spacing={1} alignItems="center">
            <Grid size={{ xs: 12, md: 3 }}>
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
            <Grid size={{ xs: 12, md: 3 }}>
              <ConfigurationSelector
                value={configFilter}
                onChange={(value) => {
                  setConfigFilter(value);
                  setPage(1);
                }}
                label={t('common:labels.configuration')}
                allowEmptySelection
                emptySelectionLabel={t('trading:filters.allConfigurations')}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
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
            sx={{ mb: 1 }}
            onClose={() => setPollingError(null)}
          >
            {t('common:errors.refreshFailed')}: {pollingError}
          </Alert>
        )}

        {/* Tab Panels */}
        <TabPanel value={tabValue} index={0}>
          {isLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
              <LoadingSpinner />
            </Box>
          ) : error ? (
            <Paper sx={{ p: 2, textAlign: 'center' }}>
              <Typography color="error">{error.message}</Typography>
            </Paper>
          ) : !data || data.results.length === 0 ? (
            <Paper sx={{ p: 2, textAlign: 'center' }}>
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
              <Grid container spacing={1}>
                {data.results.map((task) => (
                  <Grid size={{ xs: 12 }} key={task.id}>
                    <TradingTaskCard
                      task={task}
                      onRefresh={handleRefresh}
                      selected={selectedIds.includes(task.id)}
                      onSelectedChange={handleSelectedChange}
                    />
                  </Grid>
                ))}
              </Grid>
              {totalPages > 1 && (
                <Box
                  sx={{ display: 'flex', justifyContent: 'center', mt: 1.5 }}
                >
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
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
              <LoadingSpinner />
            </Box>
          ) : error ? (
            <Paper sx={{ p: 2, textAlign: 'center' }}>
              <Typography color="error">{error.message}</Typography>
            </Paper>
          ) : !data || data.results.length === 0 ? (
            <Paper sx={{ p: 2, textAlign: 'center' }}>
              <Typography variant="h6" color="text.secondary">
                {t('trading:empty.noRunningTasks')}
              </Typography>
            </Paper>
          ) : (
            <>
              <Grid container spacing={1}>
                {data.results.map((task) => (
                  <Grid size={{ xs: 12 }} key={task.id}>
                    <TradingTaskCard
                      task={task}
                      onRefresh={handleRefresh}
                      selected={selectedIds.includes(task.id)}
                      onSelectedChange={handleSelectedChange}
                    />
                  </Grid>
                ))}
              </Grid>
              {totalPages > 1 && (
                <Box
                  sx={{ display: 'flex', justifyContent: 'center', mt: 1.5 }}
                >
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
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
              <LoadingSpinner />
            </Box>
          ) : error ? (
            <Paper sx={{ p: 2, textAlign: 'center' }}>
              <Typography color="error">{error.message}</Typography>
            </Paper>
          ) : !data || data.results.length === 0 ? (
            <Paper sx={{ p: 2, textAlign: 'center' }}>
              <Typography variant="h6" color="text.secondary">
                {t('trading:empty.noPausedTasks')}
              </Typography>
            </Paper>
          ) : (
            <>
              <Grid container spacing={1}>
                {data.results.map((task) => (
                  <Grid size={{ xs: 12 }} key={task.id}>
                    <TradingTaskCard
                      task={task}
                      onRefresh={handleRefresh}
                      selected={selectedIds.includes(task.id)}
                      onSelectedChange={handleSelectedChange}
                    />
                  </Grid>
                ))}
              </Grid>
              {totalPages > 1 && (
                <Box
                  sx={{ display: 'flex', justifyContent: 'center', mt: 1.5 }}
                >
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
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
              <LoadingSpinner />
            </Box>
          ) : error ? (
            <Paper sx={{ p: 2, textAlign: 'center' }}>
              <Typography color="error">{error.message}</Typography>
            </Paper>
          ) : !data || data.results.length === 0 ? (
            <Paper sx={{ p: 2, textAlign: 'center' }}>
              <Typography variant="h6" color="text.secondary">
                {t('trading:empty.noStoppedTasks')}
              </Typography>
            </Paper>
          ) : (
            <>
              <Grid container spacing={1}>
                {data.results.map((task) => (
                  <Grid size={{ xs: 12 }} key={task.id}>
                    <TradingTaskCard
                      task={task}
                      onRefresh={handleRefresh}
                      selected={selectedIds.includes(task.id)}
                      onSelectedChange={handleSelectedChange}
                    />
                  </Grid>
                ))}
              </Grid>
              {totalPages > 1 && (
                <Box
                  sx={{ display: 'flex', justifyContent: 'center', mt: 1.5 }}
                >
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
