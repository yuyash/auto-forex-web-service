import { useState, useEffect, useCallback } from 'react';
import {
  Container,
  Typography,
  Box,
  Paper,
  Grid,
  TextField,
  MenuItem,
  Button,
  Chip,
  Alert,
  CircularProgress,
} from '@mui/material';
import {
  Download as DownloadIcon,
  FilterList as FilterListIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import DataTable from '../components/common/DataTable';
import type { Column } from '../components/common/DataTable';
import type { Order, OrderFilters } from '../types/order';

const OrderHistoryPage = () => {
  const { t } = useTranslation(['orders', 'common']);
  const { token } = useAuth();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<OrderFilters>({});
  const [searchOrderId, setSearchOrderId] = useState('');

  // Fetch orders from API
  const fetchOrders = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    setError(null);

    try {
      // Build query parameters
      const params = new URLSearchParams();
      if (filters.start_date) params.append('start_date', filters.start_date);
      if (filters.end_date) params.append('end_date', filters.end_date);
      if (filters.instrument) params.append('instrument', filters.instrument);
      if (filters.status) params.append('status', filters.status);
      if (searchOrderId) params.append('order_id', searchOrderId);

      const response = await fetch(`/api/orders?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch orders');
      }

      const data = await response.json();
      const ordersData = data.results || data;
      setOrders(Array.isArray(ordersData) ? ordersData : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    token,
    filters.start_date,
    filters.end_date,
    filters.instrument,
    filters.status,
    searchOrderId,
  ]);

  // Fetch orders on mount and when filters change
  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  // Handle filter changes
  const handleFilterChange = (field: keyof OrderFilters, value: string) => {
    setFilters((prev) => ({
      ...prev,
      [field]: value || undefined,
    }));
  };

  // Clear all filters
  const handleClearFilters = () => {
    setFilters({});
    setSearchOrderId('');
  };

  // Export to CSV
  const handleExportCSV = () => {
    if (orders.length === 0) return;

    // Create CSV content
    const headers = [
      t('orders:columns.date'),
      t('orders:columns.orderId'),
      t('orders:columns.instrument'),
      t('orders:columns.type'),
      t('orders:columns.direction'),
      t('orders:columns.units'),
      t('orders:columns.price'),
      t('orders:columns.status'),
    ];

    const rows = orders.map((order) => [
      new Date(order.created_at).toLocaleString(),
      order.order_id,
      order.instrument,
      order.order_type,
      order.direction,
      order.units.toString(),
      order.price?.toString() || 'N/A',
      order.status,
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map((row) => row.map((cell) => `"${cell}"`).join(',')),
    ].join('\n');

    // Create and download file
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `orders_${new Date().toISOString()}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Get unique instruments from orders
  const instruments = Array.from(
    new Set((orders || []).map((o) => o.instrument))
  ).sort();

  // Define table columns
  const columns: Column<Order>[] = [
    {
      id: 'created_at',
      label: t('orders:columns.date'),
      sortable: true,
      render: (order) => new Date(order.created_at).toLocaleString(),
      minWidth: 180,
    },
    {
      id: 'order_id',
      label: t('orders:columns.orderId'),
      sortable: true,
      minWidth: 120,
    },
    {
      id: 'instrument',
      label: t('orders:columns.instrument'),
      sortable: true,
      filterable: true,
      minWidth: 100,
    },
    {
      id: 'order_type',
      label: t('orders:columns.type'),
      sortable: true,
      render: (order) => (
        <Chip
          label={t(`orders:orderTypes.${order.order_type}`)}
          size="small"
          color="default"
        />
      ),
      minWidth: 100,
    },
    {
      id: 'direction',
      label: t('orders:columns.direction'),
      sortable: true,
      render: (order) => (
        <Chip
          label={t(`orders:directions.${order.direction}`)}
          size="small"
          color={order.direction === 'BUY' ? 'success' : 'error'}
        />
      ),
      minWidth: 100,
    },
    {
      id: 'units',
      label: t('orders:columns.units'),
      sortable: true,
      align: 'right',
      minWidth: 100,
    },
    {
      id: 'price',
      label: t('orders:columns.price'),
      sortable: true,
      align: 'right',
      render: (order) => order.price?.toFixed(5) || 'N/A',
      minWidth: 100,
    },
    {
      id: 'status',
      label: t('orders:columns.status'),
      sortable: true,
      render: (order) => {
        const statusColors: Record<
          string,
          'default' | 'success' | 'warning' | 'error'
        > = {
          PENDING: 'warning',
          FILLED: 'success',
          CANCELLED: 'default',
          REJECTED: 'error',
        };
        return (
          <Chip
            label={t(`orders:statuses.${order.status}`)}
            size="small"
            color={statusColors[order.status] || 'default'}
          />
        );
      },
      minWidth: 120,
    },
  ];

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Box>
        <Typography variant="h4" gutterBottom>
          {t('orders:title')}
        </Typography>

        {/* Filters Section */}
        <Paper sx={{ p: 3, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <FilterListIcon sx={{ mr: 1 }} />
            <Typography variant="h6">{t('common:actions.filter')}</Typography>
          </Box>

          <Grid container spacing={2}>
            {/* Date Range */}
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <TextField
                fullWidth
                label={t('orders:filters.startDate')}
                type="date"
                value={filters.start_date || ''}
                onChange={(e) =>
                  handleFilterChange('start_date', e.target.value)
                }
                InputLabelProps={{ shrink: true }}
                size="small"
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <TextField
                fullWidth
                label={t('orders:filters.endDate')}
                type="date"
                value={filters.end_date || ''}
                onChange={(e) => handleFilterChange('end_date', e.target.value)}
                InputLabelProps={{ shrink: true }}
                size="small"
              />
            </Grid>

            {/* Instrument Filter */}
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <TextField
                fullWidth
                select
                label={t('orders:filters.instrument')}
                value={filters.instrument || ''}
                onChange={(e) =>
                  handleFilterChange('instrument', e.target.value)
                }
                size="small"
              >
                <MenuItem value="">
                  {t('orders:filters.allInstruments')}
                </MenuItem>
                {instruments.map((instrument) => (
                  <MenuItem key={instrument} value={instrument}>
                    {instrument}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>

            {/* Status Filter */}
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <TextField
                fullWidth
                select
                label={t('orders:filters.status')}
                value={filters.status || ''}
                onChange={(e) => handleFilterChange('status', e.target.value)}
                size="small"
              >
                <MenuItem value="">{t('orders:filters.allStatuses')}</MenuItem>
                <MenuItem value="PENDING">
                  {t('orders:statuses.PENDING')}
                </MenuItem>
                <MenuItem value="FILLED">
                  {t('orders:statuses.FILLED')}
                </MenuItem>
                <MenuItem value="CANCELLED">
                  {t('orders:statuses.CANCELLED')}
                </MenuItem>
                <MenuItem value="REJECTED">
                  {t('orders:statuses.REJECTED')}
                </MenuItem>
              </TextField>
            </Grid>

            {/* Order ID Search */}
            <Grid size={{ xs: 12, sm: 6, md: 6 }}>
              <TextField
                fullWidth
                label={t('orders:filters.searchOrderId')}
                value={searchOrderId}
                onChange={(e) => setSearchOrderId(e.target.value)}
                size="small"
                placeholder="e.g., 12345"
              />
            </Grid>

            {/* Action Buttons */}
            <Grid size={{ xs: 12, sm: 6, md: 6 }}>
              <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                <Button
                  variant="outlined"
                  onClick={handleClearFilters}
                  size="small"
                  aria-label="Clear Filters"
                >
                  {t('orders:actions.clearFilters')}
                </Button>
                <Button
                  variant="contained"
                  onClick={fetchOrders}
                  size="small"
                  aria-label="Apply Filters"
                >
                  {t('orders:actions.applyFilters')}
                </Button>
              </Box>
            </Grid>
          </Grid>
        </Paper>

        {/* Export Button */}
        <Box sx={{ mb: 2, display: 'flex', justifyContent: 'flex-end' }}>
          <Button
            variant="contained"
            startIcon={<DownloadIcon />}
            onClick={handleExportCSV}
            disabled={orders.length === 0}
          >
            {t('orders:actions.exportCSV')}
          </Button>
        </Box>

        {/* Error Alert */}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {t('orders:messages.errorLoadingOrders')}: {error}
          </Alert>
        )}

        {/* Loading State */}
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
            <CircularProgress />
          </Box>
        )}

        {/* Orders Table */}
        {!loading && (
          <DataTable<Order>
            columns={columns}
            data={orders}
            emptyMessage={t('orders:messages.noOrders')}
            defaultRowsPerPage={25}
            rowsPerPageOptions={[10, 25, 50, 100]}
          />
        )}
      </Box>
    </Container>
  );
};

export default OrderHistoryPage;
