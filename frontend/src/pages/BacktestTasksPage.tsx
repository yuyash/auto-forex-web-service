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
  type SelectChangeEvent,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import {
  Add as AddIcon,
  Search as SearchIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  useBacktestTasks,
  invalidateBacktestTasksCache,
} from '../hooks/useBacktestTasks';
import { TaskStatus } from '../types/common';
import BacktestTaskCard from '../components/backtest/BacktestTaskCard';
import { LoadingSpinner, Breadcrumbs } from '../components/common';

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
  const navigate = useNavigate();
  const location = useLocation();
  const [tabValue, setTabValue] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('-created_at');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Force refetch when navigating back after a deletion
  useEffect(() => {
    if (location.state?.deleted) {
      invalidateBacktestTasksCache();
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
        return TaskStatus.COMPLETED;
      case 3:
        return TaskStatus.FAILED;
      default:
        return undefined; // All tasks
    }
  };

  const { data, isLoading, error, refetch } = useBacktestTasks({
    page,
    page_size: pageSize,
    search: searchQuery || undefined,
    status: getStatusFilter(),
    ordering: sortBy,
  });

  // Auto-refresh every 10 seconds when there are running tasks
  // This ensures status changes are detected across all pages
  const autoRefreshIntervalRef = useRef<ReturnType<typeof setInterval> | null>(
    null
  );

  useEffect(() => {
    const hasRunningTasks = data?.results.some(
      (task) => task.status === TaskStatus.RUNNING
    );

    // Clear existing interval
    if (autoRefreshIntervalRef.current) {
      clearInterval(autoRefreshIntervalRef.current);
      autoRefreshIntervalRef.current = null;
    }

    // Set up auto-refresh if there are running tasks
    if (hasRunningTasks) {
      autoRefreshIntervalRef.current = setInterval(() => {
        console.log('[BacktestTasksPage] Auto-refreshing task list');
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
            Backtest Tasks
          </Typography>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={handleRefresh}
              disabled={isLoading}
            >
              Refresh
            </Button>
            <Button
              variant="outlined"
              onClick={() => navigate('/configurations?from=backtest-tasks')}
            >
              Manage Configurations
            </Button>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleCreateTask}
            >
              New Task
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
            <Tab label="All" {...a11yProps(0)} />
            <Tab label="Running" {...a11yProps(1)} />
            <Tab label="Completed" {...a11yProps(2)} />
            <Tab label="Failed" {...a11yProps(3)} />
          </Tabs>
        </Paper>

        {/* Filters */}
        <Paper sx={{ p: 2, mb: 3 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                placeholder="Search tasks..."
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
                <InputLabel>Sort By</InputLabel>
                <Select
                  value={sortBy}
                  onChange={handleSortChange}
                  label="Sort By"
                >
                  <MenuItem value="-created_at">Newest First</MenuItem>
                  <MenuItem value="created_at">Oldest First</MenuItem>
                  <MenuItem value="name">Name (A-Z)</MenuItem>
                  <MenuItem value="-name">Name (Z-A)</MenuItem>
                  <MenuItem value="-updated_at">Recently Updated</MenuItem>
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
              <Typography color="error">
                Error loading tasks: {error.message}
              </Typography>
            </Paper>
          ) : !data || data.results.length === 0 ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography variant="h6" color="text.secondary" gutterBottom>
                No backtest tasks found
              </Typography>
              <Typography color="text.secondary" sx={{ mb: 2 }}>
                Create your first backtest task to get started
              </Typography>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={handleCreateTask}
              >
                Create Task
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
                    size="large"
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
              <Typography color="error">
                Error loading tasks: {error.message}
              </Typography>
            </Paper>
          ) : !data || data.results.length === 0 ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography variant="h6" color="text.secondary">
                No running tasks
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
                    size="large"
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
              <Typography color="error">
                Error loading tasks: {error.message}
              </Typography>
            </Paper>
          ) : !data || data.results.length === 0 ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography variant="h6" color="text.secondary">
                No completed tasks
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
                    size="large"
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
              <Typography color="error">
                Error loading tasks: {error.message}
              </Typography>
            </Paper>
          ) : !data || data.results.length === 0 ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography variant="h6" color="text.secondary">
                No failed tasks
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
                    size="large"
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
