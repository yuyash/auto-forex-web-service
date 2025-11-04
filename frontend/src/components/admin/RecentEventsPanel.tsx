import React from 'react';
import { Paper, Typography, Box, Chip } from '@mui/material';
import {
  Info as InfoIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  BugReport as BugReportIcon,
  CrisisAlert as CrisisAlertIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import DataTable, { type Column } from '../common/DataTable';
import type { AdminEvent } from '../../types/admin';

interface RecentEventsPanelProps {
  events: AdminEvent[];
}

const RecentEventsPanel: React.FC<RecentEventsPanelProps> = ({ events }) => {
  const { t } = useTranslation('admin');

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

  const getTimeSince = (dateString: string): string => {
    const now = new Date();
    const date = new Date(dateString);
    const diffMs = now.getTime() - date.getTime();
    const diffSecs = Math.floor(diffMs / 1000);

    if (diffSecs < 60) return t('events.secondsAgo', { count: diffSecs });
    const diffMins = Math.floor(diffSecs / 60);
    if (diffMins < 60) return t('events.minutesAgo', { count: diffMins });
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return t('events.hoursAgo', { count: diffHours });
    const diffDays = Math.floor(diffHours / 24);
    return t('events.daysAgo', { count: diffDays });
  };

  const columns: Column<AdminEvent & Record<string, unknown>>[] = [
    {
      id: 'timestamp',
      label: t('events.timestamp'),
      sortable: true,
      render: (row) => (
        <Box>
          <Typography variant="body2">
            {formatDateTime(row.timestamp)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {getTimeSince(row.timestamp)}
          </Typography>
        </Box>
      ),
      minWidth: 180,
    },
    {
      id: 'severity',
      label: t('events.severity'),
      sortable: true,
      filterable: true,
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
      filterable: true,
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
      filterable: true,
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
      filterable: true,
      render: (row) => row.user || '-',
      minWidth: 120,
    },
    {
      id: 'ip_address',
      label: t('events.ipAddress'),
      sortable: true,
      filterable: true,
      render: (row) => row.ip_address || '-',
      minWidth: 130,
    },
  ];

  return (
    <Paper elevation={2} sx={{ p: 3 }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 2,
        }}
      >
        <Typography variant="h6">{t('events.title')}</Typography>
        <Chip
          label={events.length}
          color="primary"
          size="small"
          sx={{ fontWeight: 'bold' }}
        />
      </Box>

      {events.length === 0 ? (
        <Box
          sx={{
            py: 4,
            textAlign: 'center',
          }}
        >
          <Typography variant="body2" color="text.secondary">
            {t('events.noEvents')}
          </Typography>
        </Box>
      ) : (
        <DataTable
          columns={columns}
          data={events as (AdminEvent & Record<string, unknown>)[]}
          emptyMessage={t('events.noEvents')}
          defaultRowsPerPage={10}
          rowsPerPageOptions={[10, 25, 50]}
          stickyHeader={false}
        />
      )}
    </Paper>
  );
};

export default RecentEventsPanel;
