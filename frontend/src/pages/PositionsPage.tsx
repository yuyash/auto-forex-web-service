import { useState, useEffect, useCallback } from 'react';

import {
  Typography,
  Box,
  Paper,
  TextField,
  MenuItem,
  Button,
  Chip,
  Alert,
  CircularProgress,
  Tabs,
  Tab,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import {
  Download as DownloadIcon,
  FilterList as FilterListIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { Breadcrumbs } from '../components/common';
import DataTable from '../components/common/DataTable';
import type { Column } from '../components/common/DataTable';
import type { Position, PositionFilters } from '../types/position';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = (props: TabPanelProps) => {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`positions-tabpanel-${index}`}
      aria-labelledby={`positions-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
};

const PositionsPage = () => {
  const { t } = useTranslation(['positions', 'common']);
  const { token } = useAuth();
  const [activePositions, setActivePositions] = useState<Position[]>([]);
  const [closedPositions, setClosedPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<PositionFilters>({});
  const [tabValue, setTabValue] = useState(0);

  // Fetch positions from API
  const fetchPositions = useCallback(
    async (status: 'OPEN' | 'CLOSED') => {
      if (!token) return;

      try {
        // Build query parameters
        const params = new URLSearchParams();
        params.append('status', status);
        if (filters.start_date) params.append('start_date', filters.start_date);
        if (filters.end_date) params.append('end_date', filters.end_date);
        if (filters.instrument) params.append('instrument', filters.instrument);
        if (filters.layer) params.append('layer', filters.layer);

        const response = await fetch(`/api/positions?${params.toString()}`, {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (!response.ok) {
          throw new Error('Failed to fetch positions');
        }

        const data = await response.json();
        const positionsData = data.results || data;
        const positions = Array.isArray(positionsData) ? positionsData : [];

        if (status === 'OPEN') {
          setActivePositions(positions);
        } else {
          setClosedPositions(positions);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      }
    },

    [
      token,
      filters.start_date,
      filters.end_date,
      filters.instrument,
      filters.layer,
    ]
  );

  // Fetch positions on mount and when filters change
  useEffect(() => {
    const fetchBoth = async () => {
      setLoading(true);
      setError(null);
      await fetchPositions('OPEN');
      await fetchPositions('CLOSED');
      setLoading(false);
    };
    fetchBoth();
  }, [fetchPositions]);

  // Handle filter changes
  const handleFilterChange = (field: keyof PositionFilters, value: string) => {
    setFilters((prev) => ({
      ...prev,
      [field]: value || undefined,
    }));
  };

  // Clear all filters
  const handleClearFilters = () => {
    setFilters({});
  };

  // Handle tab change
  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  // Export to CSV
  const handleExportCSV = (positions: Position[], filename: string) => {
    if (positions.length === 0) return;

    // Create CSV content
    const headers = [
      t('positions:columns.date'),
      t('positions:columns.positionId'),
      t('positions:columns.instrument'),
      t('positions:columns.direction'),
      t('positions:columns.units'),
      t('positions:columns.entryPrice'),
      tabValue === 0
        ? t('positions:columns.currentPrice')
        : t('positions:columns.closedAt'),
      tabValue === 0
        ? t('positions:columns.unrealizedPnL')
        : t('positions:columns.realizedPnL'),
      t('positions:columns.layer'),
      t('positions:columns.strategy'),
    ];

    const rows = positions.map((position) => [
      new Date(position.opened_at).toLocaleString(),
      position.position_id,
      position.instrument,
      position.direction,
      position.units.toString(),
      position.entry_price.toFixed(5),
      tabValue === 0
        ? position.current_price.toFixed(5)
        : position.closed_at
          ? new Date(position.closed_at).toLocaleString()
          : 'N/A',
      tabValue === 0
        ? position.unrealized_pnl.toFixed(2)
        : (position.realized_pnl || 0).toFixed(2),
      position.layer?.toString() || 'N/A',
      position.strategy || 'N/A',
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
    link.setAttribute(
      'download',
      `${filename}_${new Date().toISOString()}.csv`
    );
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Get unique instruments from positions
  const allPositions = [
    ...(Array.isArray(activePositions) ? activePositions : []),
    ...(Array.isArray(closedPositions) ? closedPositions : []),
  ];
  const instruments = Array.from(
    new Set(allPositions.map((p) => p.instrument))
  ).sort();

  // Get unique layers from positions
  const layers = Array.from(
    new Set(
      allPositions
        .map((p) => p.layer)
        .filter((layer): layer is number => layer !== undefined)
    )
  ).sort((a, b) => a - b);

  // Define table columns for active positions
  const activeColumns: Column<Position>[] = [
    {
      id: 'opened_at',
      label: t('positions:columns.date'),
      sortable: true,
      render: (position) => new Date(position.opened_at).toLocaleString(),
      minWidth: 180,
    },
    {
      id: 'position_id',
      label: t('positions:columns.positionId'),
      sortable: true,
      minWidth: 120,
    },
    {
      id: 'instrument',
      label: t('positions:columns.instrument'),
      sortable: true,
      filterable: true,
      minWidth: 100,
    },
    {
      id: 'direction',
      label: t('positions:columns.direction'),
      sortable: true,
      render: (position) => (
        <Chip
          label={t(`positions:directions.${position.direction}`)}
          size="small"
          color={position.direction === 'LONG' ? 'success' : 'error'}
        />
      ),
      minWidth: 100,
    },
    {
      id: 'units',
      label: t('positions:columns.units'),
      sortable: true,
      align: 'right',
      minWidth: 100,
    },
    {
      id: 'entry_price',
      label: t('positions:columns.entryPrice'),
      sortable: true,
      align: 'right',
      render: (position) => position.entry_price.toFixed(5),
      minWidth: 120,
    },
    {
      id: 'current_price',
      label: t('positions:columns.currentPrice'),
      sortable: true,
      align: 'right',
      render: (position) => position.current_price.toFixed(5),
      minWidth: 120,
    },
    {
      id: 'unrealized_pnl',
      label: t('positions:columns.unrealizedPnL'),
      sortable: true,
      align: 'right',
      render: (position) => {
        const pnl = position.unrealized_pnl;
        return (
          <Chip
            label={`${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}`}
            size="small"
            color={pnl >= 0 ? 'success' : 'error'}
          />
        );
      },
      minWidth: 140,
    },
    {
      id: 'layer',
      label: t('positions:columns.layer'),
      sortable: true,
      align: 'center',
      render: (position) => position.layer || 'N/A',
      minWidth: 80,
    },
    {
      id: 'strategy',
      label: t('positions:columns.strategy'),
      sortable: true,
      render: (position) => position.strategy || 'N/A',
      minWidth: 120,
    },
  ];

  // Define table columns for closed positions
  const closedColumns: Column<Position>[] = [
    {
      id: 'opened_at',
      label: t('positions:columns.date'),
      sortable: true,
      render: (position) => new Date(position.opened_at).toLocaleString(),
      minWidth: 180,
    },
    {
      id: 'position_id',
      label: t('positions:columns.positionId'),
      sortable: true,
      minWidth: 120,
    },
    {
      id: 'instrument',
      label: t('positions:columns.instrument'),
      sortable: true,
      filterable: true,
      minWidth: 100,
    },
    {
      id: 'direction',
      label: t('positions:columns.direction'),
      sortable: true,
      render: (position) => (
        <Chip
          label={t(`positions:directions.${position.direction}`)}
          size="small"
          color={position.direction === 'LONG' ? 'success' : 'error'}
        />
      ),
      minWidth: 100,
    },
    {
      id: 'units',
      label: t('positions:columns.units'),
      sortable: true,
      align: 'right',
      minWidth: 100,
    },
    {
      id: 'entry_price',
      label: t('positions:columns.entryPrice'),
      sortable: true,
      align: 'right',
      render: (position) => position.entry_price.toFixed(5),
      minWidth: 120,
    },
    {
      id: 'closed_at',
      label: t('positions:columns.closedAt'),
      sortable: true,
      render: (position) =>
        position.closed_at
          ? new Date(position.closed_at).toLocaleString()
          : 'N/A',
      minWidth: 180,
    },
    {
      id: 'realized_pnl',
      label: t('positions:columns.realizedPnL'),
      sortable: true,
      align: 'right',
      render: (position) => {
        const pnl = position.realized_pnl || 0;
        return (
          <Chip
            label={`${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}`}
            size="small"
            color={pnl >= 0 ? 'success' : 'error'}
          />
        );
      },
      minWidth: 140,
    },
    {
      id: 'layer',
      label: t('positions:columns.layer'),
      sortable: true,
      align: 'center',
      render: (position) => position.layer || 'N/A',
      minWidth: 80,
    },
    {
      id: 'strategy',
      label: t('positions:columns.strategy'),
      sortable: true,
      render: (position) => position.strategy || 'N/A',
      minWidth: 120,
    },
  ];

  return (
    <Box
      sx={{
        width: '100%',
        maxWidth: '100vw',
        px: { xs: 2, sm: 3 },
        py: { xs: 2, sm: 4 },
        boxSizing: 'border-box',
      }}
    >
      <Breadcrumbs />
      <Typography variant="h4" gutterBottom>
        {t('positions:title')}
      </Typography>

      {/* Filters Section */}
      <Paper sx={{ p: { xs: 2, sm: 3 }, mb: 3, width: '100%' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <FilterListIcon sx={{ mr: 1 }} />
          <Typography variant="h6">{t('common:actions.filter')}</Typography>
        </Box>

        <Grid container spacing={2}>
          {/* Date Range */}
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <TextField
              fullWidth
              label={t('positions:filters.startDate')}
              type="date"
              value={filters.start_date || ''}
              onChange={(e) => handleFilterChange('start_date', e.target.value)}
              InputLabelProps={{ shrink: true }}
              size="small"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <TextField
              fullWidth
              label={t('positions:filters.endDate')}
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
              label={t('positions:filters.instrument')}
              value={filters.instrument || ''}
              onChange={(e) => handleFilterChange('instrument', e.target.value)}
              size="small"
            >
              <MenuItem value="">
                {t('positions:filters.allInstruments')}
              </MenuItem>
              {instruments.map((instrument) => (
                <MenuItem key={instrument} value={instrument}>
                  {instrument}
                </MenuItem>
              ))}
            </TextField>
          </Grid>

          {/* Layer Filter */}
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <TextField
              fullWidth
              select
              label={t('positions:filters.layer')}
              value={filters.layer || ''}
              onChange={(e) => handleFilterChange('layer', e.target.value)}
              size="small"
            >
              <MenuItem value="">{t('positions:filters.allLayers')}</MenuItem>
              {layers.map((layer) => (
                <MenuItem key={layer} value={layer.toString()}>
                  {layer}
                </MenuItem>
              ))}
            </TextField>
          </Grid>

          {/* Action Buttons */}
          <Grid size={{ xs: 12 }}>
            <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
              <Button
                variant="outlined"
                onClick={handleClearFilters}
                size="small"
                aria-label="Clear Filters"
              >
                {t('positions:actions.clearFilters')}
              </Button>
              <Button
                variant="contained"
                onClick={async () => {
                  setLoading(true);
                  setError(null);
                  await fetchPositions('OPEN');
                  await fetchPositions('CLOSED');
                  setLoading(false);
                }}
                size="small"
                aria-label="Apply Filters"
              >
                {t('positions:actions.applyFilters')}
              </Button>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Tabs for Active/Closed Positions */}
      <Box
        sx={{ borderBottom: 1, borderColor: 'divider', mb: 2, width: '100%' }}
      >
        <Tabs value={tabValue} onChange={handleTabChange}>
          <Tab label={t('positions:activePositions')} />
          <Tab label={t('positions:closedPositions')} />
        </Tabs>
      </Box>

      {/* Export Button */}
      <Box
        sx={{
          mb: 2,
          display: 'flex',
          justifyContent: 'flex-end',
          width: '100%',
        }}
      >
        <Button
          variant="contained"
          startIcon={<DownloadIcon />}
          onClick={() =>
            handleExportCSV(
              tabValue === 0 ? activePositions : closedPositions,
              tabValue === 0 ? 'active_positions' : 'closed_positions'
            )
          }
          disabled={
            tabValue === 0
              ? activePositions.length === 0
              : closedPositions.length === 0
          }
        >
          {t('positions:actions.exportCSV')}
        </Button>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert
          severity="error"
          sx={{ mb: 2, width: '100%' }}
          onClose={() => setError(null)}
        >
          {t('positions:messages.errorLoadingPositions')}: {error}
        </Alert>
      )}

      {/* Loading State */}
      {loading && (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            my: 4,
            width: '100%',
          }}
        >
          <CircularProgress />
        </Box>
      )}

      {/* Active Positions Tab */}
      <TabPanel value={tabValue} index={0}>
        {!loading && (
          <DataTable<Position>
            columns={activeColumns}
            data={activePositions}
            emptyMessage={t('positions:messages.noActivePositions')}
            defaultRowsPerPage={25}
            rowsPerPageOptions={[10, 25, 50, 100]}
          />
        )}
      </TabPanel>

      {/* Closed Positions Tab */}
      <TabPanel value={tabValue} index={1}>
        {!loading && (
          <DataTable<Position>
            columns={closedColumns}
            data={closedPositions}
            emptyMessage={t('positions:messages.noClosedPositions')}
            defaultRowsPerPage={25}
            rowsPerPageOptions={[10, 25, 50, 100]}
          />
        )}
      </TabPanel>
    </Box>
  );
};

export default PositionsPage;
