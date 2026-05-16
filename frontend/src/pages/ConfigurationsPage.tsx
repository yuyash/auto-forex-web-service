import { useMemo, useState } from 'react';
import {
  Typography,
  Box,
  Paper,
  TextField,
  InputAdornment,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
  Pagination,
} from '@mui/material';

import SearchIcon from '@mui/icons-material/Search';
import AddIcon from '@mui/icons-material/Add';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useConfigurations } from '../hooks/useConfigurations';
import { Breadcrumbs, PageContainer, useToast } from '../components/common';
import ConfigurationCard from '../components/configurations/ConfigurationCard';
import type { SelectChangeEvent } from '@mui/material';
import { useStrategies, getStrategyDisplayName } from '../hooks/useStrategies';
import { buildCompareUrl } from '../utils/compareParams';
import { BulkActionToolbar } from '../components/common/BulkActionToolbar';
import { BulkDeleteDialog } from '../components/common/BulkDeleteDialog';
import {
  useCopyConfiguration,
  useDeleteConfiguration,
} from '../hooks/useConfigurationMutations';
import { logger } from '../utils/logger';

const ConfigurationsPage = () => {
  const { t } = useTranslation(['configuration', 'common']);
  const navigate = useNavigate();
  const { showError, showSuccess } = useToast();
  const [search, setSearch] = useState('');
  const [strategyTypeFilter, setStrategyTypeFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState('-updated_at');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const copyMutation = useCopyConfiguration({
    onSuccess: (copied) => {
      navigate(`/configurations/${copied.id}`);
    },
  });
  const deleteMutation = useDeleteConfiguration();

  // Fetch configurations with filters
  const { data, isLoading, error, refresh } = useConfigurations({
    search: search || undefined,
    strategy_type:
      strategyTypeFilter !== 'all' ? strategyTypeFilter : undefined,
    page_size: pageSize,
    ordering: sortBy,
    page,
  });

  // Get configurations from paginated response
  const configurations = useMemo(() => {
    return data?.results || [];
  }, [data]);

  const totalPages = data ? Math.ceil(data.count / pageSize) : 0;

  const visibleIdSet = useMemo(
    () => new Set(configurations.map((config) => config.id)),
    [configurations]
  );
  const visibleSelectedIds = useMemo(
    () => selectedIds.filter((id) => visibleIdSet.has(id)),
    [selectedIds, visibleIdSet]
  );
  const selectedConfigurations = useMemo(
    () =>
      configurations.filter((config) => visibleSelectedIds.includes(config.id)),
    [configurations, visibleSelectedIds]
  );
  const singleSelectedConfiguration =
    selectedConfigurations.length === 1 ? selectedConfigurations[0] : null;
  const selectedIncludesInUse = selectedConfigurations.some(
    (config) => config.is_in_use
  );

  // Fetch strategies for display names
  const { strategies } = useStrategies();

  // Get unique strategy types for filter
  const strategyTypes = useMemo(() => {
    return strategies.map((strategy) => strategy.id).sort();
  }, [strategies]);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    setSelectedIds([]);
    setPage(1);
  };

  const handleStrategyTypeChange = (event: SelectChangeEvent<string>) => {
    setStrategyTypeFilter(event.target.value);
    setSelectedIds([]);
    setPage(1);
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

  const handleCreateNew = () => {
    navigate('/configurations/new');
  };

  const handleCompare = () => {
    navigate(buildCompareUrl('/configurations/compare', visibleSelectedIds));
  };

  const handleSelectAll = () => {
    setSelectedIds(configurations.map((config) => config.id));
  };

  const handleClearSelection = () => {
    setSelectedIds([]);
  };

  const handleCopySelected = async () => {
    if (!singleSelectedConfiguration) return;
    try {
      await copyMutation.mutate({ id: singleSelectedConfiguration.id });
    } catch (error) {
      logger.error('Failed to copy configuration from bulk toolbar', {
        configurationId: singleSelectedConfiguration.id,
        error: error instanceof Error ? error.message : String(error),
      });
      showError(
        error instanceof Error
          ? error.message
          : t('common:errors.operationFailed', {
              defaultValue: 'Operation failed',
            })
      );
    }
  };

  const handleEditSelected = () => {
    if (
      !singleSelectedConfiguration ||
      singleSelectedConfiguration.has_running_tasks
    ) {
      return;
    }
    navigate(`/configurations/${singleSelectedConfiguration.id}/edit`);
  };

  const handleBulkDelete = async () => {
    setIsBulkDeleting(true);
    try {
      for (const config of selectedConfigurations) {
        await deleteMutation.mutate(config.id);
      }
      setBulkDeleteOpen(false);
      setSelectedIds([]);
      await refresh();
      showSuccess(t('common:selection.bulkDeleteSuccess'));
    } catch (error) {
      logger.error('Failed to bulk delete configurations', {
        configurationIds: selectedConfigurations.map((config) => config.id),
        error: error instanceof Error ? error.message : String(error),
      });
      showError(
        error instanceof Error
          ? error.message
          : t('common:errors.operationFailed', {
              defaultValue: 'Operation failed',
            })
      );
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

  const handlePageChange = (
    _event: React.ChangeEvent<unknown>,
    value: number
  ) => {
    setSelectedIds([]);
    setPage(value);
  };

  return (
    <PageContainer sx={{ mt: { xs: 1, sm: 1.5 }, mb: 1.5 }}>
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
        <Box>
          <Typography
            variant="h4"
            sx={{
              fontSize: { xs: '1.25rem', sm: '1.5rem' },
              lineHeight: 1.2,
              fontWeight: 600,
              mb: 0.25,
            }}
          >
            {t('configuration:pages.title')}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {t('configuration:pages.subtitle')}
          </Typography>
        </Box>
        <Button
          variant="contained"
          color="primary"
          startIcon={<AddIcon />}
          onClick={handleCreateNew}
        >
          {t('configuration:card.newConfiguration')}
        </Button>
      </Box>

      {/* Search and Filter Controls */}
      <Paper elevation={2} sx={{ p: 1, mb: 1 }}>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              md: 'minmax(0, 1fr) 220px 200px 160px',
            },
            gap: 1,
            alignItems: 'center',
          }}
        >
          <TextField
            fullWidth
            placeholder={t('configuration:filters.searchConfigurations')}
            value={search}
            onChange={handleSearchChange}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
          />
          <FormControl fullWidth>
            <InputLabel id="strategy-type-filter-label">
              {t('configuration:filters.strategyType')}
            </InputLabel>
            <Select
              labelId="strategy-type-filter-label"
              value={strategyTypeFilter}
              label={t('configuration:filters.strategyType')}
              onChange={handleStrategyTypeChange}
            >
              <MenuItem value="all">
                {t('configuration:filters.allTypes')}
              </MenuItem>
              {strategyTypes.map((type) => (
                <MenuItem key={type} value={type}>
                  {getStrategyDisplayName(strategies, type)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth>
            <InputLabel>{t('configuration:filters.sortBy')}</InputLabel>
            <Select
              value={sortBy}
              label={t('configuration:filters.sortBy')}
              onChange={handleSortChange}
            >
              <MenuItem value="-updated_at">
                {t('configuration:filters.recentlyUpdated')}
              </MenuItem>
              <MenuItem value="-created_at">
                {t('configuration:filters.newestFirst')}
              </MenuItem>
              <MenuItem value="created_at">
                {t('configuration:filters.oldestFirst')}
              </MenuItem>
              <MenuItem value="name">
                {t('configuration:filters.nameAZ')}
              </MenuItem>
              <MenuItem value="-name">
                {t('configuration:filters.nameZA')}
              </MenuItem>
            </Select>
          </FormControl>
          <FormControl fullWidth>
            <InputLabel>{t('common:labels.pageSize')}</InputLabel>
            <Select
              value={String(pageSize)}
              label={t('common:labels.pageSize')}
              onChange={handlePageSizeChange}
            >
              {[10, 20, 50, 100].map((size) => (
                <MenuItem key={size} value={String(size)}>
                  {size}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>
      </Paper>

      <BulkActionToolbar
        selectedCount={visibleSelectedIds.length}
        totalCount={configurations.length}
        onSelectAll={handleSelectAll}
        onClearSelection={handleClearSelection}
        onCompare={handleCompare}
        onBulkDelete={() => setBulkDeleteOpen(true)}
        onCopy={handleCopySelected}
        onEdit={handleEditSelected}
        disableCompare={visibleSelectedIds.length < 2}
        disableCopy={
          selectedConfigurations.length !== 1 || copyMutation.isLoading
        }
        copyTooltip={
          selectedConfigurations.length === 1
            ? undefined
            : t('common:selection.singleSelectionRequired')
        }
        disableEdit={
          selectedConfigurations.length !== 1 ||
          Boolean(singleSelectedConfiguration?.has_running_tasks)
        }
        editTooltip={
          singleSelectedConfiguration?.has_running_tasks
            ? t('configuration:form.editLockedRunningTasks')
            : selectedConfigurations.length === 1
              ? undefined
              : t('common:selection.singleSelectionRequired')
        }
        disableBulkDelete={
          selectedConfigurations.length === 0 ||
          selectedIncludesInUse ||
          isBulkDeleting
        }
        bulkDeleteTooltip={
          selectedIncludesInUse
            ? t('configuration:deleteDialog.bulkDeleteInUseBlocked')
            : undefined
        }
      />

      {/* Error State */}
      {error && (
        <Alert
          severity="error"
          sx={{ mb: 1 }}
          action={
            !error.message.toLowerCase().includes('connection refused') && (
              <Button color="inherit" onClick={() => window.location.reload()}>
                {t('common:actions.reload')}
              </Button>
            )
          }
        >
          <Typography variant="body2" gutterBottom>
            <strong>{t('common:errors.fetchFailed')}</strong>
          </Typography>
          <Typography variant="body2">
            {error.message.toLowerCase().includes('connection refused') ||
            error.message.toLowerCase().includes('failed to fetch')
              ? t('common:errors.cannotConnectToServer')
              : error.message.includes('429') ||
                  error.message.includes('Too Many Requests')
                ? t('common:errors.tooManyRequests')
                : error.message.includes('502') ||
                    error.message.includes('Bad Gateway')
                  ? t('common:errors.serverUnavailable')
                  : error.message}
          </Typography>
        </Alert>
      )}

      {/* Loading State */}
      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Empty State */}
      {!isLoading && configurations.length === 0 && (
        <Paper
          elevation={0}
          sx={{
            p: 3,
            textAlign: 'center',
            backgroundColor: 'background.default',
          }}
        >
          <Typography variant="h6" color="text.secondary" gutterBottom>
            {search || strategyTypeFilter !== 'all'
              ? t('configuration:empty.noConfigurationsFound')
              : t('configuration:empty.noConfigurationsYet')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            {search || strategyTypeFilter !== 'all'
              ? t('configuration:empty.tryAdjustingFilters')
              : t('configuration:empty.createFirstConfig')}
          </Typography>
          {!search && strategyTypeFilter === 'all' && (
            <Button
              variant="contained"
              color="primary"
              startIcon={<AddIcon />}
              onClick={handleCreateNew}
            >
              {t('configuration:card.newConfiguration')}
            </Button>
          )}
        </Paper>
      )}

      {/* Configuration Cards Grid */}
      {!isLoading && configurations.length > 0 && (
        <>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: '1fr',
                md: 'repeat(2, 1fr)',
                lg: 'repeat(3, 1fr)',
              },
              gap: 1,
            }}
          >
            {configurations.map((config) => (
              <ConfigurationCard
                key={config.id}
                configuration={config}
                selected={selectedIds.includes(config.id)}
                onSelectedChange={handleSelectedChange}
              />
            ))}
          </Box>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 1.5 }}>
              <Pagination
                count={totalPages}
                page={page}
                onChange={handlePageChange}
                color="primary"
                disabled={isLoading}
              />
            </Box>
          )}
        </>
      )}

      <BulkDeleteDialog
        open={bulkDeleteOpen}
        title={t('common:selection.bulkDeleteTitle')}
        itemNames={selectedConfigurations.map((config) => config.name)}
        onCancel={() => setBulkDeleteOpen(false)}
        onConfirm={handleBulkDelete}
        isLoading={isBulkDeleting}
        warning={t('configuration:deleteDialog.cannotBeUndone')}
      />
    </PageContainer>
  );
};

export default ConfigurationsPage;
