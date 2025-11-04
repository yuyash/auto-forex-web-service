import React, { useState } from 'react';
import { Paper, Typography, Box, Button, Chip } from '@mui/material';
import { PersonOff as PersonOffIcon } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import DataTable, { type Column } from '../common/DataTable';
import ConfirmDialog from '../common/ConfirmDialog';
import type { UserSession } from '../../types/admin';

interface UserSessionListProps {
  sessions: UserSession[];
  onKickOff: (userId: number) => void;
}

const UserSessionList: React.FC<UserSessionListProps> = ({
  sessions,
  onKickOff,
}) => {
  const { t } = useTranslation('admin');
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    userId: number | null;
    username: string;
  }>({
    open: false,
    userId: null,
    username: '',
  });

  const handleKickOffClick = (userId: number, username: string) => {
    setConfirmDialog({
      open: true,
      userId,
      username,
    });
  };

  const handleConfirmKickOff = () => {
    if (confirmDialog.userId) {
      onKickOff(confirmDialog.userId);
    }
    setConfirmDialog({ open: false, userId: null, username: '' });
  };

  const handleCancelKickOff = () => {
    setConfirmDialog({ open: false, userId: null, username: '' });
  };

  const formatDateTime = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const getTimeSince = (dateString: string): string => {
    const now = new Date();
    const date = new Date(dateString);
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return t('users.justNow');
    if (diffMins < 60) return t('users.minutesAgo', { count: diffMins });
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return t('users.hoursAgo', { count: diffHours });
    const diffDays = Math.floor(diffHours / 24);
    return t('users.daysAgo', { count: diffDays });
  };

  const columns: Column<UserSession & Record<string, unknown>>[] = [
    {
      id: 'username',
      label: t('users.username'),
      sortable: true,
      filterable: true,
      minWidth: 150,
    },
    {
      id: 'email',
      label: t('users.email'),
      sortable: true,
      filterable: true,
      minWidth: 200,
    },
    {
      id: 'ip_address',
      label: t('users.ipAddress'),
      sortable: true,
      filterable: true,
      minWidth: 130,
    },
    {
      id: 'login_time',
      label: t('users.loginTime'),
      sortable: true,
      render: (row) => formatDateTime(row.login_time),
      minWidth: 180,
    },
    {
      id: 'last_activity',
      label: t('users.lastActivity'),
      sortable: true,
      render: (row) => (
        <Box>
          <Typography variant="body2">
            {formatDateTime(row.last_activity)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {getTimeSince(row.last_activity)}
          </Typography>
        </Box>
      ),
      minWidth: 180,
    },
    {
      id: 'session_count',
      label: t('users.sessions'),
      sortable: true,
      align: 'center',
      render: (row) => (
        <Chip
          label={row.session_count}
          color="primary"
          size="small"
          sx={{ fontWeight: 'bold' }}
        />
      ),
      minWidth: 100,
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
          startIcon={<PersonOffIcon />}
          onClick={(e) => {
            e.stopPropagation();
            handleKickOffClick(row.id, row.username);
          }}
        >
          {t('users.kickOff')}
        </Button>
      ),
      minWidth: 150,
    },
  ];

  return (
    <>
      <Paper elevation={2} sx={{ p: 3, height: '100%' }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mb: 2,
          }}
        >
          <Typography variant="h6">{t('users.title')}</Typography>
          <Chip
            label={sessions.length}
            color="primary"
            size="small"
            sx={{ fontWeight: 'bold' }}
          />
        </Box>

        {sessions.length === 0 ? (
          <Box
            sx={{
              py: 4,
              textAlign: 'center',
            }}
          >
            <Typography variant="body2" color="text.secondary">
              {t('users.noUsers')}
            </Typography>
          </Box>
        ) : (
          <DataTable
            columns={columns}
            data={sessions as (UserSession & Record<string, unknown>)[]}
            emptyMessage={t('users.noUsers')}
            defaultRowsPerPage={5}
            rowsPerPageOptions={[5, 10, 25]}
            stickyHeader={false}
          />
        )}
      </Paper>

      <ConfirmDialog
        open={confirmDialog.open}
        title={t('users.confirmKickOffTitle')}
        message={t('users.confirmKickOffMessage', {
          username: confirmDialog.username,
        })}
        onConfirm={handleConfirmKickOff}
        onCancel={handleCancelKickOff}
        confirmText={t('users.kickOff')}
        cancelText={t('common.cancel')}
        confirmColor="warning"
      />
    </>
  );
};

export default UserSessionList;
