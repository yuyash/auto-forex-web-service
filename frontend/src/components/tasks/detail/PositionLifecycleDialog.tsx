/**
 * PositionLifecycleDialog Component
 *
 * Displays the lifecycle logs for a specific position in a dialog.
 * Shows when and why a position was opened, and when/why it was closed.
 * Supports searching by position ID prefix (truncated UUID).
 */

import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Chip,
  CircularProgress,
  Alert,
  TextField,
  IconButton,
  InputAdornment,
  Divider,
} from '@mui/material';
import {
  Timeline,
  TimelineItem,
  TimelineSeparator,
  TimelineConnector,
  TimelineContent,
  TimelineDot,
  TimelineOppositeContent,
} from '@mui/lab';
import {
  Close as CloseIcon,
  Search as SearchIcon,
  TrendingUp as LongIcon,
  TrendingDown as ShortIcon,
} from '@mui/icons-material';
import { useTaskLogs, type TaskLog } from '../../../hooks/useTaskLogs';
import { TaskType } from '../../../types/common';
import type { TaskPosition } from '../../../hooks/useTaskPositions';

interface PositionLifecycleDialogProps {
  open: boolean;
  onClose: () => void;
  taskId: string;
  taskType: TaskType;
  executionRunId?: string;
  initialPositionId?: string;
  positionData?: TaskPosition | null;
}

const formatTimestamp = (ts: string): string =>
  new Date(ts).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

type LifecycleEvent = 'OPENED' | 'CLOSED' | 'PARTIAL_CLOSE';

function getLifecycleColor(
  event: LifecycleEvent
): 'success' | 'error' | 'warning' {
  switch (event) {
    case 'OPENED':
      return 'success';
    case 'CLOSED':
      return 'error';
    case 'PARTIAL_CLOSE':
      return 'warning';
    default:
      return 'success';
  }
}

export const PositionLifecycleDialog: React.FC<
  PositionLifecycleDialogProps
> = ({
  open,
  onClose,
  taskId,
  taskType,
  executionRunId,
  initialPositionId,
  positionData,
}) => {
  const { t } = useTranslation('common');
  const [searchValue, setSearchValue] = useState(initialPositionId ?? '');
  const [activePositionId, setActivePositionId] = useState(
    initialPositionId ?? ''
  );

  // Reset search when dialog opens with a new position
  React.useEffect(() => {
    if (open && initialPositionId) {
      setSearchValue(initialPositionId);
      setActivePositionId(initialPositionId);
    }
  }, [open, initialPositionId]);

  // Stabilize the component filter array to avoid infinite re-render loops.
  // useTaskLogs includes `component` in a useCallback dependency array,
  // so a new array reference on every render triggers fetch → setState → re-render.
  const componentFilter = useMemo(
    () => (activePositionId ? ['position.lifecycle'] : undefined),
    [activePositionId]
  );

  const { logs, isLoading, error } = useTaskLogs({
    taskId: open && activePositionId ? taskId : '',
    taskType,
    executionRunId,
    component: componentFilter,
    positionId: activePositionId || undefined,
    page: 1,
    pageSize: 100,
  });

  // Sort logs chronologically (oldest first for timeline)
  const sortedLogs = useMemo(
    () => [...logs].sort((a, b) => a.timestamp.localeCompare(b.timestamp)),
    [logs]
  );

  const handleSearch = () => {
    const trimmed = searchValue.trim();
    if (trimmed) {
      setActivePositionId(trimmed);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      aria-labelledby="position-lifecycle-title"
    >
      <DialogTitle id="position-lifecycle-title">
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
      <DialogContent>
        {/* Search bar */}
        <Box sx={{ mb: 3 }}>
          <TextField
            fullWidth
            size="small"
            label={t('tables.positions.lifecycle.searchLabel')}
            placeholder={t('tables.positions.lifecycle.searchPlaceholder')}
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            onKeyDown={handleKeyDown}
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
        </Box>

        {!activePositionId && (
          <Alert severity="info">
            {t('tables.positions.lifecycle.enterPositionId')}
          </Alert>
        )}

        {activePositionId && isLoading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        )}

        {activePositionId && error && (
          <Alert severity="error">{error.message}</Alert>
        )}

        {activePositionId &&
          !isLoading &&
          !error &&
          sortedLogs.length === 0 && (
            <Alert severity="info">
              {t('tables.positions.lifecycle.noLogs')}
            </Alert>
          )}

        {activePositionId && !isLoading && sortedLogs.length > 0 && (
          <Box>
            {/* Position summary */}
            <PositionSummary logs={sortedLogs} positionData={positionData} />
            <Divider sx={{ my: 2 }} />
            {/* Timeline */}
            <Timeline position="alternate">
              {sortedLogs.map((log, idx) => {
                const ctx = (log.details as Record<string, unknown>)
                  ?.context as Record<string, unknown> | undefined;
                const lifecycleEvent =
                  (ctx?.lifecycle_event as LifecycleEvent) ?? 'OPENED';
                const color = getLifecycleColor(lifecycleEvent);
                const isLast = idx === sortedLogs.length - 1;

                return (
                  <TimelineItem key={log.id}>
                    <TimelineOppositeContent
                      sx={{ m: 'auto 0' }}
                      variant="body2"
                      color="text.secondary"
                    >
                      {formatTimestamp(log.timestamp)}
                    </TimelineOppositeContent>
                    <TimelineSeparator>
                      <TimelineConnector sx={{ opacity: idx === 0 ? 0 : 1 }} />
                      <TimelineDot color={color}>
                        {ctx?.direction === 'LONG' ||
                        ctx?.direction === 'long' ? (
                          <LongIcon fontSize="small" />
                        ) : (
                          <ShortIcon fontSize="small" />
                        )}
                      </TimelineDot>
                      <TimelineConnector sx={{ opacity: isLast ? 0 : 1 }} />
                    </TimelineSeparator>
                    <TimelineContent sx={{ py: '12px', px: 2 }}>
                      <Chip
                        label={lifecycleEvent}
                        color={color}
                        size="small"
                        sx={{ mb: 0.5 }}
                      />
                      <Typography variant="body2" sx={{ mt: 0.5 }}>
                        {log.message}
                      </Typography>
                      <LifecycleDetails ctx={ctx} positionData={positionData} />
                    </TimelineContent>
                  </TimelineItem>
                );
              })}
            </Timeline>
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>
          {t('tables.positions.lifecycle.close')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

/** Renders a summary card from the first and last lifecycle log entries. */
const PositionSummary: React.FC<{
  logs: TaskLog[];
  positionData?: TaskPosition | null;
}> = ({ logs, positionData }) => {
  const { t } = useTranslation('common');
  const first = logs[0];
  const last = logs[logs.length - 1];
  const firstCtx = (first?.details as Record<string, unknown>)?.context as
    | Record<string, unknown>
    | undefined;
  const lastCtx = (last?.details as Record<string, unknown>)?.context as
    | Record<string, unknown>
    | undefined;

  // Prefer positionData (from Positions API) over log context
  const positionId =
    positionData?.id ?? (firstCtx?.position_id as string) ?? '';
  const direction =
    positionData?.direction?.toUpperCase() ??
    (firstCtx?.direction as string) ??
    '';
  const instrument =
    positionData?.instrument ?? (firstCtx?.instrument as string) ?? '';
  const entryPrice =
    positionData?.entry_price ?? (firstCtx?.entry_price as string | undefined);
  const exitPrice =
    positionData?.exit_price ?? (lastCtx?.exit_price as string | undefined);
  const plannedExitPrice =
    positionData?.planned_exit_price ??
    (firstCtx?.planned_exit_price as string | undefined);
  const plannedExitFormula =
    positionData?.planned_exit_price_formula ??
    (firstCtx?.planned_exit_price_formula as string | undefined);
  const units = positionData
    ? Math.abs(positionData.units)
    : firstCtx?.units != null
      ? Number(firstCtx.units)
      : 0;
  const isClosed =
    positionData != null
      ? !positionData.is_open
      : lastCtx?.lifecycle_event === 'CLOSED';

  // Calculate realized PnL the same way as the positions table:
  // (exit - entry) * units for LONG, (entry - exit) * units for SHORT.
  const computedPnl = (() => {
    if (!isClosed || !entryPrice || !exitPrice) return null;
    const ep = parseFloat(entryPrice);
    const xp = parseFloat(exitPrice);
    const isLong = direction === 'LONG' || direction === 'long';
    return isLong ? (xp - ep) * units : (ep - xp) * units;
  })();

  return (
    <Box
      sx={{
        p: 2,
        bgcolor: 'background.default',
        borderRadius: 1,
        display: 'flex',
        gap: 3,
        flexWrap: 'wrap',
        alignItems: 'center',
      }}
    >
      <Box>
        <Typography variant="caption" color="text.secondary">
          {t('tables.positions.positionId')}
        </Typography>
        <Typography variant="body2" fontFamily="monospace">
          {positionId.slice(0, 8)}
        </Typography>
      </Box>
      <Box>
        <Typography variant="caption" color="text.secondary">
          {t('tables.positions.instrument')}
        </Typography>
        <Typography variant="body2">{instrument}</Typography>
      </Box>
      <Box>
        <Typography variant="caption" color="text.secondary">
          Direction
        </Typography>
        <Chip
          label={direction}
          size="small"
          color={
            direction === 'LONG' || direction === 'long' ? 'success' : 'error'
          }
        />
      </Box>
      {entryPrice && (
        <Box>
          <Typography variant="caption" color="text.secondary">
            {t('tables.positions.openPrice')}
          </Typography>
          <Typography variant="body2">
            ¥{parseFloat(entryPrice).toFixed(3)}
          </Typography>
        </Box>
      )}
      {isClosed && exitPrice && (
        <Box>
          <Typography variant="caption" color="text.secondary">
            {t('tables.positions.closePrice')}
          </Typography>
          <Typography variant="body2">
            ¥{parseFloat(exitPrice).toFixed(3)}
          </Typography>
        </Box>
      )}
      {isClosed && computedPnl != null && (
        <Box>
          <Typography variant="caption" color="text.secondary">
            {t('tables.positions.realizedPnl')}
          </Typography>
          <Typography
            variant="body2"
            fontWeight="bold"
            color={computedPnl >= 0 ? 'success.main' : 'error.main'}
          >
            {computedPnl >= 0 ? '+' : ''}¥{computedPnl.toFixed(2)}
          </Typography>
        </Box>
      )}
      {plannedExitPrice && (
        <Box>
          <Typography variant="caption" color="text.secondary">
            {t('tables.positions.plannedExitPrice')}
          </Typography>
          <Typography variant="body2">
            ¥{parseFloat(plannedExitPrice).toFixed(3)}
          </Typography>
        </Box>
      )}
      {plannedExitFormula && (
        <Box>
          <Typography variant="caption" color="text.secondary">
            {t('tables.positions.plannedExitPriceFormula')}
          </Typography>
          <Typography variant="body2" fontFamily="monospace" fontSize="0.8rem">
            {plannedExitFormula}
          </Typography>
        </Box>
      )}
      <Box>
        <Typography variant="caption" color="text.secondary">
          Status
        </Typography>
        <Chip
          label={isClosed ? 'CLOSED' : 'OPEN'}
          size="small"
          color={isClosed ? 'default' : 'info'}
        />
      </Box>
    </Box>
  );
};

/** Renders detail fields from lifecycle log context. */
const LifecycleDetails: React.FC<{
  ctx: Record<string, unknown> | undefined;
  positionData?: TaskPosition | null;
}> = ({ ctx, positionData }) => {
  if (!ctx) return null;

  const formula =
    (ctx.planned_exit_price_formula as string | undefined) ??
    positionData?.planned_exit_price_formula ??
    undefined;

  const fields: [string, string | undefined][] = [
    [
      'Units',
      ctx.units != null
        ? String(ctx.units)
        : ctx.units_closed != null
          ? String(ctx.units_closed)
          : undefined,
    ],
    ['Layer', ctx.layer_index != null ? String(ctx.layer_index) : undefined],
    [
      'Retracement',
      ctx.retracement_count != null ? String(ctx.retracement_count) : undefined,
    ],
    ['Exit Formula', formula != null ? String(formula) : undefined],
    ['Close Reason', ctx.close_reason as string | undefined],
    ['Description', ctx.description as string | undefined],
  ];

  const rendered = fields.filter(
    ([, v]) => v != null && v !== '' && v !== 'None'
  );
  if (rendered.length === 0) return null;

  return (
    <Box sx={{ mt: 0.5 }}>
      {rendered.map(([label, value]) => (
        <Typography
          key={label}
          variant="caption"
          color="text.secondary"
          display="block"
        >
          {label}: {value}
        </Typography>
      ))}
    </Box>
  );
};

export default PositionLifecycleDialog;
