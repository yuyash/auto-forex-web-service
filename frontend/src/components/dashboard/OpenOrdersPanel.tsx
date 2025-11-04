import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  Collapse,
  Button,
  Chip,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import DataTable, { type Column } from '../common/DataTable';
import type { Order } from '../../types/chart';

interface OpenOrdersPanelProps {
  orders: Order[];
  onCancelOrder: (orderId: string) => void;
  loading?: boolean;
}

const OpenOrdersPanel: React.FC<OpenOrdersPanelProps> = ({
  orders,
  onCancelOrder,
  loading = false,
}) => {
  const { t } = useTranslation('dashboard');
  const [expanded, setExpanded] = useState(true);

  const handleToggleExpand = () => {
    setExpanded((prev) => !prev);
  };

  const getOrderTypeLabel = (orderType: string): string => {
    return t(`orders.${orderType}`, orderType);
  };

  const getStatusColor = (
    status: string
  ):
    | 'default'
    | 'primary'
    | 'secondary'
    | 'error'
    | 'info'
    | 'success'
    | 'warning' => {
    const statusLower = status.toLowerCase();
    if (statusLower.includes('pending') || statusLower.includes('open')) {
      return 'info';
    }
    if (statusLower.includes('filled') || statusLower.includes('executed')) {
      return 'success';
    }
    if (statusLower.includes('cancelled') || statusLower.includes('rejected')) {
      return 'error';
    }
    return 'default';
  };

  const columns: Column<Order & Record<string, unknown>>[] = [
    {
      id: 'order_id',
      label: t('orders.orderId'),
      sortable: true,
      filterable: true,
      minWidth: 120,
    },
    {
      id: 'order_type',
      label: t('orders.type'),
      sortable: true,
      filterable: true,
      render: (row) => getOrderTypeLabel(row.order_type),
      minWidth: 100,
    },
    {
      id: 'instrument',
      label: t('orders.instrument'),
      sortable: true,
      filterable: true,
      minWidth: 100,
    },
    {
      id: 'price',
      label: t('orders.price'),
      sortable: true,
      align: 'right',
      render: (row) => (row.price ? row.price.toFixed(5) : '-'),
      minWidth: 100,
    },
    {
      id: 'units',
      label: t('orders.units'),
      sortable: true,
      align: 'right',
      render: (row) => row.units.toLocaleString(),
      minWidth: 100,
    },
    {
      id: 'status',
      label: t('orders.status'),
      sortable: true,
      filterable: true,
      render: (row) => (
        <Chip
          label={row.status}
          color={getStatusColor(row.status)}
          size="small"
        />
      ),
      minWidth: 120,
    },
    {
      id: 'actions',
      label: '',
      align: 'center',
      render: (row) => (
        <Button
          variant="outlined"
          color="error"
          size="small"
          startIcon={<CancelIcon />}
          onClick={(e) => {
            e.stopPropagation();
            onCancelOrder(row.order_id);
          }}
          disabled={loading}
        >
          {t('orders.cancelOrder')}
        </Button>
      ),
      minWidth: 150,
    },
  ];

  return (
    <Paper elevation={2} sx={{ mb: 2 }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: 2,
          borderBottom: expanded ? 1 : 0,
          borderColor: 'divider',
          cursor: 'pointer',
          '&:hover': {
            bgcolor: 'action.hover',
          },
        }}
        onClick={handleToggleExpand}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="h6">{t('orders.title')}</Typography>
          <Chip
            label={orders.length}
            color="primary"
            size="small"
            sx={{ fontWeight: 'bold' }}
          />
        </Box>
        <IconButton size="small" aria-label="toggle panel">
          {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconButton>
      </Box>
      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <Box sx={{ p: 2 }}>
          {orders.length === 0 ? (
            <Box
              sx={{
                py: 4,
                textAlign: 'center',
              }}
            >
              <Typography variant="body2" color="text.secondary">
                {t('orders.noOrders')}
              </Typography>
            </Box>
          ) : (
            <DataTable
              columns={columns}
              data={orders as (Order & Record<string, unknown>)[]}
              emptyMessage={t('orders.noOrders')}
              defaultRowsPerPage={5}
              rowsPerPageOptions={[5, 10, 25]}
              stickyHeader={false}
            />
          )}
        </Box>
      </Collapse>
    </Paper>
  );
};

export default OpenOrdersPanel;
