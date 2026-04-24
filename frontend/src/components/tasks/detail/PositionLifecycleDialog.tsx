import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  InputAdornment,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import {
  Close as CloseIcon,
  Search as SearchIcon,
  TrendingDown as ShortIcon,
  TrendingUp as LongIcon,
} from '@mui/icons-material';
import { useAuth } from '../../../contexts/AuthContext';
import { fetchTaskResourceObject } from '../../../services/api/taskResources';
import type { TaskType } from '../../../types/common';
import { formatDateTimeInTimezone } from '../../../utils/timezone';

interface PositionLifecycleDialogProps {
  open: boolean;
  onClose: () => void;
  taskId: string;
  taskType: TaskType;
  executionRunId?: string;
  initialPositionId?: string;
  positionData?: unknown | null;
  timezone?: string;
}

type LifecycleEventKind =
  | 'opened'
  | 'rebuilt'
  | 'partial_close'
  | 'closed'
  | 'stop_loss_closed'
  | 'rebuilt_into';

interface PositionLifecycleEvent {
  id: string;
  kind: LifecycleEventKind;
  timestamp: string | null;
  position_id: string;
  related_position_id?: string | null;
  direction?: string | null;
  units?: number | string | null;
  entry_price?: string | null;
  exit_price?: string | null;
  planned_exit_price?: string | null;
  planned_exit_price_formula?: string | null;
  description?: string | null;
  close_reason?: string | null;
  realized_pnl?: string | null;
}

interface PositionLifecycleSummary {
  position_id: string;
  direction: 'long' | 'short';
  units: number;
  is_open: boolean;
  is_rebuild: boolean;
  instrument: string;
  layer_index?: number | null;
  retracement_count?: number | null;
  entry_price: string;
  entry_time: string | null;
  exit_price?: string | null;
  exit_time?: string | null;
  planned_exit_price?: string | null;
  planned_exit_price_formula?: string | null;
  stop_loss_price?: string | null;
  close_reason?: string | null;
  realized_pnl?: string | null;
}

interface PositionLifecycleItem {
  position_id: string;
  original_position_id?: string | null;
  rebuilt_position_ids: string[];
  summary: PositionLifecycleSummary;
  events: PositionLifecycleEvent[];
}

interface PositionLifecycleResponse {
  requested_position_id: string;
  matched_position_id: string;
  position_ids: string[];
  positions: PositionLifecycleItem[];
  chain_realized_pnl?: string | null;
}

const formatTimestamp = (
  value?: string | null,
  language?: string,
  timezone = 'UTC'
): string =>
  formatDateTimeInTimezone(value, timezone, language, {
    includeSeconds: true,
    includeTimezone: true,
  });

const shortId = (value?: string | null): string =>
  value ? value.slice(0, 8) : '-';

function quoteCurrencySymbol(instrument?: string): string {
  if (!instrument) return '';
  const quote = instrument.split('_')[1] ?? '';
  if (quote === 'JPY') return '¥';
  if (quote === 'USD') return '$';
  if (quote === 'EUR') return '€';
  if (quote === 'GBP') return '£';
  return quote + ' ';
}

function quoteCurrencyDecimals(instrument?: string): number {
  if (!instrument) return 3;
  const quote = instrument.split('_')[1] ?? '';
  return quote === 'JPY' ? 0 : 2;
}

const formatPrice = (value?: string | null): string => {
  if (!value) return '-';
  const parsed = Number(value);
  return Number.isFinite(parsed)
    ? `¥${parsed.toLocaleString('en-US', {
        minimumFractionDigits: 3,
        maximumFractionDigits: 3,
      })}`
    : value;
};

const formatSignedPnl = (
  value?: string | null,
  instrument?: string
): string => {
  if (!value) return '-';
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return value;
  const sym = quoteCurrencySymbol(instrument);
  const decimals = quoteCurrencyDecimals(instrument);
  const text = `${sym}${Math.abs(parsed).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
  if (parsed > 0) return `+${text}`;
  if (parsed < 0) return `-${text}`;
  return text;
};

function eventColor(
  kind: LifecycleEventKind
): 'success' | 'info' | 'warning' | 'default' | 'error' {
  switch (kind) {
    case 'opened':
      return 'success';
    case 'rebuilt':
      return 'info';
    case 'partial_close':
      return 'warning';
    case 'stop_loss_closed':
      return 'error';
    case 'rebuilt_into':
      return 'info';
    default:
      return 'default';
  }
}

const eventDotColor = (kind: LifecycleEventKind): string => {
  switch (kind) {
    case 'opened':
      return 'success.main';
    case 'rebuilt':
    case 'rebuilt_into':
      return 'info.main';
    case 'partial_close':
      return 'warning.main';
    case 'stop_loss_closed':
      return 'error.main';
    default:
      return 'text.secondary';
  }
};

function closeReasonLabel(
  reason?: string | null,
  t?: (key: string) => string
): string {
  if (!reason) return '-';
  const mapping: Record<string, string> = {
    normal: 'tables.positions.lifecycle.closeReasons.normal',
    tp: 'tables.positions.lifecycle.closeReasons.normal',
    close_position: 'tables.positions.lifecycle.closeReasons.normal',
    stop_loss: 'tables.positions.lifecycle.closeReasons.stopLossProtection',
    shrink: 'tables.positions.lifecycle.closeReasons.shrinkProtection',
    volatility_lock:
      'tables.positions.lifecycle.closeReasons.volatilityLockProtection',
    margin_protection:
      'tables.positions.lifecycle.closeReasons.marginProtection',
    counter_tp: 'tables.positions.lifecycle.closeReasons.counterTp',
    layer_initial_tp: 'tables.positions.lifecycle.closeReasons.layerInitialTp',
    lock_hedge_neutralize:
      'tables.positions.lifecycle.closeReasons.lockHedgeNeutralize',
  };
  const key = mapping[reason];
  if (key && t) return t(key);
  return reason.replace(/_/g, ' ');
}

const LifecycleField: React.FC<{
  label: string;
  value: React.ReactNode;
  mono?: boolean;
  noWrap?: boolean;
  minWidth?: number;
}> = ({ label, value, mono = false, noWrap = false, minWidth = 180 }) => (
  <Box sx={{ minWidth, flex: `1 1 ${minWidth}px` }}>
    <Typography variant="caption" color="text.secondary">
      {label}
    </Typography>
    <Typography
      variant="body2"
      sx={{
        fontFamily: mono ? 'monospace' : 'inherit',
        wordBreak: noWrap ? 'normal' : mono ? 'break-all' : 'break-word',
        whiteSpace: noWrap ? 'nowrap' : 'normal',
      }}
    >
      {value}
    </Typography>
  </Box>
);

const LifecycleEventRow: React.FC<{
  event: PositionLifecycleEvent;
  timezone?: string;
  instrument?: string;
}> = ({ event, timezone = 'UTC', instrument }) => {
  const { t, i18n } = useTranslation('common');
  const relatedLabel =
    event.kind === 'rebuilt'
      ? t('tables.positions.lifecycle.fields.rebuiltFrom')
      : event.kind === 'rebuilt_into'
        ? t('tables.positions.lifecycle.fields.rebuiltTo')
        : undefined;

  return (
    <Box
      sx={{
        position: 'relative',
        pl: 3,
        py: 1.5,
        borderLeft: 2,
        borderColor: 'divider',
      }}
    >
      <Box
        sx={{
          position: 'absolute',
          left: -7,
          top: 20,
          width: 12,
          height: 12,
          borderRadius: '50%',
          bgcolor: eventDotColor(event.kind),
        }}
      />
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={1}
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', md: 'center' }}
      >
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          <Chip
            size="small"
            color={eventColor(event.kind)}
            label={t(`tables.positions.lifecycle.events.${event.kind}`)}
          />
          {relatedLabel && event.related_position_id ? (
            <Chip
              size="small"
              variant="outlined"
              label={`${relatedLabel}: ${shortId(event.related_position_id)}`}
            />
          ) : null}
        </Stack>
        <Typography variant="caption" color="text.secondary">
          {formatTimestamp(event.timestamp, i18n.language, timezone)}
        </Typography>
      </Stack>
      <Stack
        direction="row"
        spacing={2}
        flexWrap="wrap"
        useFlexGap
        sx={{ mt: 1 }}
      >
        {event.entry_price ? (
          <LifecycleField
            label={t('tables.positions.entryPrice')}
            value={formatPrice(event.entry_price)}
          />
        ) : null}
        {event.exit_price ? (
          <LifecycleField
            label={t('tables.positions.exitPrice')}
            value={formatPrice(event.exit_price)}
          />
        ) : null}
        {event.planned_exit_price ? (
          <LifecycleField
            label={t('tables.positions.plannedExitPrice')}
            value={formatPrice(event.planned_exit_price)}
          />
        ) : null}
        {event.realized_pnl ? (
          <LifecycleField
            label={t('tables.positions.realizedPnl')}
            value={
              <Typography
                component="span"
                color={
                  Number(event.realized_pnl) >= 0
                    ? 'success.main'
                    : 'error.main'
                }
                fontWeight={700}
              >
                {formatSignedPnl(event.realized_pnl, instrument)}
              </Typography>
            }
          />
        ) : null}
      </Stack>
      {event.close_reason ? (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ mt: 1, display: 'block' }}
        >
          {t('tables.positions.lifecycle.fields.closeReason')}:{' '}
          {closeReasonLabel(event.close_reason, t)}
        </Typography>
      ) : null}
      {event.related_position_id ? (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{
            display: 'block',
            mt: 1,
            fontFamily: 'monospace',
            wordBreak: 'break-all',
          }}
        >
          {event.related_position_id}
        </Typography>
      ) : null}
      {event.description ? (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {event.description}
        </Typography>
      ) : null}
      {event.planned_exit_price_formula ? (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mt: 1, wordBreak: 'break-word' }}
        >
          {event.planned_exit_price_formula}
        </Typography>
      ) : null}
    </Box>
  );
};

const PositionCard: React.FC<{
  item: PositionLifecycleItem;
  timezone?: string;
}> = ({ item, timezone = 'UTC' }) => {
  const { t, i18n } = useTranslation('common');
  const summary = item.summary;
  const pnlValue = summary.realized_pnl ? Number(summary.realized_pnl) : null;

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack spacing={2}>
          <Stack
            direction={{ xs: 'column', md: 'row' }}
            justifyContent="space-between"
            spacing={1}
          >
            <Box>
              <Stack
                direction="row"
                spacing={1}
                alignItems="center"
                flexWrap="wrap"
              >
                <Typography variant="h6" sx={{ fontFamily: 'monospace' }}>
                  {shortId(summary.position_id)}
                </Typography>
                <Chip
                  size="small"
                  label={
                    summary.direction === 'long'
                      ? t('tables.positions.long')
                      : t('tables.positions.short')
                  }
                  color={summary.direction === 'long' ? 'success' : 'error'}
                  icon={
                    summary.direction === 'long' ? <LongIcon /> : <ShortIcon />
                  }
                />
                <Chip
                  size="small"
                  variant="outlined"
                  color={summary.is_open ? 'success' : 'default'}
                  label={
                    summary.is_open
                      ? t('tables.positions.open')
                      : t('tables.positions.closed')
                  }
                />
                {summary.is_rebuild ? (
                  <Chip
                    size="small"
                    color="info"
                    variant="outlined"
                    label={t('tables.positions.rebuild')}
                  />
                ) : null}
              </Stack>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{
                  display: 'block',
                  mt: 0.5,
                  fontFamily: 'monospace',
                  wordBreak: 'break-all',
                }}
              >
                {summary.position_id}
              </Typography>
            </Box>
            {pnlValue != null ? (
              <Typography
                variant="h6"
                color={pnlValue >= 0 ? 'success.main' : 'error.main'}
              >
                {formatSignedPnl(summary.realized_pnl, summary.instrument)}
              </Typography>
            ) : null}
          </Stack>

          <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
            <LifecycleField
              label={t('tables.positions.instrument')}
              value={summary.instrument}
            />
            <LifecycleField
              label={t('tables.positions.units')}
              value={String(summary.units)}
            />
            <LifecycleField
              label={t('tables.positions.layer')}
              value={
                summary.layer_index != null ? `L${summary.layer_index}` : '-'
              }
            />
            <LifecycleField
              label={t('tables.positions.retracement')}
              value={
                summary.retracement_count != null
                  ? `R${summary.retracement_count}`
                  : '-'
              }
            />
            <LifecycleField
              label={t('tables.positions.entryTime')}
              value={formatTimestamp(
                summary.entry_time,
                i18n.language,
                timezone
              )}
              noWrap
              minWidth={240}
            />
            <LifecycleField
              label={t('tables.positions.exitTime')}
              value={formatTimestamp(
                summary.exit_time,
                i18n.language,
                timezone
              )}
              noWrap
              minWidth={240}
            />
            <LifecycleField
              label={t('tables.positions.entryPrice')}
              value={formatPrice(summary.entry_price)}
            />
            <LifecycleField
              label={t('tables.positions.exitPrice')}
              value={formatPrice(summary.exit_price)}
            />
            <LifecycleField
              label={t('tables.positions.plannedExitPrice')}
              value={formatPrice(summary.planned_exit_price)}
            />
            <LifecycleField
              label={t('tables.positions.stopLossPrice')}
              value={formatPrice(summary.stop_loss_price)}
            />
            <LifecycleField
              label={t('tables.positions.lifecycle.fields.closeReason')}
              value={closeReasonLabel(summary.close_reason, t)}
            />
          </Stack>

          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Chip
              size="small"
              variant="outlined"
              label={`${t('tables.positions.lifecycle.fields.positionId')}: ${shortId(
                summary.position_id
              )}`}
            />
            {item.original_position_id ? (
              <Chip
                size="small"
                variant="outlined"
                label={`${t('tables.positions.lifecycle.fields.rebuiltFrom')}: ${shortId(
                  item.original_position_id
                )}`}
              />
            ) : null}
            {item.rebuilt_position_ids.map((positionId) => (
              <Chip
                key={positionId}
                size="small"
                variant="outlined"
                label={`${t('tables.positions.lifecycle.fields.rebuiltTo')}: ${shortId(
                  positionId
                )}`}
              />
            ))}
          </Stack>

          {summary.planned_exit_price_formula ? (
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('tables.positions.lifecycle.fields.plannedExitFormula')}
              </Typography>
              <Typography variant="body2" sx={{ wordBreak: 'break-word' }}>
                {summary.planned_exit_price_formula}
              </Typography>
            </Box>
          ) : null}

          <Divider />

          <Stack spacing={1}>
            {item.events.map((event) => (
              <LifecycleEventRow
                key={event.id}
                event={event}
                timezone={timezone}
                instrument={summary.instrument}
              />
            ))}
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
};

export const PositionLifecycleDialog: React.FC<
  PositionLifecycleDialogProps
> = ({
  open,
  onClose,
  taskId,
  taskType,
  executionRunId,
  initialPositionId,
  timezone,
}) => {
  const { t } = useTranslation('common');
  const { user } = useAuth();
  const resolvedTimezone = timezone || user?.timezone || 'UTC';
  const [searchValue, setSearchValue] = useState(initialPositionId ?? '');
  const [activePositionId, setActivePositionId] = useState(
    initialPositionId ?? ''
  );
  const [data, setData] = useState<PositionLifecycleResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && initialPositionId) {
      setSearchValue(initialPositionId);
      setActivePositionId(initialPositionId);
    }
  }, [initialPositionId, open]);

  useEffect(() => {
    if (!open || !activePositionId.trim()) {
      setData(null);
      setError(null);
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    const run = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response =
          await fetchTaskResourceObject<PositionLifecycleResponse>(
            taskType,
            taskId,
            'position-lifecycle',
            {
              ...(executionRunId ? { execution_id: executionRunId } : {}),
              position_id: activePositionId.trim(),
            }
          );
        if (!cancelled) {
          setData(response);
        }
      } catch (err) {
        if (!cancelled) {
          setData(null);
          setError(
            err instanceof Error ? err.message : 'Failed to load lifecycle'
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [activePositionId, executionRunId, open, taskId, taskType]);

  const positions = useMemo(() => data?.positions ?? [], [data]);

  const handleSearch = () => {
    const trimmed = searchValue.trim();
    if (trimmed) {
      setActivePositionId(trimmed);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Typography variant="h6">
            {t('tables.positions.lifecycle.title')}
          </Typography>
          <IconButton onClick={onClose} size="small" aria-label="close">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2.5}>
          <TextField
            fullWidth
            size="small"
            label={t('tables.positions.lifecycle.searchLabel')}
            placeholder={t('tables.positions.lifecycle.searchPlaceholder')}
            value={searchValue}
            onChange={(event) => setSearchValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                handleSearch();
              }
            }}
            slotProps={{
              input: {
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={handleSearch}
                      size="small"
                      aria-label="search"
                    >
                      <SearchIcon />
                    </IconButton>
                  </InputAdornment>
                ),
              },
            }}
          />

          {!activePositionId ? (
            <Alert severity="info">
              {t('tables.positions.lifecycle.enterPositionId')}
            </Alert>
          ) : null}

          {isLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
              <CircularProgress />
            </Box>
          ) : null}

          {!isLoading && error ? <Alert severity="error">{error}</Alert> : null}

          {!isLoading &&
          !error &&
          activePositionId &&
          positions.length === 0 ? (
            <Alert severity="info">
              {t('tables.positions.lifecycle.noData')}
            </Alert>
          ) : null}

          {!isLoading && !error && positions.length > 0 && data ? (
            <Stack spacing={2.5}>
              <Card variant="outlined">
                <CardContent>
                  <Stack
                    direction={{ xs: 'column', md: 'row' }}
                    spacing={1.5}
                    justifyContent="space-between"
                  >
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        {t('tables.positions.lifecycle.chainSummary', {
                          count: data.positions.length,
                        })}
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{ fontFamily: 'monospace', mt: 0.5 }}
                      >
                        {data.matched_position_id}
                      </Typography>
                      {data.chain_realized_pnl != null ? (
                        <Stack
                          direction="row"
                          spacing={1}
                          alignItems="baseline"
                          sx={{ mt: 1 }}
                        >
                          <Typography variant="caption" color="text.secondary">
                            {t(
                              'tables.positions.lifecycle.fields.chainRealizedPnl'
                            )}
                          </Typography>
                          <Typography
                            variant="subtitle1"
                            color={
                              Number(data.chain_realized_pnl) >= 0
                                ? 'success.main'
                                : 'error.main'
                            }
                            fontWeight={700}
                          >
                            {formatSignedPnl(
                              data.chain_realized_pnl,
                              positions[0]?.summary.instrument
                            )}
                          </Typography>
                        </Stack>
                      ) : null}
                    </Box>
                    <Stack
                      direction="row"
                      spacing={1}
                      flexWrap="wrap"
                      useFlexGap
                    >
                      {data.position_ids.map((positionId) => (
                        <Chip
                          key={positionId}
                          size="small"
                          variant={
                            positionId === data.matched_position_id
                              ? 'filled'
                              : 'outlined'
                          }
                          color={
                            positionId === data.matched_position_id
                              ? 'primary'
                              : 'default'
                          }
                          label={shortId(positionId)}
                        />
                      ))}
                    </Stack>
                  </Stack>
                </CardContent>
              </Card>

              {positions.map((item) => (
                <PositionCard
                  key={item.position_id}
                  item={item}
                  timezone={resolvedTimezone}
                />
              ))}
            </Stack>
          ) : null}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>
          {t('tables.positions.lifecycle.close')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default PositionLifecycleDialog;
