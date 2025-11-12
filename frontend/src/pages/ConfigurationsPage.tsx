import { useState, useMemo } from 'react';
import {
  Container,
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
} from '@mui/material';

import SearchIcon from '@mui/icons-material/Search';
import AddIcon from '@mui/icons-material/Add';
import { useNavigate } from 'react-router-dom';
import { useConfigurations } from '../hooks/useConfigurations';
import { Breadcrumbs } from '../components/common';
import ConfigurationCard from '../components/configurations/ConfigurationCard';
import type { SelectChangeEvent } from '@mui/material';
import { useStrategies, getStrategyDisplayName } from '../hooks/useStrategies';

const ConfigurationsPage = () => {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [strategyTypeFilter, setStrategyTypeFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Fetch configurations with filters
  const { data, isLoading, error } = useConfigurations({
    search: search || undefined,
    strategy_type:
      strategyTypeFilter !== 'all' ? strategyTypeFilter : undefined,
    page_size: pageSize,
    page,
  });

  // Get configurations from paginated response
  const configurations = useMemo(() => {
    return data?.results || [];
  }, [data]);

  const hasNextPage = data?.next !== null;
  const hasPreviousPage = data?.previous !== null;

  // Fetch strategies for display names
  const { strategies } = useStrategies();

  // Get unique strategy types for filter
  const strategyTypes = useMemo(() => {
    const types = new Set(configurations.map((config) => config.strategy_type));
    return Array.from(types).sort();
  }, [configurations]);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    setPage(1);
  };

  const handleStrategyTypeChange = (event: SelectChangeEvent<string>) => {
    setStrategyTypeFilter(event.target.value);
    setPage(1);
  };

  const handleCreateNew = () => {
    navigate('/configurations/new');
  };

  const handleNextPage = () => {
    if (hasNextPage) {
      setPage((prev) => prev + 1);
    }
  };

  const handlePreviousPage = () => {
    if (hasPreviousPage) {
      setPage((prev) => prev - 1);
    }
  };

  return (
    <Container maxWidth={false} sx={{ mt: 4, mb: 4, px: 3 }}>
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
            Strategy Configurations
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Manage reusable strategy configurations for backtesting and live
            trading
          </Typography>
        </Box>
        <Button
          variant="contained"
          color="primary"
          startIcon={<AddIcon />}
          onClick={handleCreateNew}
        >
          New Configuration
        </Button>
      </Box>

      {/* Search and Filter Controls */}
      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
            gap: 2,
            alignItems: 'center',
          }}
        >
          <TextField
            fullWidth
            placeholder="Search configurations..."
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
              Strategy Type
            </InputLabel>
            <Select
              labelId="strategy-type-filter-label"
              value={strategyTypeFilter}
              label="Strategy Type"
              onChange={handleStrategyTypeChange}
            >
              <MenuItem value="all">All Types</MenuItem>
              {strategyTypes.map((type) => (
                <MenuItem key={type} value={type}>
                  {getStrategyDisplayName(strategies, type)}
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
              <Button
                color="inherit"
                size="small"
                onClick={() => window.location.reload()}
              >
                Reload
              </Button>
            )
          }
        >
          <Typography variant="body2" gutterBottom>
            <strong>Failed to load configurations</strong>
          </Typography>
          <Typography variant="body2">
            {error.message.toLowerCase().includes('connection refused') ||
            error.message.toLowerCase().includes('failed to fetch')
              ? 'Cannot connect to server. Please check if the backend is running.'
              : error.message.includes('429') ||
                  error.message.includes('Too Many Requests')
                ? 'Too many requests. Please wait a moment and try again.'
                : error.message.includes('502') ||
                    error.message.includes('Bad Gateway')
                  ? 'Server is temporarily unavailable. Please try again later.'
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
              ? 'No configurations found'
              : 'No configurations yet'}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            {search || strategyTypeFilter !== 'all'
              ? 'Try adjusting your search or filters'
              : 'Create your first strategy configuration to get started'}
          </Typography>
          {!search && strategyTypeFilter === 'all' && (
            <Button
              variant="contained"
              color="primary"
              startIcon={<AddIcon />}
              onClick={handleCreateNew}
            >
              Create Configuration
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
          {(hasNextPage || hasPreviousPage) && (
            <Box
              sx={{ display: 'flex', justifyContent: 'center', gap: 2, mt: 4 }}
            >
              <Button
                variant="outlined"
                onClick={handlePreviousPage}
                disabled={!hasPreviousPage || isLoading}
              >
                Previous
              </Button>
              <Button
                variant="outlined"
                onClick={handleNextPage}
                disabled={!hasNextPage || isLoading}
              >
                Next
              </Button>
            </Box>
          )}
        </>
      )}
    </Container>
  );
};

export default ConfigurationsPage;
