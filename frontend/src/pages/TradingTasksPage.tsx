import { useState } from 'react';

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
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useTradingTasks } from '../hooks/useTradingTasks';
import { useConfigurations } from '../hooks/useConfigurations';
import { TaskStatus } from '../types/common';
import TradingTaskCard from '../components/trading/TradingTaskCard';
import { Breadcrumbs } from '../components/common';
import { LoadingSpinner } from '../components/common';

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
  const navigate = useNavigate();
  const [tabValue, setTabValue] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('-created_at');
  const [configFilter, setConfigFilter] = useState<number | ''>('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

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

  const { data, isLoading, error } = useTradingTasks({
    page,
    page_size: pageSize,
    search: searchQuery || undefined,
    status: getStatusFilter(),
    config_id: configFilter || undefined,
    ordering: sortBy,
  });

  // Fetch configurations for filter dropdown
  const { data: configurationsData } = useConfigurations({
    page: 1,
    page_size: 100, // Get enough for dropdown
  });

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
    target: { value: number | '' };
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
    <Container maxWidth="xl">
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
            Trading Tasks
          </Typography>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="outlined"
              onClick={() => navigate('/configurations')}
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

        {/* Warning about one-task-per-account rule */}
        <Alert severity="warning" icon={<WarningIcon />} sx={{ mb: 3 }}>
          <AlertTitle>Important: One Task Per Account</AlertTitle>
          Only one trading task can be running per account at a time. Starting a
          new task on an account with an active task will stop the existing
          task.
        </Alert>

        {/* Tabs */}
        <Paper sx={{ mb: 3 }}>
          <Tabs
            value={tabValue}
            onChange={handleTabChange}
            aria-label="trading tasks tabs"
            sx={{ borderBottom: 1, borderColor: 'divider' }}
          >
            <Tab label="All" {...a11yProps(0)} />
            <Tab label="Running" {...a11yProps(1)} />
            <Tab label="Paused" {...a11yProps(2)} />
            <Tab label="Stopped" {...a11yProps(3)} />
          </Tabs>
        </Paper>

        {/* Filters */}
        <Paper sx={{ p: 2, mb: 3 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid size={{ xs: 12, md: 4 }}>
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
            <Grid size={{ xs: 12, md: 4 }}>
              <FormControl fullWidth>
                <InputLabel>Configuration</InputLabel>
                <Select
                  value={configFilter}
                  onChange={handleConfigFilterChange}
                  label="Configuration"
                >
                  <MenuItem value="">All Configurations</MenuItem>
                  {configurationsData?.results.map((config) => (
                    <MenuItem key={config.id} value={config.id}>
                      {config.name} ({config.strategy_type})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
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
                No trading tasks found
              </Typography>
              <Typography color="text.secondary" sx={{ mb: 2 }}>
                Create your first trading task to start automated trading
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
                  <Grid size={{ xs: 12 }} key={task.id}>
                    <TradingTaskCard task={task} />
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
                  <Grid size={{ xs: 12 }} key={task.id}>
                    <TradingTaskCard task={task} />
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
                No paused tasks
              </Typography>
            </Paper>
          ) : (
            <>
              <Grid container spacing={3}>
                {data.results.map((task) => (
                  <Grid size={{ xs: 12 }} key={task.id}>
                    <TradingTaskCard task={task} />
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
                No stopped tasks
              </Typography>
            </Paper>
          ) : (
            <>
              <Grid container spacing={3}>
                {data.results.map((task) => (
                  <Grid size={{ xs: 12 }} key={task.id}>
                    <TradingTaskCard task={task} />
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
