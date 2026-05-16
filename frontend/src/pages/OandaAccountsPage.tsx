import { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  CardActions,
  Typography,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  FormControlLabel,
  InputLabel,
  Select,
  MenuItem,
  Pagination,
  InputAdornment,
  CircularProgress,
  Alert,
  Tooltip,
  Switch,
  type SelectChangeEvent,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Visibility,
  VisibilityOff,
  Refresh as RefreshIcon,
  Search as SearchIcon,
  FilterAltOff as ClearFiltersIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { Link } from 'react-router-dom';
import { Breadcrumbs, PageContainer } from '../components/common';
import { useToast } from '../components/common/useToast';
import ConfirmDialog from '../components/common/ConfirmDialog';
import type { Account, AccountUpsertData } from '../types/strategy';
import {
  useCreateAccount,
  useDeleteAccount,
  useRefreshAccountSnapshot,
  useUpdateAccount,
} from '../hooks/useAccountMutations';
import {
  isAccountSnapshotRefreshActive,
  useAccounts,
  useAccountPage,
  useAccountSnapshotRefreshStatus,
} from '../hooks/useAccounts';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
import { logger } from '../utils/logger';
import {
  formatMoneyAmount,
  normalizeCurrencyCode,
  type NumberFormatSeparators,
} from '../utils/numberFormat';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import { useNumberFormatter } from '../hooks/useNumberFormatter';
import type { AccountSnapshotState } from '../services/api/accounts';
import type { AccountSnapshotRefreshStatus } from '../types/strategy';
import { DEFAULT_ACCOUNT_CURRENCY } from '../constants/currencies';

interface AccountFormData {
  account_id: string;
  api_token: string;
  api_type: 'practice' | 'live';
  live_max_exposure_guard_enabled: boolean;
  live_max_estimated_exposure_units: string;
  live_max_initial_order_guard_enabled: boolean;
  live_max_initial_order_units: string;
  live_max_order_guard_enabled: boolean;
  live_max_order_units: string;
  live_tick_latency_metric_interval_seconds: string;
}

const DEFAULT_MAX_GROSS_UNITS = '200000';
const DEFAULT_MAX_INITIAL_ORDER_UNITS = '10000';
const DEFAULT_MAX_ORDER_UNITS = '10000';
const DEFAULT_TICK_LATENCY_METRIC_INTERVAL_SECONDS = '60';

const resolveCurrencyCode = (currency?: string | null) => {
  return normalizeCurrencyCode(currency, DEFAULT_ACCOUNT_CURRENCY);
};

const formatBalance = (
  balance: string | number | null | undefined,
  currency?: string,
  separators?: NumberFormatSeparators,
  signed = false
) => {
  if (balance == null) return '—';
  const numericBalance =
    typeof balance === 'string' ? Number(balance) : balance;
  if (Number.isNaN(numericBalance)) return '—';
  return formatMoneyAmount(
    numericBalance,
    resolveCurrencyCode(currency),
    {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
      useCurrencySymbol: false,
      signed,
    },
    separators
  );
};

interface SnapshotRefreshTaskState {
  taskId: string;
  status: AccountSnapshotRefreshStatus;
}

type SnapshotStateFilterValue = 'all' | AccountSnapshotState;
type SnapshotRefreshStatusFilterValue = 'all' | AccountSnapshotRefreshStatus;

const SNAPSHOT_STATE_FILTER_OPTIONS: readonly AccountSnapshotState[] = [
  'failed',
  'stale',
  'healthy',
];

const SNAPSHOT_REFRESH_STATUS_FILTER_OPTIONS: readonly AccountSnapshotRefreshStatus[] =
  ['idle', 'queued', 'running', 'completed', 'failed'];

const snapshotRefreshStatusLabel = (
  t: TFunction,
  status: AccountSnapshotRefreshStatus
) => {
  if (status === 'queued') {
    return t('settings:accounts.snapshotRefreshQueued', 'Refresh queued');
  }
  if (status === 'running') {
    return t('settings:accounts.snapshotRefreshRunning', 'Refreshing');
  }
  if (status === 'completed') {
    return t('settings:accounts.snapshotRefreshCompleted', 'Refresh complete');
  }
  if (status === 'failed') {
    return t('settings:accounts.snapshotRefreshFailed', 'Refresh failed');
  }
  return t('settings:accounts.snapshotRefreshIdle', 'Refresh idle');
};

const snapshotStateLabel = (t: TFunction, state: AccountSnapshotState) => {
  if (state === 'failed') {
    return t('settings:accounts.snapshotStateFailed', 'Failed');
  }
  if (state === 'stale') {
    return t('settings:accounts.snapshotStateStale', 'Stale');
  }
  return t('settings:accounts.snapshotStateHealthy', 'Healthy');
};

function AccountCard({
  account,
  onEdit,
  onDelete,
  onRefreshSnapshot,
  onRefreshSnapshotSettled,
  isRefreshingSnapshot,
  refreshTask,
}: {
  account: Account;
  onEdit: (a: Account) => void;
  onDelete: (a: Account) => void;
  onRefreshSnapshot: (a: Account) => void;
  onRefreshSnapshotSettled: (accountId: number) => void;
  isRefreshingSnapshot: boolean;
  refreshTask?: SnapshotRefreshTaskState;
}) {
  const { t } = useTranslation(['settings', 'common']);
  const { formatNumber, separators } = useNumberFormatter();
  const a = account;
  const activeAccountTaskId = isAccountSnapshotRefreshActive(
    a.snapshot_refresh_status
  )
    ? a.snapshot_refresh_task_id
    : undefined;
  const trackedTaskId = refreshTask?.taskId ?? activeAccountTaskId;
  const refreshStatus = useAccountSnapshotRefreshStatus(a.id, trackedTaskId, {
    enabled: Boolean(trackedTaskId),
  });
  const trackedStatus =
    refreshStatus.data?.status ??
    refreshTask?.status ??
    (trackedTaskId ? a.snapshot_refresh_status : undefined);
  const isSnapshotRefreshInFlight =
    isRefreshingSnapshot || isAccountSnapshotRefreshActive(trackedStatus);

  useEffect(() => {
    const status = refreshStatus.data?.status;
    if (status && !isAccountSnapshotRefreshActive(status)) {
      onRefreshSnapshotSettled(a.id);
    }
  }, [a.id, onRefreshSnapshotSettled, refreshStatus.data?.status]);

  return (
    <Card>
      <CardActionArea
        component={Link}
        to={`/oanda-accounts/${a.id}`}
        aria-label={`View account ${a.account_id}`}
      >
        <CardContent>
          <Box
            display="flex"
            justifyContent="space-between"
            alignItems="flex-start"
            mb={2}
          >
            <Box display="flex" alignItems="center" gap={1}>
              <Typography variant="h6" component="div" noWrap>
                {a.account_id}
              </Typography>
            </Box>
            <Chip
              label={
                a.api_type === 'practice'
                  ? t('settings:accounts.practice')
                  : t('settings:accounts.live')
              }
              color={a.api_type === 'practice' ? 'default' : 'warning'}
            />
          </Box>
          <Box mb={1}>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.balance')}
            </Typography>
            <Typography variant="h6">
              {formatBalance(a.balance, a.currency, separators)}
            </Typography>
          </Box>
          <Box mb={1}>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.marginUsed')}
            </Typography>
            <Typography variant="body1">
              {formatBalance(a.margin_used, a.currency, separators)}
            </Typography>
          </Box>
          <Box mb={1}>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.marginAvailable')}
            </Typography>
            <Typography variant="body1">
              {formatBalance(a.margin_available, a.currency, separators)}
            </Typography>
          </Box>
          <Box mb={1}>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.unrealizedPnL')}
            </Typography>
            <Typography
              variant="body1"
              sx={{
                color:
                  parseFloat(a.unrealized_pnl) >= 0
                    ? 'success.main'
                    : 'error.main',
                fontWeight: 500,
              }}
            >
              {formatBalance(a.unrealized_pnl, a.currency, separators, true)}
            </Typography>
          </Box>
          <Box mb={1}>
            <Typography variant="body2" color="text.secondary">
              {t('settings:accounts.currency')}
            </Typography>
            <Typography variant="body1">{a.currency}</Typography>
          </Box>
          <Box display="flex" gap={1} flexWrap="wrap">
            <Chip
              label={
                a.is_active
                  ? t('common:labels.active')
                  : t('common:labels.inactive')
              }
              color={a.is_active ? 'success' : 'default'}
            />
            {a.is_default && (
              <Chip
                label={t('common:labels.default')}
                color="primary"
                variant="outlined"
              />
            )}
            {isAccountSnapshotRefreshActive(trackedStatus) && (
              <Chip
                label={snapshotRefreshStatusLabel(t, trackedStatus)}
                color="info"
                variant="outlined"
              />
            )}
            {a.snapshot_stale && (
              <Chip
                label={t('settings:accounts.snapshotStale', 'Snapshot stale')}
                color="warning"
                variant="outlined"
              />
            )}
            {a.snapshot_refresh_error && (
              <Chip
                label={t(
                  'settings:accounts.snapshotRefreshFailed',
                  'Refresh failed'
                )}
                color="error"
                variant="outlined"
              />
            )}
            {a.live_max_exposure_guard_enabled && (
              <Chip
                label={t('settings:accounts.maxGrossUnitsChip', {
                  defaultValue: 'Max Gross {{units}}',
                  units: formatNumber(
                    a.live_max_estimated_exposure_units ?? 0,
                    {
                      maximumFractionDigits: 0,
                    }
                  ),
                })}
                color="secondary"
                variant="outlined"
              />
            )}
            {a.live_max_initial_order_guard_enabled && (
              <Chip
                label={t('settings:accounts.maxInitialOrderUnitsChip', {
                  defaultValue: 'Max Initial {{units}}',
                  units: formatNumber(a.live_max_initial_order_units ?? 0, {
                    maximumFractionDigits: 0,
                  }),
                })}
                color="secondary"
                variant="outlined"
              />
            )}
            {a.live_max_order_guard_enabled && (
              <Chip
                label={t('settings:accounts.maxOrderUnitsChip', {
                  defaultValue: 'Max Order {{units}}',
                  units: formatNumber(a.live_max_order_units ?? 0, {
                    maximumFractionDigits: 0,
                  }),
                })}
                color="secondary"
                variant="outlined"
              />
            )}
            {(a.live_tick_latency_metric_interval_seconds ?? 60) > 0 && (
              <Chip
                label={t('settings:accounts.tickLatencyMetricIntervalChip', {
                  defaultValue: 'Tick latency {{seconds}}s',
                  seconds: formatNumber(
                    a.live_tick_latency_metric_interval_seconds ?? 60,
                    {
                      maximumFractionDigits: 0,
                    }
                  ),
                })}
                color="info"
                variant="outlined"
              />
            )}
          </Box>
        </CardContent>
      </CardActionArea>
      <CardActions>
        <Tooltip
          title={
            isSnapshotRefreshInFlight
              ? snapshotRefreshStatusLabel(t, trackedStatus ?? 'queued')
              : a.is_active
                ? t('settings:accounts.refreshSnapshot', 'Refresh snapshot')
                : t(
                    'settings:accounts.inactiveRefreshDisabled',
                    'Inactive accounts cannot be refreshed'
                  )
          }
        >
          <span>
            <IconButton
              color="primary"
              onClick={(e) => {
                e.stopPropagation();
                onRefreshSnapshot(a);
              }}
              disabled={!a.is_active || isSnapshotRefreshInFlight}
              aria-label={t(
                'settings:accounts.refreshSnapshot',
                'Refresh snapshot'
              )}
            >
              {isSnapshotRefreshInFlight ? (
                <CircularProgress size={20} />
              ) : (
                <RefreshIcon />
              )}
            </IconButton>
          </span>
        </Tooltip>
        <IconButton
          color="primary"
          onClick={(e) => {
            e.stopPropagation();
            onEdit(a);
          }}
          aria-label={t('settings:accounts.editAccount')}
        >
          <EditIcon />
        </IconButton>
        <IconButton
          color="error"
          onClick={(e) => {
            e.stopPropagation();
            onDelete(a);
          }}
          aria-label={t('settings:accounts.deleteAccount')}
        >
          <DeleteIcon />
        </IconButton>
      </CardActions>
    </Card>
  );
}

export default function OandaAccountsPage() {
  const { t } = useTranslation(['settings', 'common', 'trading']);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('-created_at');
  const [snapshotStateFilter, setSnapshotStateFilter] =
    useState<SnapshotStateFilterValue>('all');
  const [snapshotRefreshStatusFilter, setSnapshotRefreshStatusFilter] =
    useState<SnapshotRefreshStatusFilterValue>('all');
  const debouncedSearchQuery = useDebouncedValue(searchQuery, 300);
  const hasActiveAccountFilters =
    searchQuery.trim().length > 0 ||
    snapshotStateFilter !== 'all' ||
    snapshotRefreshStatusFilter !== 'all';
  const {
    data: accountsPage,
    isLoading: loading,
    error: accountsError,
  } = useAccountPage({
    page,
    page_size: pageSize,
    search: debouncedSearchQuery || undefined,
    ordering: sortBy,
    snapshot_state:
      snapshotStateFilter === 'all' ? undefined : snapshotStateFilter,
    snapshot_refresh_status:
      snapshotRefreshStatusFilter === 'all'
        ? undefined
        : snapshotRefreshStatusFilter,
  });
  const { data: allAccountsForDefault } = useAccounts({ page_size: 200 });
  const accounts = accountsPage?.results ?? [];
  const totalPages = accountsPage
    ? Math.ceil(accountsPage.count / pageSize)
    : 0;
  const hasAnyAccount =
    (allAccountsForDefault?.length ?? accountsPage?.count ?? 0) > 0;
  const createAccount = useCreateAccount();
  const updateAccount = useUpdateAccount();
  const deleteAccount = useDeleteAccount();
  const refreshSnapshot = useRefreshAccountSnapshot();
  const [refreshingSnapshotIds, setRefreshingSnapshotIds] = useState<
    ReadonlySet<number>
  >(new Set());
  const [refreshTasksByAccount, setRefreshTasksByAccount] = useState<
    Record<number, SnapshotRefreshTaskState>
  >({});
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [accountToDelete, setAccountToDelete] = useState<Account | null>(null);
  const [showApiToken, setShowApiToken] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState<AccountFormData>({
    account_id: '',
    api_token: '',
    api_type: 'practice',
    live_max_exposure_guard_enabled: false,
    live_max_estimated_exposure_units: DEFAULT_MAX_GROSS_UNITS,
    live_max_initial_order_guard_enabled: true,
    live_max_initial_order_units: DEFAULT_MAX_INITIAL_ORDER_UNITS,
    live_max_order_guard_enabled: false,
    live_max_order_units: DEFAULT_MAX_ORDER_UNITS,
    live_tick_latency_metric_interval_seconds:
      DEFAULT_TICK_LATENCY_METRIC_INTERVAL_SECONDS,
  });
  const [isDefault, setIsDefault] = useState(false);
  const [formErrors, setFormErrors] = useState<
    Partial<Record<keyof AccountFormData, string>>
  >({});

  const handlePageSizeChange = (event: SelectChangeEvent<string>) => {
    setPageSize(Number(event.target.value));
    setPage(1);
  };

  const handleClearAccountFilters = () => {
    setSearchQuery('');
    setSnapshotStateFilter('all');
    setSnapshotRefreshStatusFilter('all');
    setPage(1);
  };

  const handleAddClick = () => {
    setEditingAccount(null);
    setFormData({
      account_id: '',
      api_token: '',
      api_type: 'practice',
      live_max_exposure_guard_enabled: false,
      live_max_estimated_exposure_units: DEFAULT_MAX_GROSS_UNITS,
      live_max_initial_order_guard_enabled: true,
      live_max_initial_order_units: DEFAULT_MAX_INITIAL_ORDER_UNITS,
      live_max_order_guard_enabled: false,
      live_max_order_units: DEFAULT_MAX_ORDER_UNITS,
      live_tick_latency_metric_interval_seconds:
        DEFAULT_TICK_LATENCY_METRIC_INTERVAL_SECONDS,
    });
    setIsDefault(!hasAnyAccount);
    setFormErrors({});
    setShowApiToken(false);
    setDialogOpen(true);
  };

  const handleEditClick = (account: Account) => {
    setEditingAccount(account);
    setFormData({
      account_id: account.account_id,
      api_token: '',
      api_type: account.api_type,
      live_max_exposure_guard_enabled:
        account.live_max_exposure_guard_enabled ?? false,
      live_max_estimated_exposure_units: String(
        account.live_max_estimated_exposure_units ??
          Number(DEFAULT_MAX_GROSS_UNITS)
      ),
      live_max_initial_order_guard_enabled:
        account.live_max_initial_order_guard_enabled ?? true,
      live_max_initial_order_units: String(
        account.live_max_initial_order_units ??
          Number(DEFAULT_MAX_INITIAL_ORDER_UNITS)
      ),
      live_max_order_guard_enabled:
        account.live_max_order_guard_enabled ?? false,
      live_max_order_units: String(
        account.live_max_order_units ?? Number(DEFAULT_MAX_ORDER_UNITS)
      ),
      live_tick_latency_metric_interval_seconds: String(
        account.live_tick_latency_metric_interval_seconds ??
          Number(DEFAULT_TICK_LATENCY_METRIC_INTERVAL_SECONDS)
      ),
    });
    setIsDefault(account.is_default || false);
    setFormErrors({});
    setShowApiToken(false);
    setDialogOpen(true);
  };

  const handleDialogClose = () => {
    setDialogOpen(false);
    setEditingAccount(null);
    setFormData({
      account_id: '',
      api_token: '',
      api_type: 'practice',
      live_max_exposure_guard_enabled: false,
      live_max_estimated_exposure_units: DEFAULT_MAX_GROSS_UNITS,
      live_max_initial_order_guard_enabled: true,
      live_max_initial_order_units: DEFAULT_MAX_INITIAL_ORDER_UNITS,
      live_max_order_guard_enabled: false,
      live_max_order_units: DEFAULT_MAX_ORDER_UNITS,
      live_tick_latency_metric_interval_seconds:
        DEFAULT_TICK_LATENCY_METRIC_INTERVAL_SECONDS,
    });
    setIsDefault(false);
    setFormErrors({});
  };

  const validateForm = (): boolean => {
    const errors: Partial<Record<keyof AccountFormData, string>> = {};
    if (!formData.account_id.trim()) {
      errors.account_id = t('common:validation.required');
    }
    if (!editingAccount && !formData.api_token.trim()) {
      errors.api_token = t('common:validation.required');
    }
    if (formData.live_max_exposure_guard_enabled) {
      const maxGrossUnits = Number(formData.live_max_estimated_exposure_units);
      if (
        !Number.isInteger(maxGrossUnits) ||
        !Number.isFinite(maxGrossUnits) ||
        maxGrossUnits <= 0
      ) {
        errors.live_max_estimated_exposure_units = t(
          'settings:accounts.maxGrossUnitsValidation'
        );
      }
    }
    if (formData.live_max_initial_order_guard_enabled) {
      const maxInitialOrderUnits = Number(
        formData.live_max_initial_order_units
      );
      if (
        !Number.isInteger(maxInitialOrderUnits) ||
        !Number.isFinite(maxInitialOrderUnits) ||
        maxInitialOrderUnits <= 0
      ) {
        errors.live_max_initial_order_units = t(
          'settings:accounts.maxInitialOrderUnitsValidation'
        );
      }
    }
    if (formData.live_max_order_guard_enabled) {
      const maxOrderUnits = Number(formData.live_max_order_units);
      if (
        !Number.isInteger(maxOrderUnits) ||
        !Number.isFinite(maxOrderUnits) ||
        maxOrderUnits <= 0
      ) {
        errors.live_max_order_units = t(
          'settings:accounts.maxOrderUnitsValidation'
        );
      }
    }
    const tickLatencyMetricInterval = Number(
      formData.live_tick_latency_metric_interval_seconds
    );
    if (
      !Number.isInteger(tickLatencyMetricInterval) ||
      !Number.isFinite(tickLatencyMetricInterval) ||
      tickLatencyMetricInterval < 0
    ) {
      errors.live_tick_latency_metric_interval_seconds = t(
        'settings:accounts.tickLatencyMetricIntervalValidation'
      );
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;
    setSubmitting(true);
    try {
      const payload: AccountUpsertData = {
        account_id: formData.account_id,
        api_type: formData.api_type,
        is_default: isDefault,
        live_max_exposure_guard_enabled:
          formData.live_max_exposure_guard_enabled,
        live_max_initial_order_guard_enabled:
          formData.live_max_initial_order_guard_enabled,
        live_max_order_guard_enabled: formData.live_max_order_guard_enabled,
        live_tick_latency_metric_interval_seconds: Number(
          formData.live_tick_latency_metric_interval_seconds ||
            DEFAULT_TICK_LATENCY_METRIC_INTERVAL_SECONDS
        ),
      };
      if (formData.live_max_exposure_guard_enabled) {
        payload.live_max_estimated_exposure_units = Number(
          formData.live_max_estimated_exposure_units || DEFAULT_MAX_GROSS_UNITS
        );
      }
      if (formData.live_max_initial_order_guard_enabled) {
        payload.live_max_initial_order_units = Number(
          formData.live_max_initial_order_units ||
            DEFAULT_MAX_INITIAL_ORDER_UNITS
        );
      }
      if (formData.live_max_order_guard_enabled) {
        payload.live_max_order_units = Number(
          formData.live_max_order_units || DEFAULT_MAX_ORDER_UNITS
        );
      }
      if (formData.api_token.trim()) {
        payload.api_token = formData.api_token;
      }
      if (editingAccount) {
        await updateAccount.mutate({
          id: editingAccount.id,
          data: payload as AccountUpsertData,
        });
      } else {
        await createAccount.mutate(payload as AccountUpsertData);
      }
      showSuccess(t('settings:messages.accountAdded'));
      handleDialogClose();
    } catch (error: unknown) {
      logger.error('Error saving account', {
        error: error instanceof Error ? error.message : String(error),
      });
      let message = t('settings:messages.saveError');
      const err = error as Record<string, unknown>;
      if (err.details && typeof err.details === 'object') {
        const details = err.details as Record<string, unknown>;
        const fieldErrors: Partial<Record<keyof AccountFormData, string>> = {};
        const messages: string[] = [];
        for (const [key, val] of Object.entries(details)) {
          const msgs = Array.isArray(val) ? val.map(String) : [String(val)];
          if (key in formData) {
            fieldErrors[key as keyof AccountFormData] = msgs.join(', ');
          }
          messages.push(...msgs);
        }
        if (Object.keys(fieldErrors).length > 0) {
          setFormErrors((prev) => ({ ...prev, ...fieldErrors }));
        }
        if (messages.length > 0) message = messages.join(' ');
      } else if (err.message && typeof err.message === 'string') {
        message = err.message;
      } else if (error instanceof Error) {
        message = error.message;
      }
      showError(message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteClick = (account: Account) => {
    setAccountToDelete(account);
    setDeleteConfirmOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!accountToDelete) return;
    try {
      await deleteAccount.mutate(accountToDelete.id);
      showSuccess(t('settings:messages.accountDeleted'));
      setDeleteConfirmOpen(false);
      setAccountToDelete(null);
    } catch (error) {
      logger.error('Error deleting account', {
        error: error instanceof Error ? error.message : String(error),
      });
      showError(t('common:errors.deleteFailed'));
    }
  };

  const handleRefreshSnapshot = async (account: Account) => {
    setRefreshingSnapshotIds((current) => new Set(current).add(account.id));
    try {
      const result = await refreshSnapshot.mutate(account.id);
      setRefreshTasksByAccount((current) => ({
        ...current,
        [account.id]: {
          taskId: result.task_id,
          status: result.status,
        },
      }));
      showSuccess(
        t('settings:messages.snapshotRefreshQueued', 'Snapshot refresh queued')
      );
    } catch (error) {
      logger.error('Error queueing account snapshot refresh', {
        account_id: account.account_id,
        error: error instanceof Error ? error.message : String(error),
      });
      showError(
        t(
          'settings:messages.snapshotRefreshFailed',
          'Failed to queue snapshot refresh'
        )
      );
    } finally {
      setRefreshingSnapshotIds((current) => {
        const next = new Set(current);
        next.delete(account.id);
        return next;
      });
    }
  };

  const handleRefreshSnapshotSettled = useCallback(
    (accountId: number) => {
      setRefreshTasksByAccount((current) => {
        if (!(accountId in current)) return current;
        const next = { ...current };
        delete next[accountId];
        return next;
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.accounts.detail(accountId),
        refetchType: 'active',
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.accounts.lists(),
        refetchType: 'active',
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.accounts.pages(),
        refetchType: 'active',
      });
    },
    [queryClient]
  );

  return (
    <PageContainer sx={{ mt: { xs: 2, sm: 4 }, mb: 4 }}>
      <Breadcrumbs />
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', sm: 'row' },
          justifyContent: 'space-between',
          alignItems: { xs: 'stretch', sm: 'center' },
          gap: 1,
          mb: 2,
        }}
      >
        <Typography
          variant="h4"
          sx={{ fontSize: { xs: '1.5rem', sm: '2.125rem' } }}
        >
          {t('settings:accounts.title')}
        </Typography>
        <Box
          sx={{
            display: 'flex',
            gap: 1,
            flexShrink: 0,
            flexWrap: 'wrap',
            justifyContent: { xs: 'flex-end', sm: 'flex-start' },
          }}
        >
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() =>
              queryClient.invalidateQueries({ queryKey: ['accounts'] })
            }
          >
            {t('common:actions.refresh')}
          </Button>
          <Button
            variant="contained"
            color="primary"
            startIcon={<AddIcon />}
            onClick={handleAddClick}
          >
            {t('settings:accounts.addAccount')}
          </Button>
        </Box>
      </Box>

      <Alert severity="info" sx={{ mb: 3 }}>
        <Typography variant="body2">
          {t('settings:accounts.defaultAccountInfo')}
        </Typography>
      </Alert>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box
            sx={{
              display: 'grid',
              gap: 2,
              gridTemplateColumns: {
                xs: '1fr',
                sm: 'repeat(2, minmax(0, 1fr))',
                md: 'repeat(3, minmax(0, 1fr))',
                xl: 'minmax(220px, 1fr) 180px 190px 160px 130px 48px',
              },
              alignItems: 'center',
            }}
          >
            <TextField
              fullWidth
              placeholder={t(
                'settings:accounts.searchAccounts',
                'Search accounts...'
              )}
              value={searchQuery}
              onChange={(event) => {
                setSearchQuery(event.target.value);
                setPage(1);
              }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
              }}
            />
            <FormControl fullWidth>
              <InputLabel>
                {t('settings:accounts.snapshotStateFilter', 'Snapshot state')}
              </InputLabel>
              <Select
                value={snapshotStateFilter}
                label={t(
                  'settings:accounts.snapshotStateFilter',
                  'Snapshot state'
                )}
                onChange={(event) => {
                  setSnapshotStateFilter(
                    event.target.value as SnapshotStateFilterValue
                  );
                  setPage(1);
                }}
              >
                <MenuItem value="all">
                  {t('settings:accounts.allSnapshotStates', 'All states')}
                </MenuItem>
                {SNAPSHOT_STATE_FILTER_OPTIONS.map((state) => (
                  <MenuItem key={state} value={state}>
                    {snapshotStateLabel(t, state)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>
                {t(
                  'settings:accounts.snapshotRefreshStatusFilter',
                  'Refresh status'
                )}
              </InputLabel>
              <Select
                value={snapshotRefreshStatusFilter}
                label={t(
                  'settings:accounts.snapshotRefreshStatusFilter',
                  'Refresh status'
                )}
                onChange={(event) => {
                  setSnapshotRefreshStatusFilter(
                    event.target.value as SnapshotRefreshStatusFilterValue
                  );
                  setPage(1);
                }}
              >
                <MenuItem value="all">
                  {t(
                    'settings:accounts.allRefreshStatuses',
                    'All refresh statuses'
                  )}
                </MenuItem>
                {SNAPSHOT_REFRESH_STATUS_FILTER_OPTIONS.map((refreshStatus) => (
                  <MenuItem key={refreshStatus} value={refreshStatus}>
                    {snapshotRefreshStatusLabel(t, refreshStatus)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>{t('trading:filters.sortBy', 'Sort By')}</InputLabel>
              <Select
                value={sortBy}
                label={t('trading:filters.sortBy', 'Sort By')}
                onChange={(event) => {
                  setSortBy(event.target.value);
                  setPage(1);
                }}
              >
                <MenuItem value="-created_at">
                  {t('trading:filters.newestFirst', 'Newest First')}
                </MenuItem>
                <MenuItem value="created_at">
                  {t('trading:filters.oldestFirst', 'Oldest First')}
                </MenuItem>
                <MenuItem value="account_id">
                  {t('settings:accounts.accountId')} A-Z
                </MenuItem>
                <MenuItem value="-account_id">
                  {t('settings:accounts.accountId')} Z-A
                </MenuItem>
                <MenuItem value="-updated_at">
                  {t('trading:filters.recentlyUpdated', 'Recently Updated')}
                </MenuItem>
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>
                {t('common:labels.pageSize', 'Page size')}
              </InputLabel>
              <Select
                value={String(pageSize)}
                label={t('common:labels.pageSize', 'Page size')}
                onChange={handlePageSizeChange}
              >
                {[6, 12, 24, 48].map((size) => (
                  <MenuItem key={size} value={String(size)}>
                    {size}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Box
              sx={{
                display: 'flex',
                justifyContent: { xs: 'flex-end', xl: 'center' },
                alignItems: 'center',
                minHeight: 56,
              }}
            >
              <Tooltip
                title={t(
                  'settings:accounts.clearAccountFilters',
                  'Clear filters'
                )}
              >
                <span>
                  <IconButton
                    color="primary"
                    disabled={!hasActiveAccountFilters}
                    onClick={handleClearAccountFilters}
                    aria-label={t(
                      'settings:accounts.clearAccountFilters',
                      'Clear filters'
                    )}
                  >
                    <ClearFiltersIcon />
                  </IconButton>
                </span>
              </Tooltip>
            </Box>
          </Box>
        </CardContent>
      </Card>

      {loading && (
        <Box display="flex" justifyContent="center" py={4}>
          <CircularProgress />
        </Box>
      )}

      {accountsError && (
        <Alert severity="error">{t('common:errors.fetchFailed')}</Alert>
      )}

      {!loading && !accountsError && accounts.length === 0 && (
        <Alert severity="info">{t('common:messages.noData')}</Alert>
      )}

      {!loading && accounts.length > 0 && (
        <>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: '1fr',
                sm: 'repeat(2, 1fr)',
                md: 'repeat(3, 1fr)',
              },
              gap: 2,
            }}
          >
            {accounts.map((account) => (
              <Box key={account.id}>
                <AccountCard
                  account={account}
                  onEdit={handleEditClick}
                  onDelete={handleDeleteClick}
                  onRefreshSnapshot={handleRefreshSnapshot}
                  onRefreshSnapshotSettled={handleRefreshSnapshotSettled}
                  isRefreshingSnapshot={refreshingSnapshotIds.has(account.id)}
                  refreshTask={refreshTasksByAccount[account.id]}
                />
              </Box>
            ))}
          </Box>
          {totalPages > 1 ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
              <Pagination
                count={totalPages}
                page={page}
                onChange={(_event, value) => setPage(value)}
                color="primary"
              />
            </Box>
          ) : null}
        </>
      )}

      {/* Add/Edit Dialog */}
      <Dialog
        open={dialogOpen}
        onClose={handleDialogClose}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {editingAccount
            ? t('settings:accounts.editAccount')
            : t('settings:accounts.addAccount')}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <TextField
              fullWidth
              label={t('settings:accounts.accountId')}
              value={formData.account_id}
              onChange={(e) =>
                setFormData({ ...formData, account_id: e.target.value })
              }
              error={!!formErrors.account_id}
              helperText={formErrors.account_id}
              margin="normal"
              required
            />
            <TextField
              fullWidth
              label={t('settings:accounts.apiToken')}
              type={showApiToken ? 'text' : 'password'}
              value={formData.api_token}
              onChange={(e) =>
                setFormData({ ...formData, api_token: e.target.value })
              }
              error={!!formErrors.api_token}
              helperText={
                formErrors.api_token ||
                (editingAccount
                  ? t('settings:accounts.leaveBlankToKeepToken')
                  : undefined)
              }
              margin="normal"
              required={!editingAccount}
              InputProps={{
                endAdornment: (
                  <IconButton
                    onClick={() => setShowApiToken(!showApiToken)}
                    edge="end"
                  >
                    {showApiToken ? <VisibilityOff /> : <Visibility />}
                  </IconButton>
                ),
              }}
            />
            <FormControl fullWidth margin="normal">
              <InputLabel id="api-type-label">
                {t('settings:accounts.apiType')}
              </InputLabel>
              <Select
                labelId="api-type-label"
                value={formData.api_type}
                label={t('settings:accounts.apiType')}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    api_type: e.target.value as 'practice' | 'live',
                  })
                }
              >
                <MenuItem value="practice">
                  {t('settings:accounts.practice')}
                </MenuItem>
                <MenuItem value="live">{t('settings:accounts.live')}</MenuItem>
              </Select>
            </FormControl>
            <TextField
              fullWidth
              label={t('settings:accounts.tickLatencyMetricIntervalSeconds')}
              type="text"
              inputMode="decimal"
              value={formData.live_tick_latency_metric_interval_seconds}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  live_tick_latency_metric_interval_seconds: e.target.value,
                })
              }
              error={!!formErrors.live_tick_latency_metric_interval_seconds}
              helperText={
                formErrors.live_tick_latency_metric_interval_seconds ||
                t('settings:accounts.tickLatencyMetricIntervalSecondsHelper')
              }
              margin="normal"
              inputProps={{ min: 0, step: 1 }}
            />
            <Box sx={{ mt: 2 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.live_max_exposure_guard_enabled}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        live_max_exposure_guard_enabled: e.target.checked,
                      })
                    }
                  />
                }
                label={t('settings:accounts.maxGrossUnitsGuard')}
              />
              {formData.live_max_exposure_guard_enabled && (
                <TextField
                  fullWidth
                  label={t('settings:accounts.maxGrossUnits')}
                  type="text"
                  inputMode="decimal"
                  value={formData.live_max_estimated_exposure_units}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      live_max_estimated_exposure_units: e.target.value,
                    })
                  }
                  error={!!formErrors.live_max_estimated_exposure_units}
                  helperText={formErrors.live_max_estimated_exposure_units}
                  margin="normal"
                  inputProps={{ min: 1, step: 1 }}
                />
              )}
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.live_max_initial_order_guard_enabled}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        live_max_initial_order_guard_enabled: e.target.checked,
                      })
                    }
                  />
                }
                label={t('settings:accounts.maxInitialOrderUnitsGuard')}
              />
              {formData.live_max_initial_order_guard_enabled && (
                <TextField
                  fullWidth
                  label={t('settings:accounts.maxInitialOrderUnits')}
                  type="text"
                  inputMode="decimal"
                  value={formData.live_max_initial_order_units}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      live_max_initial_order_units: e.target.value,
                    })
                  }
                  error={!!formErrors.live_max_initial_order_units}
                  helperText={formErrors.live_max_initial_order_units}
                  margin="normal"
                  inputProps={{ min: 1, step: 1 }}
                />
              )}
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.live_max_order_guard_enabled}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        live_max_order_guard_enabled: e.target.checked,
                      })
                    }
                  />
                }
                label={t('settings:accounts.maxOrderUnitsGuard')}
              />
              {formData.live_max_order_guard_enabled && (
                <TextField
                  fullWidth
                  label={t('settings:accounts.maxOrderUnits')}
                  type="text"
                  inputMode="decimal"
                  value={formData.live_max_order_units}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      live_max_order_units: e.target.value,
                    })
                  }
                  error={!!formErrors.live_max_order_units}
                  helperText={formErrors.live_max_order_units}
                  margin="normal"
                  inputProps={{ min: 1, step: 1 }}
                />
              )}
            </Box>
            <Box sx={{ mt: 2 }}>
              <Box display="flex" alignItems="center" gap={1}>
                <input
                  type="checkbox"
                  id="is-default-checkbox"
                  checked={isDefault}
                  onChange={(e) => setIsDefault(e.target.checked)}
                  disabled={!hasAnyAccount && !editingAccount}
                />
                <label htmlFor="is-default-checkbox">
                  <Typography variant="body2">
                    {t('settings:accounts.setAsDefault')}
                  </Typography>
                </label>
              </Box>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mt: 0.5, display: 'block' }}
              >
                {t('settings:accounts.defaultAccountDescription')}
              </Typography>
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDialogClose} disabled={submitting}>
            {t('common:actions.cancel')}
          </Button>
          <Button
            onClick={handleSubmit}
            variant="contained"
            color="primary"
            disabled={submitting}
          >
            {submitting ? (
              <CircularProgress size={24} />
            ) : editingAccount ? (
              t('common:actions.save')
            ) : (
              t('common:actions.add')
            )}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={deleteConfirmOpen}
        title={t('settings:accounts.deleteAccount')}
        message={t('settings:accounts.confirmDelete')}
        confirmText={t('common:actions.delete')}
        cancelText={t('common:actions.cancel')}
        confirmColor="error"
        onConfirm={handleDeleteConfirm}
        onCancel={() => {
          setDeleteConfirmOpen(false);
          setAccountToDelete(null);
        }}
      />
    </PageContainer>
  );
}
