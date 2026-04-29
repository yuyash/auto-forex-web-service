import { useState, useMemo } from 'react';
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
import { Breadcrumbs, PageContainer } from '../components/common';
import ConfigurationCard from '../components/configurations/ConfigurationCard';
import type { SelectChangeEvent } from '@mui/material';
import { useStrategies, getStrategyDisplayName } from '../hooks/useStrategies';

const ConfigurationsPage = () => {
  const { t } = useTranslation(['configuration', 'common']);
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [strategyTypeFilter, setStrategyTypeFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState('-updated_at');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // Fetch configurations with filters
  const { data, isLoading, error } = useConfigurations({
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

  // Fetch strategies for display names
  const { strategies } = useStrategies();

  // Get unique strategy types for filter
  const strategyTypes = useMemo(() => {
    return strategies.map((strategy) => strategy.id).sort();
  }, [strategies]);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    setPage(1);
  };

  const handleStrategyTypeChange = (event: SelectChangeEvent<string>) => {
    setStrategyTypeFilter(event.target.value);
    setPage(1);
  };

  const handleSortChange = (event: SelectChangeEvent<string>) => {
    setSortBy(event.target.value);
    setPage(1);
  };

  const handlePageSizeChange = (event: SelectChangeEvent<string>) => {
    setPageSize(Number(event.target.value));
    setPage(1);
  };

  const handleCreateNew = () => {
    navigate('/configurations/new');
  };

  const handlePageChange = (
    _event: React.ChangeEvent<unknown>,
    value: number
  ) => {
    setPage(value);
  };

  return (
    <PageContainer sx={{ mt: 4, mb: 4 }}>
      <Breadcrumbs />

      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 4,
          flexWrap: 'wrap',
          gap: 2,
        }}
      >
        <Box>
          <Typography variant="h4" gutterBottom>
            {t('configuration:pages.title')}
          </Typography>
          <Typography variant="body1" color="text.secondary">
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
      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              md: 'minmax(0, 1fr) 220px 200px 160px',
            },
            gap: 2,
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

      {/* Error State */}
      {error && (
        <Alert
          severity="error"
          sx={{ mb: 3 }}
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
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Empty State */}
      {!isLoading && configurations.length === 0 && (
        <Paper
          elevation={0}
          sx={{
            p: 8,
            textAlign: 'center',
            backgroundColor: 'background.default',
          }}
        >
          <Typography variant="h6" color="text.secondary" gutterBottom>
            {search || strategyTypeFilter !== 'all'
              ? t('configuration:empty.noConfigurationsFound')
              : t('configuration:empty.noConfigurationsYet')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
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
              gap: 3,
            }}
          >
            {configurations.map((config) => (
              <ConfigurationCard key={config.id} configuration={config} />
            ))}
          </Box>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
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
    </PageContainer>
  );
};

export default ConfigurationsPage;
