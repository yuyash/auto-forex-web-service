import React, { useState, useEffect, useCallback } from 'react';
import {
  Paper,
  Typography,
  Box,
  Chip,
  TextField,
  MenuItem,
  Button,
  CircularProgress,
  Alert,
  Grid,
} from '@mui/material';
import {
  Info as InfoIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  BugReport as BugReportIcon,
  CrisisAlert as CrisisAlertIcon,
  Download as DownloadIcon,
  Search as SearchIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import DataTable, { type Column } from '../common/DataTable';
import type { AdminEvent } from '../../types/admin';
import { useAuth } from '../../contexts/AuthContext';

interface EventFilters {
  category: string;
  severity: string;
  username: string;
  startDate: Date | null;
  endDate: Date | null;
  search: string;
}

const EventViewer: React.FC = () => {
  const { t } = useTranslation('admin');
  const { token } = useAuth();
  const [events, setEvents] = useState<AdminEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [filters, setFilters] = useState<EventFilters>({
    category: '',
    severity: '',
    username: '',
    startDate: null,
    endDate: null,
    search: '',
  });

  const rowsPerPage = 50;

  const fetchEvents = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.append('page', String(page + 1));
      params.append('page_size', String(rowsPerPage));

      if (filters.category) params.append('category', filters.category);
      if (filters.severity) params.append('severity', filters.severity);
      if (filters.username) params.append('username', filters.username);
      if (filters.startDate) {
        params.append('start_date', filters.startDate.toISOString());
      }
      if (filters.endDate) {
        params.append('end_date', filters.endDate.toISOString());
      }
      if (filters.search) params.append('search', filters.search);

      const response = await fetch(`/api/events?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch events');
      }

      const data = await response.json();
      setEvents(data.results || data);
      setTotalCount(data.count || data.length);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load events');
    } finally {
      setLoading(false);
    }
  }, [token, page, filters]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const handleFilterChange = (field: keyof EventFilters, value: unknown) => {
    setFilters((prev) => ({ ...prev, [field]: value }));
    setPage(0);
  };

  const handleSearch = () => {
    setPage(0);
    fetchEvents();
  };

  const handleExportCSV = async () => {
    if (!token) return;

    try {
      const params = new URLSearchParams();
      if (filters.category) params.append('category', filters.category);
      if (filters.severity) params.append('severity', filters.severity);
      if (filters.username) params.append('username', filters.username);
      if (filters.startDate) {
        params.append('start_date', filters.startDate.toISOString());
      }
      if (filters.endDate) {
        params.append('end_date', filters.endDate.toISOString());
      }
      if (filters.search) params.append('search', filters.search);
      params.append('format', 'csv');

      const response = await fetch(`/api/events/export?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to export events');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `events_${new Date().toISOString()}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export events');
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'debug':
        return <BugReportIcon fontSize="small" />;
      case 'info':
        return <InfoIcon fontSize="small" />;
      case 'warning':
        return <WarningIcon fontSize="small" />;
      case 'error':
        return <ErrorIcon fontSize="small" />;
      case 'critical':
        return <CrisisAlertIcon fontSize="small" />;
      default:
        return <InfoIcon fontSize="small" />;
    }
  };

  const getSeverityColor = (
    severity: string
  ):
    | 'default'
    | 'primary'
    | 'secondary'
    | 'error'
    | 'info'
    | 'success'
    | 'warning' => {
    switch (severity) {
      case 'debug':
        return 'default';
      case 'info':
        return 'info';
      case 'warning':
        return 'warning';
      case 'error':
        return 'error';
      case 'critical':
        return 'error';
      default:
        return 'default';
    }
  };

  const getCategoryColor = (
    category: string
  ):
    | 'default'
    | 'primary'
    | 'secondary'
    | 'error'
    | 'info'
    | 'success'
    | 'warning' => {
    switch (category.toLowerCase()) {
      case 'trading':
        return 'primary';
      case 'system':
        return 'info';
      case 'security':
        return 'error';
      case 'admin':
        return 'secondary';
      default:
        return 'default';
    }
  };

  const formatDateTime = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const columns: Column<AdminEvent & Record<string, unknown>>[] = [
    {
      id: 'timestamp',
      label: t('events.timestamp'),
      sortable: true,
      render: (row) => (
        <Typography variant="body2" sx={{ whiteSpace: 'nowrap' }}>
          {formatDateTime(row.timestamp)}
        </Typography>
      ),
      minWidth: 180,
    },
    {
      id: 'severity',
      label: t('events.severity'),
      sortable: true,
      render: (row) => (
        <Chip
          icon={getSeverityIcon(row.severity)}
          label={t(`events.severities.${row.severity}`, row.severity)}
          color={getSeverityColor(row.severity)}
          size="small"
        />
      ),
      minWidth: 120,
    },
    {
      id: 'category',
      label: t('events.category'),
      sortable: true,
      render: (row) => (
        <Chip
          label={t(`events.categories.${row.category}`, row.category)}
          color={getCategoryColor(row.category)}
          size="small"
          variant="outlined"
        />
      ),
      minWidth: 120,
    },
    {
      id: 'event_type',
      label: t('events.eventType'),
      sortable: true,
      minWidth: 150,
    },
    {
      id: 'description',
      label: t('events.description'),
      sortable: false,
      minWidth: 300,
      render: (row) => (
        <Typography
          variant="body2"
          sx={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
          }}
        >
          {row.description}
        </Typography>
      ),
    },
    {
      id: 'user',
      label: t('events.user'),
      sortable: true,
      render: (row) => row.user || '-',
      minWidth: 120,
    },
    {
      id: 'ip_address',
      label: t('events.ipAddress'),
      sortable: true,
      render: (row) => row.ip_address || '-',
      minWidth: 130,
    },
  ];

  const categories = ['', 'trading', 'system', 'security', 'admin'];
  const severities = ['', 'debug', 'info', 'warning', 'error', 'critical'];

  return (
    <Paper elevation={2} sx={{ p: 3 }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 3,
        }}
      >
        <Box>
          <Typography variant="h5" gutterBottom>
            {t('events.title')}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {t('events.subtitle', 'View and search all system events')}
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<DownloadIcon />}
          onClick={handleExportCSV}
          disabled={loading || events.length === 0}
        >
          {t('events.exportCSV', 'Export CSV')}
        </Button>
      </Box>

      {/* Filters */}
      <Box sx={{ mb: 3 }}>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <TextField
              select
              fullWidth
              label={t('events.category')}
              value={filters.category}
              onChange={(e) => handleFilterChange('category', e.target.value)}
              size="small"
            >
              {categories.map((cat) => (
                <MenuItem key={cat} value={cat}>
                  {cat
                    ? t(`events.categories.${cat}`, cat)
                    : t('events.allCategories', 'All Categories')}
                </MenuItem>
              ))}
            </TextField>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <TextField
              select
              fullWidth
              label={t('events.severity')}
              value={filters.severity}
              onChange={(e) => handleFilterChange('severity', e.target.value)}
              size="small"
            >
              {severities.map((sev) => (
                <MenuItem key={sev} value={sev}>
                  {sev
                    ? t(`events.severities.${sev}`, sev)
                    : t('events.allSeverities', 'All Severities')}
                </MenuItem>
              ))}
            </TextField>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <TextField
              fullWidth
              label={t('events.username', 'Username')}
              value={filters.username}
              onChange={(e) => handleFilterChange('username', e.target.value)}
              size="small"
              placeholder={t('events.filterByUsername', 'Filter by username')}
            />
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <TextField
              fullWidth
              label={t('events.search', 'Search')}
              value={filters.search}
              onChange={(e) => handleFilterChange('search', e.target.value)}
              size="small"
              placeholder={t(
                'events.searchPlaceholder',
                'Search description...'
              )}
              InputProps={{
                endAdornment: (
                  <SearchIcon color="action" sx={{ cursor: 'pointer' }} />
                ),
              }}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  handleSearch();
                }
              }}
            />
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <LocalizationProvider dateAdapter={AdapterDateFns}>
              <DatePicker
                label={t('events.startDate', 'Start Date')}
                value={filters.startDate}
                onChange={(date) => handleFilterChange('startDate', date)}
                slotProps={{
                  textField: {
                    size: 'small',
                    fullWidth: true,
                  },
                }}
              />
            </LocalizationProvider>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <LocalizationProvider dateAdapter={AdapterDateFns}>
              <DatePicker
                label={t('events.endDate', 'End Date')}
                value={filters.endDate}
                onChange={(date) => handleFilterChange('endDate', date)}
                slotProps={{
                  textField: {
                    size: 'small',
                    fullWidth: true,
                  },
                }}
              />
            </LocalizationProvider>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Button
              fullWidth
              variant="outlined"
              onClick={handleSearch}
              startIcon={<SearchIcon />}
              sx={{ height: '40px' }}
            >
              {t('events.applyFilters', 'Apply Filters')}
            </Button>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Button
              fullWidth
              variant="text"
              onClick={() => {
                setFilters({
                  category: '',
                  severity: '',
                  username: '',
                  startDate: null,
                  endDate: null,
                  search: '',
                });
                setPage(0);
              }}
              sx={{ height: '40px' }}
            >
              {t('events.clearFilters', 'Clear Filters')}
            </Button>
          </Grid>
        </Grid>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Loading State */}
      {loading ? (
        <Box
          display="flex"
          justifyContent="center"
          alignItems="center"
          minHeight="400px"
        >
          <CircularProgress />
        </Box>
      ) : (
        <>
          {/* Results Count */}
          <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" color="text.secondary">
              {t('events.showing', 'Showing')} {page * rowsPerPage + 1}-
              {Math.min((page + 1) * rowsPerPage, totalCount)}{' '}
              {t('events.of', 'of')} {totalCount} {t('events.events', 'events')}
            </Typography>
          </Box>

          {/* Events Table */}
          {events.length === 0 ? (
            <Box
              sx={{
                py: 8,
                textAlign: 'center',
              }}
            >
              <Typography variant="body1" color="text.secondary">
                {t('events.noEvents')}
              </Typography>
            </Box>
          ) : (
            <DataTable
              columns={columns}
              data={events as (AdminEvent & Record<string, unknown>)[]}
              emptyMessage={t('events.noEvents')}
              defaultRowsPerPage={50}
              rowsPerPageOptions={[50]}
              stickyHeader={true}
            />
          )}

          {/* Pagination Controls */}
          {totalCount > rowsPerPage && (
            <Box
              sx={{
                mt: 2,
                display: 'flex',
                justifyContent: 'center',
                gap: 2,
              }}
            >
              <Button
                variant="outlined"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                {t('events.previous', 'Previous')}
              </Button>
              <Typography
                variant="body2"
                sx={{ display: 'flex', alignItems: 'center' }}
              >
                {t('events.page', 'Page')} {page + 1} {t('events.of', 'of')}{' '}
                {Math.ceil(totalCount / rowsPerPage)}
              </Typography>
              <Button
                variant="outlined"
                disabled={(page + 1) * rowsPerPage >= totalCount}
                onClick={() => setPage((p) => p + 1)}
              >
                {t('events.next', 'Next')}
              </Button>
            </Box>
          )}
        </>
      )}
    </Paper>
  );
};

export default EventViewer;
