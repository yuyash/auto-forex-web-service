import { useMemo, useState } from 'react';
import VisibilityIcon from '@mui/icons-material/Visibility';
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import type {
  BacktestInitialPosition,
  BacktestInitialPositionCycle,
  BacktestInitialPositionStatus,
} from '../../../types/backtestTask';
import { spacingTokens, typographyTokens } from '../../../theme/density';

interface InitialPositionSettingValueProps {
  value: unknown;
  executionId?: string | null;
}

interface InitialPositionSummary {
  cycles: number;
  positions: number;
  open: number;
  closed: number;
  closedSlot: number;
  pendingRebuild: number;
}

export function selectInitialPositionSettingValue(
  value: unknown,
  context: {
    snapshot?: Record<string, unknown> | null;
    source: Record<string, unknown>;
  }
): unknown {
  const snapshotHasInitialPositionCycles =
    context.snapshot &&
    Object.prototype.hasOwnProperty.call(
      context.source,
      'initial_position_cycles'
    );

  if (
    context.snapshot &&
    !snapshotHasInitialPositionCycles &&
    value === undefined
  ) {
    return [];
  }

  return value;
}

const STATUS_CHIP_COLORS: Record<
  BacktestInitialPositionStatus,
  'default' | 'info' | 'success' | 'warning'
> = {
  open: 'success',
  closed: 'default',
  closed_slot: 'info',
  pending_rebuild: 'warning',
};

export function InitialPositionSettingValue({
  value,
  executionId,
}: InitialPositionSettingValueProps) {
  const { t } = useTranslation(['backtest', 'common']);
  const [open, setOpen] = useState(false);
  const cycles = useMemo(() => normalizeInitialPositionCycles(value), [value]);
  const summary = useMemo(
    () => summarizeInitialPositionCycles(cycles),
    [cycles]
  );
  const summaryLabel = t('backtest:form.initialPositionsSummary', {
    defaultValue: '{{cycles}} cycles, {{positions}} positions',
    cycles: summary.cycles,
    positions: summary.positions,
  });

  return (
    <>
      <Stack spacing={0.75} alignItems="flex-start" sx={{ minWidth: 0 }}>
        <Typography
          variant={typographyTokens.body}
          sx={{ overflowWrap: 'anywhere', whiteSpace: 'pre-wrap' }}
        >
          {summaryLabel}
        </Typography>
        {summary.positions > 0 ? (
          <Button
            size="small"
            variant="outlined"
            startIcon={<VisibilityIcon fontSize="small" />}
            onClick={() => setOpen(true)}
            aria-haspopup="dialog"
          >
            {t('backtest:form.initialPositionDetails', 'View details')}
          </Button>
        ) : null}
      </Stack>
      <InitialPositionDetailsDialog
        open={open}
        onClose={() => setOpen(false)}
        cycles={cycles}
        executionId={executionId}
        summary={summary}
      />
    </>
  );
}

export function normalizeInitialPositionCycles(
  value: unknown
): BacktestInitialPositionCycle[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter(isRecord).map((cycle) => ({
    direction: normalizeDirection(cycle.direction),
    positions: Array.isArray(cycle.positions)
      ? cycle.positions.filter(isRecord).map(normalizeInitialPosition)
      : [],
  }));
}

export function summarizeInitialPositionCycles(
  cycles: BacktestInitialPositionCycle[]
): InitialPositionSummary {
  return cycles.reduce<InitialPositionSummary>(
    (summary, cycle) => {
      summary.cycles += 1;
      for (const position of cycle.positions) {
        summary.positions += 1;
        if (position.status === 'open') summary.open += 1;
        if (position.status === 'closed') summary.closed += 1;
        if (position.status === 'closed_slot') summary.closedSlot += 1;
        if (position.status === 'pending_rebuild') summary.pendingRebuild += 1;
      }
      return summary;
    },
    {
      cycles: 0,
      positions: 0,
      open: 0,
      closed: 0,
      closedSlot: 0,
      pendingRebuild: 0,
    }
  );
}

interface InitialPositionDetailsDialogProps {
  open: boolean;
  onClose: () => void;
  cycles: BacktestInitialPositionCycle[];
  executionId?: string | null;
  summary: InitialPositionSummary;
}

function InitialPositionDetailsDialog({
  open,
  onClose,
  cycles,
  executionId,
  summary,
}: InitialPositionDetailsDialogProps) {
  const { t } = useTranslation(['backtest', 'common']);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      fullWidth
      maxWidth="lg"
      scroll="paper"
      aria-labelledby="initial-position-settings-title"
    >
      <DialogTitle id="initial-position-settings-title">
        {t(
          'backtest:form.initialPositionDetailsTitle',
          'Initial position settings'
        )}
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={spacingTokens.md}>
          <Stack spacing={spacingTokens.xs}>
            <Typography
              variant={typographyTokens.body}
              color="text.secondary"
              sx={{ overflowWrap: 'anywhere' }}
            >
              {executionId
                ? t('backtest:form.initialPositionExecutionId', {
                    defaultValue: 'Execution ID: {{executionId}}',
                    executionId,
                  })
                : t(
                    'backtest:form.initialPositionNoExecutionId',
                    'Execution ID is not available.'
                  )}
            </Typography>
            <Stack direction="row" spacing={spacingTokens.xs} flexWrap="wrap">
              <Chip
                size="small"
                label={t('backtest:form.initialPositionDetailsSummary', {
                  defaultValue: '{{cycles}} cycles / {{positions}} positions',
                  cycles: summary.cycles,
                  positions: summary.positions,
                })}
              />
              <Chip
                size="small"
                color="success"
                label={t('backtest:form.initialPositionDetailsOpen', {
                  defaultValue: 'Open {{count}}',
                  count: summary.open,
                })}
              />
              <Chip
                size="small"
                label={t('backtest:form.initialPositionDetailsClosed', {
                  defaultValue: 'Closed {{count}}',
                  count: summary.closed,
                })}
              />
              <Chip
                size="small"
                color="info"
                label={t('backtest:form.initialPositionDetailsClosedSlot', {
                  defaultValue: 'Closed slots {{count}}',
                  count: summary.closedSlot,
                })}
              />
              <Chip
                size="small"
                color="warning"
                label={t('backtest:form.initialPositionDetailsPendingRebuild', {
                  defaultValue: 'Pending rebuild {{count}}',
                  count: summary.pendingRebuild,
                })}
              />
            </Stack>
          </Stack>

          {summary.positions === 0 ? (
            <Alert severity="info">
              {t(
                'backtest:form.initialPositionNoDetails',
                'No initial position settings are recorded for this execution.'
              )}
            </Alert>
          ) : (
            cycles.map((cycle, index) => (
              <Box
                key={`${cycle.direction}-${index}`}
                sx={{
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: 1,
                  overflow: 'hidden',
                }}
              >
                <Box sx={{ px: 1.5, py: 1, bgcolor: 'action.hover' }}>
                  <Typography variant={typographyTokens.subsectionTitle}>
                    {t('backtest:form.initialPositionCycleHeading', {
                      defaultValue: 'Cycle {{cycle}} - {{direction}}',
                      cycle: index + 1,
                      direction: formatDirection(cycle.direction, t),
                    })}
                  </Typography>
                </Box>
                <TableContainer>
                  <Table size="small" aria-label={cycleTableLabel(index, t)}>
                    <TableHead>
                      <TableRow>
                        <TableCell>
                          {t('backtest:form.initialPositionSlot', 'Slot')}
                        </TableCell>
                        <TableCell>
                          {t('common:strategy.summary.status', 'Status')}
                        </TableCell>
                        <TableCell align="right">
                          {t('backtest:form.units', 'Units')}
                        </TableCell>
                        <TableCell align="right">
                          {t('backtest:form.entryPrice', 'Entry Price')}
                        </TableCell>
                        <TableCell align="right">
                          {t('backtest:form.plannedExitPrice', 'Planned exit')}
                        </TableCell>
                        <TableCell align="right">
                          {t('backtest:form.stopLossPrice', 'Stop loss')}
                        </TableCell>
                        <TableCell align="right">
                          {t('backtest:form.exitPrice', 'Exit')}
                        </TableCell>
                        <TableCell>
                          {t('backtest:form.closeReason', 'Close reason')}
                        </TableCell>
                        <TableCell>
                          {t(
                            'backtest:form.initialPositionOandaTradeId',
                            'OANDA trade ID'
                          )}
                        </TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {cycle.positions.map((position, positionIndex) => (
                        <TableRow
                          key={`${position.layer_number}-${position.retracement_count}-${positionIndex}`}
                        >
                          <TableCell>
                            {formatSlot(
                              position.layer_number,
                              position.retracement_count
                            )}
                          </TableCell>
                          <TableCell>
                            <Chip
                              size="small"
                              color={STATUS_CHIP_COLORS[position.status]}
                              label={formatPositionStatus(position.status, t)}
                            />
                          </TableCell>
                          <TableCell align="right">
                            {formatCellValue(position.units)}
                          </TableCell>
                          <TableCell align="right">
                            {formatCellValue(position.entry_price)}
                          </TableCell>
                          <TableCell align="right">
                            {formatCellValue(position.planned_exit_price)}
                          </TableCell>
                          <TableCell align="right">
                            {formatCellValue(position.stop_loss_price)}
                          </TableCell>
                          <TableCell align="right">
                            {formatCellValue(position.exit_price)}
                          </TableCell>
                          <TableCell>
                            {formatCellValue(position.close_reason)}
                          </TableCell>
                          <TableCell>
                            {formatCellValue(position.oanda_trade_id)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Box>
            ))
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('common:actions.close')}</Button>
      </DialogActions>
    </Dialog>
  );
}

function normalizeInitialPosition(
  position: Record<string, unknown>
): BacktestInitialPosition {
  return {
    layer_number: scalarValue(position.layer_number),
    retracement_count: scalarValue(position.retracement_count),
    units: optionalScalarValue(position.units),
    entry_price: optionalScalarValue(position.entry_price),
    planned_exit_price: optionalScalarValue(position.planned_exit_price),
    stop_loss_price: optionalScalarValue(position.stop_loss_price),
    status: normalizeStatus(position.status),
    exit_price: optionalScalarValue(position.exit_price),
    close_reason: stringValue(position.close_reason),
    oanda_trade_id: stringValue(position.oanda_trade_id),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function normalizeDirection(value: unknown): 'long' | 'short' {
  return value === 'short' ? 'short' : 'long';
}

function normalizeStatus(value: unknown): BacktestInitialPositionStatus {
  if (
    value === 'open' ||
    value === 'closed' ||
    value === 'closed_slot' ||
    value === 'pending_rebuild'
  ) {
    return value;
  }
  return 'open';
}

function scalarValue(value: unknown): string | number {
  if (typeof value === 'number' || typeof value === 'string') {
    return value;
  }
  return '';
}

function optionalScalarValue(value: unknown): string | number | null {
  if (value == null || value === '') {
    return null;
  }
  if (typeof value === 'number' || typeof value === 'string') {
    return value;
  }
  return String(value);
}

function stringValue(value: unknown): string {
  if (value == null) {
    return '';
  }
  return String(value);
}

function formatCellValue(value: unknown): string {
  if (value == null || value === '') {
    return '-';
  }
  return String(value);
}

function formatSlot(layer: unknown, retracement: unknown): string {
  return `L${formatCellValue(layer)}/R${formatCellValue(retracement)}`;
}

function formatDirection(
  direction: 'long' | 'short',
  t: ReturnType<typeof useTranslation>['t']
): string {
  return t(`common:strategy.labels.${direction}`, {
    defaultValue: direction === 'long' ? 'Long' : 'Short',
  });
}

function formatPositionStatus(
  status: BacktestInitialPositionStatus,
  t: ReturnType<typeof useTranslation>['t']
): string {
  const key =
    status === 'closed_slot'
      ? 'closedSlot'
      : status === 'pending_rebuild'
        ? 'pendingRebuild'
        : status;
  return t(`backtest:form.initialPositionStatus.${key}`, status);
}

function cycleTableLabel(
  index: number,
  t: ReturnType<typeof useTranslation>['t']
): string {
  return t('backtest:form.initialPositionCycleTableLabel', {
    defaultValue: 'Initial position cycle {{cycle}}',
    cycle: index + 1,
  });
}
