import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Chip,
  Divider,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import { LineStyle } from 'lightweight-charts';
import type {
  CycleTrade,
  NetGridLedgerEntry,
  NetGridStrategyState,
} from '../../../../types/strategyVisualization';
import type { TaskType } from '../../../../types/common';
import { formatAppNumber } from '../../../../utils/numberFormat';
import { useTranslation } from 'react-i18next';
import {
  StrategyGroupChart,
  type StrategyPriceLine,
} from './StrategyGroupChart';

interface NetGridStrategyPanelProps {
  state?: NetGridStrategyState | null;
  instrument: string;
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  lastTickTimestamp?: string | null;
}

function formatUnits(value?: number | null): string {
  return formatAppNumber(value ?? 0, {
    maximumFractionDigits: 0,
    signed: true,
  });
}

function formatPrice(value?: string | null): string {
  if (!value) return '-';
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return value;
  return formatAppNumber(numeric, { maximumFractionDigits: 5 });
}

function formatPips(value?: string | null): string {
  if (!value) return '-';
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return value;
  return formatAppNumber(numeric, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
    signed: true,
  });
}

function formatPercent(value?: string | null): string {
  if (!value) return '-';
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return value;
  return `${formatAppNumber(numeric * 100, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}%`;
}

function directionIcon(units?: number) {
  if (!units) return <SwapHorizIcon fontSize="small" />;
  return units > 0 ? (
    <TrendingUpIcon fontSize="small" />
  ) : (
    <TrendingDownIcon fontSize="small" />
  );
}

function ledgerRows(entries?: NetGridLedgerEntry[]): NetGridLedgerEntry[] {
  return [...(entries ?? [])].reverse().slice(0, 12);
}

function ledgerEntryId(entry: NetGridLedgerEntry): string {
  return String(
    entry.broker_transaction_id ??
      entry.broker_order_id ??
      `${entry.timestamp ?? 'ledger'}-${entry.action}-${entry.units_delta}-${entry.filled_price ?? ''}`
  );
}

function numericPrice(value?: string | null): number | null {
  if (!value) return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function ledgerToTrades(
  entries: NetGridLedgerEntry[] | undefined,
  options: { fills: boolean; sync: boolean }
): CycleTrade[] {
  return (entries ?? [])
    .filter((entry) => {
      if (!entry.timestamp) return false;
      const isSync =
        entry.action === 'broker_backfill' ||
        entry.action === 'broker_reconciliation' ||
        entry.source === 'broker_transaction_history' ||
        entry.source === 'broker_reconciliation';
      return isSync ? options.sync : options.fills;
    })
    .map((entry) => {
      const unitsDelta = entry.units_delta ?? 0;
      const isSync =
        entry.action === 'broker_backfill' ||
        entry.action === 'broker_reconciliation' ||
        entry.source === 'broker_transaction_history' ||
        entry.source === 'broker_reconciliation';
      const isClose =
        entry.action === 'take_profit' ||
        entry.action === 'risk_exit' ||
        Math.abs(entry.net_units_after ?? 0) <
          Math.abs(entry.net_units_before ?? 0);
      return {
        id: ledgerEntryId(entry),
        direction: unitsDelta >= 0 ? 'buy' : 'sell',
        units: Math.abs(unitsDelta),
        price: entry.filled_price ?? '',
        execution_method: isSync
          ? entry.action
          : isClose
            ? 'close_position'
            : 'open_position',
        description: `${entry.action}: ${entry.reason ?? entry.source ?? ''}`,
        timestamp: entry.timestamp ?? null,
        position_id: null,
        pnl: entry.realized_pnl ?? null,
      };
    });
}

function chartStartTime(state?: NetGridStrategyState | null): string | null {
  const ledgerStart = state?.grid_ledger?.find(
    (entry) => entry.timestamp
  )?.timestamp;
  return ledgerStart ?? state?.started_at ?? state?.last_tick_at ?? null;
}

export function NetGridStrategyPanel({
  state,
  instrument,
  taskId,
  taskType,
  executionRunId,
  lastTickTimestamp,
}: NetGridStrategyPanelProps) {
  const { t } = useTranslation('strategy');
  const [selectedLedgerId, setSelectedLedgerId] = useState<string | null>(null);
  const [visibleOverlays, setVisibleOverlays] = useState({
    fills: true,
    sync: true,
    averageEntry: true,
    takeProfit: true,
    lastGrid: true,
    nextGrid: true,
  });
  const currentNet = state?.current_net_units ?? 0;
  const latestDecision = state?.latest_decision;
  const rows = ledgerRows(state?.grid_ledger);
  const auditRows = useMemo(
    () =>
      [...(state?.grid_ledger ?? [])]
        .reverse()
        .filter(
          (entry) =>
            entry.broker_transaction_id ||
            entry.broker_order_id ||
            entry.oanda_trade_id ||
            entry.source === 'broker_transaction_history' ||
            entry.source === 'broker_reconciliation'
        )
        .slice(0, 20),
    [state?.grid_ledger]
  );
  const trades = useMemo(
    () =>
      ledgerToTrades(state?.grid_ledger, {
        fills: visibleOverlays.fills,
        sync: visibleOverlays.sync,
      }),
    [state?.grid_ledger, visibleOverlays.fills, visibleOverlays.sync]
  );
  const startTime = chartStartTime(state);
  const endTime = lastTickTimestamp ?? state?.last_tick_at ?? null;
  const selectedTradeIds = useMemo(
    () => (selectedLedgerId ? new Set([selectedLedgerId]) : undefined),
    [selectedLedgerId]
  );
  const syncStatus = state?.broker_reconciliation_status;
  const priceLines: StrategyPriceLine[] = [
    {
      price: numericPrice(state?.average_entry_price) ?? Number.NaN,
      title: t('netGrid.chart.averageEntry'),
      color: '#1976d2',
      lineStyle: LineStyle.Solid,
    },
    {
      price: numericPrice(state?.net_take_profit_price) ?? Number.NaN,
      title: t('netGrid.chart.takeProfit'),
      color: '#2e7d32',
      lineStyle: LineStyle.Dashed,
    },
    {
      price: numericPrice(state?.last_grid_price) ?? Number.NaN,
      title: t('netGrid.chart.lastGrid'),
      color: '#f57c00',
      lineStyle: LineStyle.Dotted,
    },
    {
      price: numericPrice(state?.next_grid_price) ?? Number.NaN,
      title: t('netGrid.chart.nextGrid'),
      color: '#d32f2f',
      lineStyle: LineStyle.Dashed,
    },
  ].filter((line) => {
    if (line.title === t('netGrid.chart.averageEntry')) {
      return visibleOverlays.averageEntry;
    }
    if (line.title === t('netGrid.chart.takeProfit')) {
      return visibleOverlays.takeProfit;
    }
    if (line.title === t('netGrid.chart.lastGrid')) {
      return visibleOverlays.lastGrid;
    }
    if (line.title === t('netGrid.chart.nextGrid')) {
      return visibleOverlays.nextGrid;
    }
    return true;
  });
  const toggleOverlay = (key: keyof typeof visibleOverlays) => {
    setVisibleOverlays((current) => ({ ...current, [key]: !current[key] }));
  };

  return (
    <Stack spacing={2}>
      {!state && <Alert severity="info">{t('netGrid.noState')}</Alert>}
      {syncStatus === 'blocked' ? (
        <Alert severity="error">{t('netGrid.alerts.syncBlocked')}</Alert>
      ) : syncStatus === 'warning' ? (
        <Alert severity="warning">{t('netGrid.alerts.syncWarning')}</Alert>
      ) : null}

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack spacing={1.5}>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            justifyContent="space-between"
            spacing={1}
          >
            <Box>
              <Typography variant="h6">{t('netGrid.summary.title')}</Typography>
              <Typography variant="body2" color="text.secondary">
                {t('netGrid.summary.description')}
              </Typography>
            </Box>
            <Chip
              size="small"
              icon={directionIcon(currentNet)}
              label={
                currentNet > 0
                  ? t('netGrid.directions.netLong')
                  : currentNet < 0
                    ? t('netGrid.directions.netShort')
                    : t('netGrid.directions.flat')
              }
              variant="outlined"
            />
          </Stack>

          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: '1fr',
                sm: 'repeat(2, minmax(0, 1fr))',
                md: 'repeat(4, minmax(0, 1fr))',
              },
              gap: 1,
            }}
          >
            <SummaryItem
              label={t('netGrid.summary.currentNet')}
              value={formatUnits(currentNet)}
            />
            <SummaryItem
              label={t('netGrid.summary.averageEntry')}
              value={formatPrice(state?.average_entry_price)}
            />
            <SummaryItem
              label={t('netGrid.summary.step')}
              value={t('netGrid.summary.stepValue', {
                step: state?.step ?? 0,
                max: state?.max_steps ?? '-',
                usage: formatPercent(state?.step_usage),
              })}
            />
            <SummaryItem
              label={t('netGrid.summary.lastGridPrice')}
              value={formatPrice(state?.last_grid_price)}
            />
            <SummaryItem
              label={t('netGrid.summary.takeProfitPrice')}
              value={formatPrice(state?.net_take_profit_price)}
            />
            <SummaryItem
              label={t('netGrid.summary.takeProfitRemaining')}
              value={formatPips(state?.take_profit_remaining_pips)}
            />
            <SummaryItem
              label={t('netGrid.summary.nextGridPrice')}
              value={formatPrice(state?.next_grid_price)}
            />
            <SummaryItem
              label={t('netGrid.summary.lastBackfilledTransaction')}
              value={String(
                state?.broker_last_backfilled_transaction_id ?? '-'
              )}
            />
            <SummaryItem
              label={t('netGrid.summary.brokerSyncStatus')}
              value={state?.broker_reconciliation_status ?? '-'}
            />
            <SummaryItem
              label={t('netGrid.summary.brokerSyncedAt')}
              value={state?.broker_reconciled_at ?? '-'}
            />
          </Box>

          <Divider />
          <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
            <Chip
              size="small"
              label={t('netGrid.summary.backfilledFills', {
                count: state?.broker_backfilled_fill_count ?? 0,
              })}
              variant="outlined"
            />
            <Chip
              size="small"
              label={t('netGrid.summary.openTrades', {
                count: state?.broker_open_trade_count ?? 0,
              })}
              variant="outlined"
            />
            <Chip
              size="small"
              label={t('netGrid.summary.pendingOrders', {
                count: state?.broker_pending_order_count ?? 0,
              })}
              color={
                (state?.broker_pending_order_count ?? 0) > 0
                  ? 'warning'
                  : 'default'
              }
              variant="outlined"
            />
          </Stack>

          {latestDecision && (
            <Alert severity="info" variant="outlined">
              {t('netGrid.latestDecision', {
                action: latestDecision.action,
                reason: latestDecision.reason,
                units: formatUnits(latestDecision.units_delta),
              })}
            </Alert>
          )}
        </Stack>
      </Paper>

      {startTime && instrument ? (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={1.5}>
            <Box>
              <Typography variant="h6">{t('netGrid.chart.title')}</Typography>
              <Typography variant="body2" color="text.secondary">
                {t('netGrid.chart.description')}
              </Typography>
            </Box>
            <StrategyGroupChart
              instrument={instrument}
              startTime={startTime}
              endTime={endTime}
              trades={trades}
              height={360}
              taskId={taskId}
              taskType={taskType}
              executionRunId={executionRunId}
              lastTickTimestamp={lastTickTimestamp}
              priceLines={priceLines}
              selectedTradeIds={selectedTradeIds}
              focusedTradeId={selectedLedgerId}
              onMarkerClick={setSelectedLedgerId}
            />
            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
              <LegendChip
                color="#1976d2"
                label={t('netGrid.chart.averageEntry')}
                active={visibleOverlays.averageEntry}
                onClick={() => toggleOverlay('averageEntry')}
              />
              <LegendChip
                color="#2e7d32"
                label={t('netGrid.chart.takeProfit')}
                active={visibleOverlays.takeProfit}
                onClick={() => toggleOverlay('takeProfit')}
              />
              <LegendChip
                color="#f57c00"
                label={t('netGrid.chart.lastGrid')}
                active={visibleOverlays.lastGrid}
                onClick={() => toggleOverlay('lastGrid')}
              />
              <LegendChip
                color="#d32f2f"
                label={t('netGrid.chart.nextGrid')}
                active={visibleOverlays.nextGrid}
                onClick={() => toggleOverlay('nextGrid')}
              />
              <LegendChip
                color="#26a69a"
                label={t('netGrid.chart.fillMarkers')}
                active={visibleOverlays.fills}
                onClick={() => toggleOverlay('fills')}
              />
              <LegendChip
                color="#7b1fa2"
                label={t('netGrid.chart.syncMarkers')}
                active={visibleOverlays.sync}
                onClick={() => toggleOverlay('sync')}
              />
            </Stack>
          </Stack>
        </Paper>
      ) : null}

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack spacing={1.5}>
          <Box>
            <Typography variant="h6">{t('netGrid.ledger.title')}</Typography>
            <Typography variant="body2" color="text.secondary">
              {t('netGrid.ledger.description')}
            </Typography>
          </Box>

          {rows.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              {t('netGrid.ledger.empty')}
            </Typography>
          ) : (
            <Box sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t('netGrid.ledger.action')}</TableCell>
                    <TableCell align="right">
                      {t('netGrid.ledger.unitsDelta')}
                    </TableCell>
                    <TableCell align="right">
                      {t('netGrid.ledger.fill')}
                    </TableCell>
                    <TableCell align="right">
                      {t('netGrid.ledger.netAfter')}
                    </TableCell>
                    <TableCell align="right">
                      {t('netGrid.ledger.pnl')}
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((entry, index) => {
                    const id = ledgerEntryId(entry);
                    const selected = selectedLedgerId === id;
                    return (
                      <TableRow
                        key={`${id}-${index}`}
                        hover
                        selected={selected}
                        onClick={() =>
                          setSelectedLedgerId(selected ? null : id)
                        }
                        sx={{ cursor: 'pointer' }}
                      >
                        <TableCell>
                          <Stack spacing={0.25}>
                            <Typography variant="body2">
                              {entry.action}
                            </Typography>
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              {entry.reason ?? entry.source ?? '-'}
                            </Typography>
                          </Stack>
                        </TableCell>
                        <TableCell align="right">
                          {formatUnits(entry.units_delta)}
                        </TableCell>
                        <TableCell align="right">
                          {formatPrice(entry.filled_price)}
                        </TableCell>
                        <TableCell align="right">
                          {formatUnits(entry.net_units_after)}
                        </TableCell>
                        <TableCell align="right">
                          {formatPrice(entry.realized_pnl)}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </Box>
          )}
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack spacing={1.5}>
          <Box>
            <Typography variant="h6">{t('netGrid.audit.title')}</Typography>
            <Typography variant="body2" color="text.secondary">
              {t('netGrid.audit.description')}
            </Typography>
          </Box>
          {auditRows.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              {t('netGrid.audit.empty')}
            </Typography>
          ) : (
            <Box sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t('netGrid.audit.action')}</TableCell>
                    <TableCell>{t('netGrid.audit.transaction')}</TableCell>
                    <TableCell>{t('netGrid.audit.order')}</TableCell>
                    <TableCell>{t('netGrid.audit.trade')}</TableCell>
                    <TableCell align="right">
                      {t('netGrid.audit.units')}
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {auditRows.map((entry, index) => (
                    <TableRow key={`${ledgerEntryId(entry)}-audit-${index}`}>
                      <TableCell>
                        <Stack spacing={0.25}>
                          <Typography variant="body2">
                            {entry.action}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {entry.timestamp ?? '-'}
                          </Typography>
                        </Stack>
                      </TableCell>
                      <TableCell>
                        {entry.broker_transaction_id ?? '-'}
                      </TableCell>
                      <TableCell>{entry.broker_order_id ?? '-'}</TableCell>
                      <TableCell>{entry.oanda_trade_id ?? '-'}</TableCell>
                      <TableCell align="right">
                        {formatUnits(entry.units_delta)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          )}
        </Stack>
      </Paper>
    </Stack>
  );
}

function LegendChip({
  color,
  label,
  active,
  onClick,
}: {
  color: string;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <Chip
      size="small"
      variant={active ? 'outlined' : 'filled'}
      label={label}
      onClick={onClick}
      icon={
        <Box
          component="span"
          sx={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            bgcolor: color,
          }}
        />
      }
    />
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <Box
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        p: 1.25,
        minWidth: 0,
      }}
    >
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="subtitle1" sx={{ overflowWrap: 'anywhere' }}>
        {value}
      </Typography>
    </Box>
  );
}
