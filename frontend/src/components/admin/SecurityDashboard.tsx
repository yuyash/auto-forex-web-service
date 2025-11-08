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
  Card,
  CardContent,
  IconButton,
  Tooltip,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import {
  Security as SecurityIcon,
  Block as BlockIcon,
  Lock as LockIcon,
  Warning as WarningIcon,
  LockOpen as LockOpenIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  Search as SearchIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import DataTable, { type Column } from '../common/DataTable';
import ConfirmDialog from '../common/ConfirmDialog';
import { useAuth } from '../../contexts/AuthContext';

interface SecurityEvent {
  id: number;
  timestamp: string;
  event_type: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  description: string;
  ip_address?: string;
  username?: string;
  details?: Record<string, unknown>;
}

interface BlockedIP {
  ip_address: string;
  blocked_at: string;
  reason: string;
  failed_attempts: number;
}

interface LockedAccount {
  username: string;
  email: string;
  locked_at: string;
  failed_attempts: number;
}

interface HTTPAccessPattern {
  ip_address: string;
  request_count: number;
  endpoint: string;
  last_access: string;
  status_codes: Record<string, number>;
}

interface SecurityFilters {
  eventType: string;
  severity: string;
  ipAddress: string;
  startDate: Date | null;
  endDate: Date | null;
}

interface SecurityStats {
  failed_login_count: number;
  blocked_ip_count: number;
  locked_account_count: number;
  suspicious_activity_count: number;
}

const SecurityDashboard: React.FC = () => {
  const { t } = useTranslation('admin');
  const { token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<SecurityStats>({
    failed_login_count: 0,
    blocked_ip_count: 0,
    locked_account_count: 0,
    suspicious_activity_count: 0,
  });
  const [securityEvents, setSecurityEvents] = useState<SecurityEvent[]>([]);
  const [blockedIPs, setBlockedIPs] = useState<BlockedIP[]>([]);
  const [lockedAccounts, setLockedAccounts] = useState<LockedAccount[]>([]);
  const [httpPatterns, setHttpPatterns] = useState<HTTPAccessPattern[]>([]);
  const [filters, setFilters] = useState<SecurityFilters>({
    eventType: '',
    severity: '',
    ipAddress: '',
    startDate: null,
    endDate: null,
  });
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    action: 'unblock' | 'unlock' | null;
    target: string;
  }>({
    open: false,
    action: null,
    target: '',
  });

  const fetchSecurityData = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (filters.eventType) params.append('event_type', filters.eventType);
      if (filters.severity) params.append('severity', filters.severity);
      if (filters.ipAddress) params.append('ip_address', filters.ipAddress);
      if (filters.startDate) {
        params.append('start_date', filters.startDate.toISOString());
      }
      if (filters.endDate) {
        params.append('end_date', filters.endDate.toISOString());
      }

      const [eventsRes, blockedRes, lockedRes, patternsRes, statsRes] =
        await Promise.all([
          fetch(`/api/admin/security/events?${params.toString()}`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch('/api/admin/security/blocked-ips', {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch('/api/admin/security/locked-accounts', {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch('/api/admin/security/http-patterns', {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch('/api/admin/security/stats', {
            headers: { Authorization: `Bearer ${token}` },
          }),
        ]);

      if (
        !eventsRes.ok ||
        !blockedRes.ok ||
        !lockedRes.ok ||
        !patternsRes.ok ||
        !statsRes.ok
      ) {
        throw new Error('Failed to fetch security data');
      }

      const [eventsData, blockedData, lockedData, patternsData, statsData] =
        await Promise.all([
          eventsRes.json(),
          blockedRes.json(),
          lockedRes.json(),
          patternsRes.json(),
          statsRes.json(),
        ]);

      setSecurityEvents(eventsData.results || eventsData);
      setBlockedIPs(blockedData);
      setLockedAccounts(lockedData);
      setHttpPatterns(patternsData);
      setStats(statsData);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load security data'
      );
    } finally {
      setLoading(false);
    }
  }, [token, filters]);

  useEffect(() => {
    fetchSecurityData();
  }, [fetchSecurityData]);

  const handleFilterChange = (field: keyof SecurityFilters, value: unknown) => {
    setFilters((prev) => ({ ...prev, [field]: value }));
  };

  const handleUnblockIP = async (ipAddress: string) => {
    if (!token) return;

    try {
      const response = await fetch(`/api/admin/security/unblock-ip`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ip_address: ipAddress }),
      });

      if (!response.ok) {
        throw new Error('Failed to unblock IP');
      }

      fetchSecurityData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to unblock IP');
    }
  };

  const handleUnlockAccount = async (username: string) => {
    if (!token) return;

    try {
      const response = await fetch(`/api/admin/security/unlock-account`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username }),
      });

      if (!response.ok) {
        throw new Error('Failed to unlock account');
      }

      fetchSecurityData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to unlock account');
    }
  };

  const handleConfirmAction = () => {
    if (confirmDialog.action === 'unblock') {
      handleUnblockIP(confirmDialog.target);
    } else if (confirmDialog.action === 'unlock') {
      handleUnlockAccount(confirmDialog.target);
    }
    setConfirmDialog({ open: false, action: null, target: '' });
  };

  const handleExportCSV = async () => {
    if (!token) return;

    try {
      const params = new URLSearchParams();
      if (filters.eventType) params.append('event_type', filters.eventType);
      if (filters.severity) params.append('severity', filters.severity);
      if (filters.ipAddress) params.append('ip_address', filters.ipAddress);
      if (filters.startDate) {
        params.append('start_date', filters.startDate.toISOString());
      }
      if (filters.endDate) {
        params.append('end_date', filters.endDate.toISOString());
      }
      params.append('format', 'csv');

      const response = await fetch(
        `/api/admin/security/events/export?${params.toString()}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to export security events');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `security_events_${new Date().toISOString()}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export events');
    }
  };

  const formatDateTime = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
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

  const isSuspicious = (event: SecurityEvent): boolean => {
    const suspiciousPatterns = [
      'sql injection',
      'path traversal',
      'multiple failed',
      'brute force',
      'unauthorized',
      'suspicious',
    ];
    const description = event.description.toLowerCase();
    return suspiciousPatterns.some((pattern) => description.includes(pattern));
  };

  const isHighRequestCount = (count: number): boolean => {
    return count > 100;
  };

  // Security Events Table Columns
  const eventColumns: Column<SecurityEvent & Record<string, unknown>>[] = [
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
          label={t(`events.severities.${row.severity}`, row.severity)}
          color={getSeverityColor(row.severity)}
          size="small"
          icon={isSuspicious(row) ? <WarningIcon /> : undefined}
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
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
          }}
        >
          {isSuspicious(row) && (
            <Tooltip title="Suspicious Activity">
              <WarningIcon color="error" fontSize="small" />
            </Tooltip>
          )}
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
        </Box>
      ),
    },
    {
      id: 'username',
      label: t('events.user'),
      sortable: true,
      render: (row) => row.username || '-',
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

  // Blocked IPs Table Columns
  const blockedIPColumns: Column<BlockedIP & Record<string, unknown>>[] = [
    {
      id: 'ip_address',
      label: t('events.ipAddress'),
      sortable: true,
      minWidth: 130,
    },
    {
      id: 'blocked_at',
      label: 'Blocked At',
      sortable: true,
      render: (row) => formatDateTime(row.blocked_at),
      minWidth: 180,
    },
    {
      id: 'failed_attempts',
      label: 'Failed Attempts',
      sortable: true,
      align: 'center',
      render: (row) => (
        <Chip
          label={row.failed_attempts}
          color="error"
          size="small"
          sx={{ fontWeight: 'bold' }}
        />
      ),
      minWidth: 120,
    },
    {
      id: 'reason',
      label: 'Reason',
      sortable: false,
      minWidth: 200,
    },
    {
      id: 'actions',
      label: '',
      align: 'center',
      render: (row) => (
        <Button
          variant="outlined"
          color="primary"
          size="small"
          startIcon={<LockOpenIcon />}
          onClick={(e) => {
            e.stopPropagation();
            setConfirmDialog({
              open: true,
              action: 'unblock',
              target: row.ip_address,
            });
          }}
        >
          {t('security.unblock')}
        </Button>
      ),
      minWidth: 120,
    },
  ];

  // Locked Accounts Table Columns
  const lockedAccountColumns: Column<
    LockedAccount & Record<string, unknown>
  >[] = [
    {
      id: 'username',
      label: t('users.username'),
      sortable: true,
      minWidth: 150,
    },
    {
      id: 'email',
      label: t('users.email'),
      sortable: true,
      minWidth: 200,
    },
    {
      id: 'locked_at',
      label: 'Locked At',
      sortable: true,
      render: (row) => formatDateTime(row.locked_at),
      minWidth: 180,
    },
    {
      id: 'failed_attempts',
      label: 'Failed Attempts',
      sortable: true,
      align: 'center',
      render: (row) => (
        <Chip
          label={row.failed_attempts}
          color="error"
          size="small"
          sx={{ fontWeight: 'bold' }}
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
          color="primary"
          size="small"
          startIcon={<LockOpenIcon />}
          onClick={(e) => {
            e.stopPropagation();
            setConfirmDialog({
              open: true,
              action: 'unlock',
              target: row.username,
            });
          }}
        >
          {t('security.unlock')}
        </Button>
      ),
      minWidth: 120,
    },
  ];

  // HTTP Access Patterns Table Columns
  const httpPatternColumns: Column<
    HTTPAccessPattern & Record<string, unknown>
  >[] = [
    {
      id: 'ip_address',
      label: t('events.ipAddress'),
      sortable: true,
      minWidth: 130,
      render: (row) => (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
          }}
        >
          {isHighRequestCount(row.request_count) && (
            <Tooltip title="High Request Count">
              <WarningIcon color="warning" fontSize="small" />
            </Tooltip>
          )}
          <Typography variant="body2">{row.ip_address}</Typography>
        </Box>
      ),
    },
    {
      id: 'request_count',
      label: 'Request Count',
      sortable: true,
      align: 'center',
      render: (row) => (
        <Chip
          label={row.request_count}
          color={isHighRequestCount(row.request_count) ? 'warning' : 'default'}
          size="small"
          sx={{ fontWeight: 'bold' }}
        />
      ),
      minWidth: 120,
    },
    {
      id: 'endpoint',
      label: 'Top Endpoint',
      sortable: false,
      minWidth: 200,
    },
    {
      id: 'last_access',
      label: 'Last Access',
      sortable: true,
      render: (row) => formatDateTime(row.last_access),
      minWidth: 180,
    },
    {
      id: 'status_codes',
      label: 'Status Codes',
      sortable: false,
      render: (row) => (
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
          {Object.entries(row.status_codes).map(([code, count]) => (
            <Chip
              key={code}
              label={`${code}: ${count}`}
              size="small"
              variant="outlined"
              color={
                code.startsWith('2')
                  ? 'success'
                  : code.startsWith('4') || code.startsWith('5')
                    ? 'error'
                    : 'default'
              }
            />
          ))}
        </Box>
      ),
      minWidth: 250,
    },
  ];

  const eventTypes = [
    '',
    'failed_login',
    'account_locked',
    'ip_blocked',
    'suspicious_access',
    'unauthorized_attempt',
  ];
  const severities = ['', 'info', 'warning', 'error', 'critical'];

  if (loading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="400px"
      >
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 3,
        }}
      >
        <Box>
          <Typography variant="h4" gutterBottom>
            <SecurityIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
            {t('security.title')}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Monitor security events, blocked IPs, and suspicious activity
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <IconButton onClick={fetchSecurityData} color="primary">
            <RefreshIcon />
          </IconButton>
          <Button
            variant="contained"
            startIcon={<DownloadIcon />}
            onClick={handleExportCSV}
            disabled={securityEvents.length === 0}
          >
            Export CSV
          </Button>
        </Box>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Statistics Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card
            sx={{
              bgcolor: 'error.light',
              color: 'error.contrastText',
            }}
          >
            <CardContent>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <Box>
                  <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
                    {stats.failed_login_count}
                  </Typography>
                  <Typography variant="body2">
                    {t('security.failedLogins')}
                  </Typography>
                </Box>
                <WarningIcon sx={{ fontSize: 48, opacity: 0.7 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card
            sx={{
              bgcolor: 'warning.light',
              color: 'warning.contrastText',
            }}
          >
            <CardContent>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <Box>
                  <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
                    {stats.blocked_ip_count}
                  </Typography>
                  <Typography variant="body2">
                    {t('security.blockedIPs')}
                  </Typography>
                </Box>
                <BlockIcon sx={{ fontSize: 48, opacity: 0.7 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card
            sx={{
              bgcolor: 'info.light',
              color: 'info.contrastText',
            }}
          >
            <CardContent>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <Box>
                  <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
                    {stats.locked_account_count}
                  </Typography>
                  <Typography variant="body2">
                    {t('security.lockedAccounts')}
                  </Typography>
                </Box>
                <LockIcon sx={{ fontSize: 48, opacity: 0.7 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card
            sx={{
              bgcolor: 'secondary.light',
              color: 'secondary.contrastText',
            }}
          >
            <CardContent>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <Box>
                  <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
                    {stats.suspicious_activity_count}
                  </Typography>
                  <Typography variant="body2">
                    {t('security.suspiciousActivity')}
                  </Typography>
                </Box>
                <SecurityIcon sx={{ fontSize: 48, opacity: 0.7 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Security Events Section */}
      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Security Events
        </Typography>

        {/* Filters */}
        <Box sx={{ mb: 3 }}>
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <TextField
                select
                fullWidth
                label="Event Type"
                value={filters.eventType}
                onChange={(e) =>
                  handleFilterChange('eventType', e.target.value)
                }
                size="small"
              >
                {eventTypes.map((type) => (
                  <MenuItem key={type} value={type}>
                    {type || 'All Event Types'}
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
                label={t('events.ipAddress')}
                value={filters.ipAddress}
                onChange={(e) =>
                  handleFilterChange('ipAddress', e.target.value)
                }
                size="small"
                placeholder="Filter by IP address"
              />
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <Button
                fullWidth
                variant="outlined"
                onClick={fetchSecurityData}
                startIcon={<SearchIcon />}
                sx={{ height: '40px' }}
              >
                Apply Filters
              </Button>
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <LocalizationProvider dateAdapter={AdapterDateFns}>
                <DatePicker
                  label="Start Date"
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
                  label="End Date"
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
                variant="text"
                onClick={() => {
                  setFilters({
                    eventType: '',
                    severity: '',
                    ipAddress: '',
                    startDate: null,
                    endDate: null,
                  });
                }}
                sx={{ height: '40px' }}
              >
                Clear Filters
              </Button>
            </Grid>
          </Grid>
        </Box>

        {securityEvents.length === 0 ? (
          <Box
            sx={{
              py: 4,
              textAlign: 'center',
            }}
          >
            <Typography variant="body2" color="text.secondary">
              No security events found
            </Typography>
          </Box>
        ) : (
          <DataTable
            columns={eventColumns}
            data={securityEvents as (SecurityEvent & Record<string, unknown>)[]}
            emptyMessage="No security events"
            defaultRowsPerPage={10}
            rowsPerPageOptions={[10, 25, 50]}
            stickyHeader={false}
          />
        )}
      </Paper>

      {/* Blocked IPs Section */}
      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          {t('security.blockedIPs')}
        </Typography>

        {blockedIPs.length === 0 ? (
          <Box
            sx={{
              py: 4,
              textAlign: 'center',
            }}
          >
            <Typography variant="body2" color="text.secondary">
              No blocked IP addresses
            </Typography>
          </Box>
        ) : (
          <DataTable
            columns={blockedIPColumns}
            data={blockedIPs as (BlockedIP & Record<string, unknown>)[]}
            emptyMessage="No blocked IPs"
            defaultRowsPerPage={5}
            rowsPerPageOptions={[5, 10, 25]}
            stickyHeader={false}
          />
        )}
      </Paper>

      {/* Locked Accounts Section */}
      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          {t('security.lockedAccounts')}
        </Typography>

        {lockedAccounts.length === 0 ? (
          <Box
            sx={{
              py: 4,
              textAlign: 'center',
            }}
          >
            <Typography variant="body2" color="text.secondary">
              No locked accounts
            </Typography>
          </Box>
        ) : (
          <DataTable
            columns={lockedAccountColumns}
            data={lockedAccounts as (LockedAccount & Record<string, unknown>)[]}
            emptyMessage="No locked accounts"
            defaultRowsPerPage={5}
            rowsPerPageOptions={[5, 10, 25]}
            stickyHeader={false}
          />
        )}
      </Paper>

      {/* HTTP Access Patterns Section */}
      <Paper elevation={2} sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          HTTP Access Patterns
        </Typography>

        {httpPatterns.length === 0 ? (
          <Box
            sx={{
              py: 4,
              textAlign: 'center',
            }}
          >
            <Typography variant="body2" color="text.secondary">
              No HTTP access patterns
            </Typography>
          </Box>
        ) : (
          <DataTable
            columns={httpPatternColumns}
            data={
              httpPatterns as (HTTPAccessPattern & Record<string, unknown>)[]
            }
            emptyMessage="No HTTP patterns"
            defaultRowsPerPage={10}
            rowsPerPageOptions={[10, 25, 50]}
            stickyHeader={false}
          />
        )}
      </Paper>

      {/* Confirm Dialog */}
      <ConfirmDialog
        open={confirmDialog.open}
        title={
          confirmDialog.action === 'unblock'
            ? 'Confirm Unblock IP'
            : 'Confirm Unlock Account'
        }
        message={
          confirmDialog.action === 'unblock'
            ? `Are you sure you want to unblock IP address ${confirmDialog.target}?`
            : `Are you sure you want to unlock account ${confirmDialog.target}?`
        }
        onConfirm={handleConfirmAction}
        onCancel={() =>
          setConfirmDialog({ open: false, action: null, target: '' })
        }
        confirmText={
          confirmDialog.action === 'unblock'
            ? t('security.unblock')
            : t('security.unlock')
        }
        cancelText={t('common.cancel')}
        confirmColor="primary"
      />
    </Box>
  );
};

export default SecurityDashboard;
