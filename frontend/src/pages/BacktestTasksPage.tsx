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
  useToast,
} from '../components/common';
import { BulkActionToolbar } from '../components/common/BulkActionToolbar';
import { BulkDeleteDialog } from '../components/common/BulkDeleteDialog';
import { CopyTaskDialog } from '../components/tasks/actions/CopyTaskDialog';
import { useSequentialPolling } from '../hooks/useSequentialPolling';
import { usePollingPolicy } from '../hooks/usePollingPolicy';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import { useAppSettings } from '../hooks/useAppSettings';
import { logger } from '../utils/logger';
import { buildCompareUrl } from '../utils/compareParams';
import {
  useCopyBacktestTask,
  useDeleteBacktestTask,
} from '../hooks/useBacktestTaskMutations';
import { formatTaskActionError } from '../utils/taskActionError';

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
      {value === index && <Box sx={{ py: 1 }}>{children}</Box>}
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
  const { showError, showSuccess } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [tabValue, setTabValue] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('-created_at');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [copyDialogOpen, setCopyDialogOpen] = useState(false);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const copyTask = useCopyBacktestTask();
  const deleteTask = useDeleteBacktestTask();
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

  const visibleIdSet = useMemo(
    () => new Set(data?.results.map((task) => task.id) ?? []),
    [data?.results]
  );
  const visibleSelectedIds = useMemo(
    () => selectedIds.filter((id) => visibleIdSet.has(id)),
    [selectedIds, visibleIdSet]
  );
  const visibleTasks = useMemo(() => data?.results ?? [], [data?.results]);
  const selectedTasks = useMemo(
    () => visibleTasks.filter((task) => visibleSelectedIds.includes(task.id)),
    [visibleSelectedIds, visibleTasks]
  );
  const singleSelectedTask =
    selectedTasks.length === 1 ? selectedTasks[0] : null;
  const selectedContainsNonDeletable = selectedTasks.some(
    (task) => !(task.action_policy?.can_delete ?? false)
  );
  const selectedTaskCanEdit =
    singleSelectedTask?.action_policy?.can_edit_metadata ?? false;

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
    setSelectedIds([]);
    setPage(1); // Reset to first page when changing tabs
  };

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value);
    setSelectedIds([]);
    setPage(1); // Reset to first page when searching
  };

  const handleSortChange = (event: SelectChangeEvent<string>) => {
    setSortBy(event.target.value);
    setSelectedIds([]);
    setPage(1);
  };

  const handlePageSizeChange = (event: SelectChangeEvent<string>) => {
    setPageSize(Number(event.target.value));
    setSelectedIds([]);
    setPage(1);
  };

  const handlePageChange = (
    _event: React.ChangeEvent<unknown>,
    value: number
  ) => {
    setPage(value);
    setSelectedIds([]);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleCreateTask = () => {
    navigate('/backtest-tasks/new');
  };

  const handleCompare = () => {
    navigate(buildCompareUrl('/backtest-tasks/compare', visibleSelectedIds));
  };

  const handleSelectAll = () => {
    setSelectedIds(visibleTasks.map((task) => task.id));
  };

  const handleClearSelection = () => {
    setSelectedIds([]);
  };

  const handleCopyConfirm = async (newName: string) => {
    if (!singleSelectedTask) return;
    try {
      await copyTask.mutate({
        id: singleSelectedTask.id,
        data: { new_name: newName },
      });
      setCopyDialogOpen(false);
      await refresh();
      showSuccess(t('common:selection.copySuccess'));
    } catch (error) {
      logger.error('Failed to copy backtest task from bulk toolbar', {
        taskId: singleSelectedTask.id,
        error: error instanceof Error ? error.message : String(error),
      });
      showError(formatTaskActionError(error, 'Failed to copy task'));
    }
  };

  const handleEditSelected = () => {
    if (!singleSelectedTask || !selectedTaskCanEdit) return;
    navigate(`/backtest-tasks/${singleSelectedTask.id}/edit`);
  };

  const handleBulkDelete = async () => {
    setIsBulkDeleting(true);
    try {
      for (const task of selectedTasks) {
        await deleteTask.mutate(task.id);
      }
      setBulkDeleteOpen(false);
      setSelectedIds([]);
      await refresh();
      showSuccess(t('common:selection.bulkDeleteSuccess'));
    } catch (error) {
      logger.error('Failed to bulk delete backtest tasks', {
        taskIds: selectedTasks.map((task) => task.id),
        error: error instanceof Error ? error.message : String(error),
      });
      showError(formatTaskActionError(error, 'Failed to delete tasks'));
    } finally {
      setIsBulkDeleting(false);
    }
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
        <Paper sx={{ mb: 1 }}>
          <Tabs
            value={tabValue}
            onChange={handleTabChange}
            aria-label="backtest tasks tabs"
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
            <Tab label={t('backtest:tabs.all')} {...a11yProps(0)} />
            <Tab label={t('backtest:tabs.running')} {...a11yProps(1)} />
            <Tab label={t('backtest:tabs.completed')} {...a11yProps(2)} />
            <Tab label={t('backtest:tabs.failed')} {...a11yProps(3)} />
          </Tabs>
        </Paper>

        {/* Filters */}
        <Paper sx={{ p: 1, mb: 1 }}>
          <Grid container spacing={1} alignItems="center">
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
            sx={{ mb: 1 }}
            onClose={() => setPollingError(null)}
          >
            {t('common:errors.refreshFailed')}: {pollingError}
          </Alert>
        )}

        {visibleTasks.length > 0 && (
          <BulkActionToolbar
            selectedCount={visibleSelectedIds.length}
            totalCount={visibleTasks.length}
            onSelectAll={handleSelectAll}
            onClearSelection={handleClearSelection}
            onCompare={handleCompare}
            onBulkDelete={() => setBulkDeleteOpen(true)}
            onCopy={() => setCopyDialogOpen(true)}
            onEdit={handleEditSelected}
            disableCompare={visibleSelectedIds.length < 2}
            disableCopy={selectedTasks.length !== 1 || copyTask.isLoading}
            copyTooltip={
              selectedTasks.length === 1
                ? undefined
                : t('common:selection.singleSelectionRequired')
            }
            disableEdit={selectedTasks.length !== 1 || !selectedTaskCanEdit}
            editTooltip={
              selectedTasks.length === 1
                ? selectedTaskCanEdit
                  ? undefined
                  : t('common:selection.editUnavailable')
                : t('common:selection.singleSelectionRequired')
            }
            disableBulkDelete={
              selectedTasks.length === 0 ||
              selectedContainsNonDeletable ||
              isBulkDeleting
            }
            bulkDeleteTooltip={
              selectedContainsNonDeletable
                ? t('common:selection.deleteUnavailable')
                : undefined
            }
          />
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
              <Grid container spacing={1}>
                {data.results.map((task) => (
                  <Grid key={task.id} size={{ xs: 12 }}>
                    <BacktestTaskCard
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
                {t('backtest:empty.noRunningTasks')}
              </Typography>
            </Paper>
          ) : (
            <>
              <Grid container spacing={1}>
                {data.results.map((task) => (
                  <Grid key={task.id} size={{ xs: 12 }}>
                    <BacktestTaskCard
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
                {t('backtest:empty.noCompletedTasks')}
              </Typography>
            </Paper>
          ) : (
            <>
              <Grid container spacing={1}>
                {data.results.map((task) => (
                  <Grid key={task.id} size={{ xs: 12 }}>
                    <BacktestTaskCard
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
                {t('backtest:empty.noFailedTasks')}
              </Typography>
            </Paper>
          ) : (
            <>
              <Grid container spacing={1}>
                {data.results.map((task) => (
                  <Grid key={task.id} size={{ xs: 12 }}>
                    <BacktestTaskCard
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
        <CopyTaskDialog
          open={copyDialogOpen}
          taskName={singleSelectedTask?.name ?? ''}
          onCancel={() => setCopyDialogOpen(false)}
          onConfirm={handleCopyConfirm}
          isLoading={copyTask.isLoading}
        />
        <BulkDeleteDialog
          open={bulkDeleteOpen}
          title={t('common:selection.bulkDeleteTitle')}
          itemNames={selectedTasks.map((task) => task.name)}
          onCancel={() => setBulkDeleteOpen(false)}
          onConfirm={handleBulkDelete}
          isLoading={isBulkDeleting}
          warning={t('common:selection.bulkDeleteWarning')}
        />
      </Box>
    </PageContainer>
  );
}
