import React, { useState, useEffect } from 'react';
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
  Close as CloseIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import DataTable, { type Column } from '../common/DataTable';
import type { Position } from '../../types/chart';

interface OpenPositionsPanelProps {
  positions: Position[];
  onClosePosition: (positionId: string) => void;
  loading?: boolean;
}

const OpenPositionsPanel: React.FC<OpenPositionsPanelProps> = ({
  positions,
  onClosePosition,
  loading = false,
}) => {
  const { t } = useTranslation('dashboard');
  const [expanded, setExpanded] = useState(true);
  const [displayPositions, setDisplayPositions] = useState(positions);

  // Update positions in real-time when props change
  useEffect(() => {
    setDisplayPositions(positions);
  }, [positions]);

  const handleToggleExpand = () => {
    setExpanded((prev) => !prev);
  };

  const getDirectionLabel = (direction: string): string => {
    return t(`positions.${direction}`, direction);
  };

  const getDirectionColor = (
    direction: string
  ):
    | 'default'
    | 'primary'
    | 'secondary'
    | 'error'
    | 'info'
    | 'success'
    | 'warning' => {
    return direction === 'long' ? 'success' : 'error';
  };

  const getPnLColor = (pnl: number): string => {
    if (pnl > 0) return 'success.main';
    if (pnl < 0) return 'error.main';
    return 'text.secondary';
  };

  const formatPnL = (pnl: number): string => {
    const sign = pnl >= 0 ? '+' : '';
    return `${sign}${pnl.toFixed(2)}`;
  };

  const columns: Column<Position & Record<string, unknown>>[] = [
    {
      id: 'position_id',
      label: t('positions.positionId', 'Position ID'),
      sortable: true,
      filterable: true,
      minWidth: 120,
    },
    {
      id: 'instrument',
      label: t('positions.instrument'),
      sortable: true,
      filterable: true,
      minWidth: 100,
    },
    {
      id: 'direction',
      label: t('positions.direction'),
      sortable: true,
      filterable: true,
      render: (row) => (
        <Chip
          label={getDirectionLabel(row.direction)}
          color={getDirectionColor(row.direction)}
          size="small"
        />
      ),
      minWidth: 100,
    },
    {
      id: 'units',
      label: t('positions.units'),
      sortable: true,
      align: 'right',
      render: (row) => row.units.toLocaleString(),
      minWidth: 100,
    },
    {
      id: 'entry_price',
      label: t('positions.entryPrice'),
      sortable: true,
      align: 'right',
      render: (row) => row.entry_price.toFixed(5),
      minWidth: 120,
    },
    {
      id: 'current_price',
      label: t('positions.currentPrice'),
      sortable: true,
      align: 'right',
      render: (row) => row.current_price.toFixed(5),
      minWidth: 120,
    },
    {
      id: 'unrealized_pnl',
      label: t('positions.unrealizedPnL'),
      sortable: true,
      align: 'right',
      render: (row) => (
        <Typography
          variant="body2"
          sx={{
            color: getPnLColor(row.unrealized_pnl),
            fontWeight: 'bold',
          }}
        >
          {formatPnL(row.unrealized_pnl)}
        </Typography>
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
          startIcon={<CloseIcon />}
          onClick={(e) => {
            e.stopPropagation();
            onClosePosition(row.position_id);
          }}
          disabled={loading}
        >
          {t('positions.closePosition')}
        </Button>
      ),
      minWidth: 150,
    },
  ];

  // Calculate total unrealized P&L
  const totalPnL = displayPositions.reduce(
    (sum, pos) => sum + pos.unrealized_pnl,
    0
  );

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
          <Typography variant="h6">{t('positions.title')}</Typography>
          <Chip
            label={displayPositions.length}
            color="primary"
            size="small"
            sx={{ fontWeight: 'bold' }}
          />
          {displayPositions.length > 0 && (
            <Chip
              label={formatPnL(totalPnL)}
              color={totalPnL >= 0 ? 'success' : 'error'}
              size="small"
              sx={{ fontWeight: 'bold' }}
            />
          )}
        </Box>
        <IconButton size="small" aria-label="toggle panel">
          {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconButton>
      </Box>
      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <Box sx={{ p: 2 }}>
          {displayPositions.length === 0 ? (
            <Box
              sx={{
                py: 4,
                textAlign: 'center',
              }}
            >
              <Typography variant="body2" color="text.secondary">
                {t('positions.noPositions')}
              </Typography>
            </Box>
          ) : (
            <DataTable
              columns={columns}
              data={displayPositions as (Position & Record<string, unknown>)[]}
              emptyMessage={t('positions.noPositions')}
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

export default OpenPositionsPanel;
