import {
  Add as AddIcon,
  Delete as DeleteIcon,
  RemoveCircleOutline as RemoveIcon,
} from '@mui/icons-material';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import type { TickDataPoint } from '../../services/api/market';
import type {
  BacktestInitialPosition,
  BacktestInitialPositionCycle,
  BacktestInitialPositionStatus,
} from '../../types/backtestTask';
import type { StrategyConfig } from '../../types/configuration';

interface BacktestInitialPositionsEditorProps {
  enabled: boolean;
  onEnabledChange: (enabled: boolean) => void;
  value: BacktestInitialPositionCycle[];
  onChange: (value: BacktestInitialPositionCycle[]) => void;
  selectedConfig?: StrategyConfig;
  strategyType?: string | null;
  pipSize?: number | string;
  firstTick?: TickDataPoint | null;
  firstTickLoading?: boolean;
  firstTickError?: string | null;
  error?: string;
}

interface InitialPositionOrderWarning {
  type: 'order' | 'duplicate';
  cycleNumber: number;
  rowNumber: number;
  expected?: string;
  actual: string;
}

export function BacktestInitialPositionsEditor({
  enabled,
  onEnabledChange,
  value,
  onChange,
  selectedConfig,
  strategyType,
  pipSize,
  firstTick,
  firstTickLoading = false,
  firstTickError,
  error,
}: BacktestInitialPositionsEditorProps) {
  const { t } = useTranslation(['backtest', 'common']);
  const resolvedStrategyType = normalizedStrategyType(
    strategyType ?? selectedConfig?.strategy_type
  );
  const strategyTypeKnown = resolvedStrategyType.length > 0;
  const isSnowball = resolvedStrategyType === 'snowball';
  const canUseInitialPositions = !strategyTypeKnown || isSnowball;
  const config = useMemo(
    () => snowballConfig(selectedConfig, pipSize),
    [selectedConfig, pipSize]
  );
  const orderWarnings = useMemo(
    () => initialPositionOrderWarnings(value, config.rMax),
    [config.rMax, value]
  );

  useEffect(() => {
    if (strategyTypeKnown && !isSnowball && enabled) {
      onEnabledChange(false);
      onChange([]);
    }
  }, [enabled, isSnowball, onChange, onEnabledChange, strategyTypeKnown]);

  useEffect(() => {
    if (!enabled || !canUseInitialPositions || value.length === 0) {
      return;
    }

    const next = normalizeCyclesForConfig(value, config);
    if (!sameInitialPositionCycles(value, next)) {
      onChange(next);
    }
  }, [canUseInitialPositions, config, enabled, onChange, value]);

  const updateCycle = (
    cycleIndex: number,
    updater: (
      cycle: BacktestInitialPositionCycle
    ) => BacktestInitialPositionCycle
  ) => {
    onChange(
      value.map((cycle, i) => (i === cycleIndex ? updater(cycle) : cycle))
    );
  };

  const addCycle = (direction: 'long' | 'short') => {
    onChange([...value, { direction, positions: [] }]);
  };

  const removeCycle = (cycleIndex: number) => {
    onChange(value.filter((_, i) => i !== cycleIndex));
  };

  const addPosition = (cycleIndex: number) => {
    updateCycle(cycleIndex, (cycle) => {
      const slot = nextSlot(cycle.positions.length, config.rMax);
      if (slot.layer > config.fMax) {
        return cycle;
      }
      const position = withDefaultPrices(
        {
          layer_number: slot.layer,
          retracement_count: slot.retracement,
          units: defaultUnits(
            slot.retracement,
            config.baseUnits,
            config.trendLotSize
          ),
          entry_price: '',
          status: 'open',
          close_reason: '',
        },
        cycle,
        config
      );
      return { ...cycle, positions: [...cycle.positions, position] };
    });
  };

  const removeLastPosition = (cycleIndex: number) => {
    updateCycle(cycleIndex, (cycle) => ({
      ...cycle,
      positions: cycle.positions.slice(0, -1),
    }));
  };

  return (
    <Box>
      <FormControlLabel
        control={
          <Checkbox
            checked={enabled}
            onChange={(event) => onEnabledChange(event.target.checked)}
            disabled={!canUseInitialPositions}
          />
        }
        label={
          <Box>
            <Typography variant="body1">
              {t('backtest:form.initialPositionsEnabled', {
                defaultValue: 'Create initial positions',
              })}
            </Typography>
            {strategyTypeKnown && !isSnowball ? (
              <Typography variant="body2" color="text.secondary">
                {t('backtest:form.initialPositionsSnowballOnly', {
                  defaultValue:
                    'Available only when the Snowball strategy is selected.',
                })}
              </Typography>
            ) : null}
          </Box>
        }
      />

      {enabled && canUseInitialPositions ? (
        <Stack spacing={2} sx={{ mt: 2 }}>
          {error ? (
            <Typography variant="body2" color="error">
              {error}
            </Typography>
          ) : null}

          {orderWarnings.length > 0 ? (
            <Alert severity="warning">
              <Stack spacing={0.5}>
                {orderWarnings.map((warning, index) => (
                  <Typography
                    key={`${warning.type}-${warning.cycleNumber}-${warning.rowNumber}-${warning.actual}-${index}`}
                    variant="body2"
                  >
                    {warning.type === 'duplicate'
                      ? t('backtest:form.initialPositionDuplicateWarning', {
                          defaultValue:
                            'Cycle {{cycle}} has duplicate slot {{actual}}.',
                          cycle: warning.cycleNumber,
                          actual: warning.actual,
                        })
                      : t('backtest:form.initialPositionOrderWarning', {
                          defaultValue:
                            'Cycle {{cycle}}, row {{row}} should be {{expected}}, but is {{actual}}.',
                          cycle: warning.cycleNumber,
                          row: warning.rowNumber,
                          expected: warning.expected,
                          actual: warning.actual,
                        })}
                  </Typography>
                ))}
              </Stack>
            </Alert>
          ) : null}

          <Alert severity={firstTickError ? 'warning' : 'info'}>
            {firstTickLoading
              ? t('backtest:form.firstTickLoading', {
                  defaultValue:
                    'Loading the first tick in the backtest period...',
                })
              : firstTick
                ? t('backtest:form.firstTickPrice', {
                    defaultValue:
                      'First tick: {{timestamp}} / Bid {{bid}} / Ask {{ask}} / Mid {{mid}}',
                    timestamp: formatTickTimestamp(firstTick.timestamp),
                    bid: firstTick.bid,
                    ask: firstTick.ask,
                    mid: firstTick.mid,
                  })
                : t(
                    firstTickError
                      ? 'backtest:form.firstTickLoadFailed'
                      : 'backtest:form.firstTickUnavailable',
                    {
                      defaultValue: firstTickError
                        ? 'Could not load the first tick in the backtest period.'
                        : 'No tick was found in the backtest period.',
                    }
                  )}
          </Alert>

          <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
            <Button
              size="small"
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={() => addCycle('long')}
            >
              {t('backtest:form.addLongCycle', { defaultValue: 'Long cycle' })}
            </Button>
            <Button
              size="small"
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={() => addCycle('short')}
            >
              {t('backtest:form.addShortCycle', {
                defaultValue: 'Short cycle',
              })}
            </Button>
          </Stack>

          {value.map((cycle, cycleIndex) => {
            const slot = nextSlot(cycle.positions.length, config.rMax);
            const canAdd = slot.layer <= config.fMax;
            return (
              <Paper
                key={`${cycle.direction}-${cycleIndex}`}
                variant="outlined"
                sx={{ p: 2, borderRadius: 1 }}
              >
                <Stack spacing={2}>
                  <Stack
                    direction="row"
                    spacing={1}
                    sx={{
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <FormControl size="small" sx={{ minWidth: 160 }}>
                      <InputLabel>
                        {t('common:labels.direction', {
                          defaultValue: 'Direction',
                        })}
                      </InputLabel>
                      <Select
                        label={t('common:labels.direction', {
                          defaultValue: 'Direction',
                        })}
                        value={cycle.direction}
                        onChange={(event) =>
                          updateCycle(cycleIndex, (current) => ({
                            ...current,
                            direction: event.target.value as 'long' | 'short',
                            positions: current.positions.map((position) =>
                              withDefaultPrices(
                                {
                                  ...position,
                                  planned_exit_price: undefined,
                                  stop_loss_price: undefined,
                                  exit_price:
                                    position.status === 'open'
                                      ? undefined
                                      : position.exit_price,
                                },
                                {
                                  ...current,
                                  direction: event.target.value as
                                    | 'long'
                                    | 'short',
                                },
                                config
                              )
                            ),
                          }))
                        }
                      >
                        <MenuItem value="long">
                          {t('common:tables.positions.long', {
                            defaultValue: 'Long',
                          })}
                        </MenuItem>
                        <MenuItem value="short">
                          {t('common:tables.positions.short', {
                            defaultValue: 'Short',
                          })}
                        </MenuItem>
                      </Select>
                    </FormControl>

                    <Tooltip
                      title={t('common:actions.delete', {
                        defaultValue: 'Delete',
                      })}
                    >
                      <IconButton onClick={() => removeCycle(cycleIndex)}>
                        <DeleteIcon />
                      </IconButton>
                    </Tooltip>
                  </Stack>

                  {cycle.positions.map((position, positionIndex) => (
                    <SeedPositionRow
                      key={`${position.layer_number}-${position.retracement_count}`}
                      position={position}
                      onChange={(next) =>
                        updateCycle(cycleIndex, (current) => ({
                          ...current,
                          positions: current.positions.map((item, i) =>
                            i === positionIndex
                              ? normalizePositionForConfig(
                                  withDefaultPrices(next, current, config),
                                  config
                                )
                              : item
                          ),
                        }))
                      }
                      stopLossEnabled={config.stopLossEnabled}
                    />
                  ))}

                  <Stack direction="row" spacing={1}>
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<AddIcon />}
                      disabled={!canAdd}
                      onClick={() => addPosition(cycleIndex)}
                    >
                      {canAdd
                        ? `L${slot.layer}/R${slot.retracement}`
                        : t('backtest:form.gridFull', {
                            defaultValue: 'Grid full',
                          })}
                    </Button>
                    <Button
                      size="small"
                      variant="text"
                      startIcon={<RemoveIcon />}
                      disabled={cycle.positions.length === 0}
                      onClick={() => removeLastPosition(cycleIndex)}
                    >
                      {t('backtest:form.removeLastPosition', {
                        defaultValue: 'Remove last',
                      })}
                    </Button>
                  </Stack>
                </Stack>
              </Paper>
            );
          })}
        </Stack>
      ) : null}
    </Box>
  );
}

function initialPositionOrderWarnings(
  cycles: BacktestInitialPositionCycle[],
  rMax: number
): InitialPositionOrderWarning[] {
  return cycles.flatMap((cycle, cycleIndex) => {
    const seen = new Set<string>();
    return cycle.positions.flatMap((position, positionIndex) => {
      const expected = nextSlot(positionIndex, rMax);
      const expectedLabel = slotLabel(expected.layer, expected.retracement);
      const actualLabel = slotLabel(
        position.layer_number,
        position.retracement_count
      );
      const key = `${position.layer_number}:${position.retracement_count}`;
      const warnings: InitialPositionOrderWarning[] = [];

      if (seen.has(key)) {
        warnings.push({
          type: 'duplicate',
          cycleNumber: cycleIndex + 1,
          rowNumber: positionIndex + 1,
          actual: actualLabel,
        });
      }
      seen.add(key);

      if (
        position.layer_number !== expected.layer ||
        position.retracement_count !== expected.retracement
      ) {
        warnings.push({
          type: 'order',
          cycleNumber: cycleIndex + 1,
          rowNumber: positionIndex + 1,
          expected: expectedLabel,
          actual: actualLabel,
        });
      }

      return warnings;
    });
  });
}

function normalizeCyclesForConfig(
  cycles: BacktestInitialPositionCycle[],
  config: SnowballUiConfig
): BacktestInitialPositionCycle[] {
  return cycles.map((cycle) => {
    const normalizedPositions = cycle.positions.map((position) =>
      normalizePositionForConfig(position, config)
    );
    const normalizedCycle = { ...cycle, positions: normalizedPositions };
    return {
      ...normalizedCycle,
      positions: normalizedPositions.map((position) =>
        normalizePositionForConfig(
          withDefaultPrices(position, normalizedCycle, config),
          config
        )
      ),
    };
  });
}

function normalizePositionForConfig(
  position: BacktestInitialPosition,
  config: SnowballUiConfig
): BacktestInitialPosition {
  if (config.stopLossEnabled) {
    return position;
  }

  if (position.status === 'pending_rebuild') {
    return {
      ...position,
      status: 'open',
      stop_loss_price: undefined,
      exit_price: undefined,
      close_reason: '',
    };
  }

  return {
    ...position,
    stop_loss_price: undefined,
  };
}

function sameInitialPositionCycles(
  left: BacktestInitialPositionCycle[],
  right: BacktestInitialPositionCycle[]
) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function formatTickTimestamp(timestamp: string) {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? timestamp : date.toLocaleString();
}

function SeedPositionRow({
  position,
  onChange,
  stopLossEnabled,
}: {
  position: BacktestInitialPosition;
  onChange: (position: BacktestInitialPosition) => void;
  stopLossEnabled: boolean;
}) {
  const { t } = useTranslation(['backtest', 'common']);
  const rawStatus = position.status ?? 'open';
  const status =
    !stopLossEnabled && rawStatus === 'pending_rebuild' ? 'open' : rawStatus;
  const statusOptions: Array<{
    value: BacktestInitialPositionStatus;
    label: string;
  }> = [
    {
      value: 'open',
      label: t('backtest:form.initialPositionStatus.open'),
    },
    {
      value: 'closed',
      label: t('backtest:form.initialPositionStatus.closed'),
    },
    ...(stopLossEnabled
      ? [
          {
            value: 'pending_rebuild' as const,
            label: t('backtest:form.initialPositionStatus.pendingRebuild'),
          },
        ]
      : []),
  ];

  const update = (patch: Partial<BacktestInitialPosition>) => {
    onChange({ ...position, ...patch });
  };

  return (
    <Box sx={{ borderTop: '1px solid', borderColor: 'divider', pt: 1.5 }}>
      <Grid container spacing={1.5} sx={{ alignItems: 'center' }}>
        <Grid size={{ xs: 12, sm: 1.4 }}>
          <Chip
            size="small"
            label={`L${position.layer_number}/R${position.retracement_count}`}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 1.6 }}>
          <TextField
            fullWidth
            size="small"
            label={t('common:tables.positions.units', {
              defaultValue: 'Units',
            })}
            type="text"
            inputMode="decimal"
            value={position.units ?? ''}
            onChange={(event) =>
              update({
                units: event.target.value,
                planned_exit_price: undefined,
                stop_loss_price: undefined,
                exit_price: status === 'open' ? undefined : position.exit_price,
              })
            }
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 1.8 }}>
          <TextField
            fullWidth
            size="small"
            label={t('common:tables.positions.openPrice', {
              defaultValue: 'Entry',
            })}
            type="text"
            inputMode="decimal"
            value={position.entry_price ?? ''}
            onChange={(event) =>
              update({
                entry_price: event.target.value,
                planned_exit_price: undefined,
                stop_loss_price: undefined,
                exit_price: status === 'open' ? undefined : position.exit_price,
              })
            }
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 1.8 }}>
          <TextField
            fullWidth
            size="small"
            label={t('backtest:form.plannedExitPrice', {
              defaultValue: 'Planned exit',
            })}
            type="text"
            inputMode="decimal"
            value={position.planned_exit_price ?? ''}
            onChange={(event) =>
              update({ planned_exit_price: event.target.value })
            }
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 1.8 }}>
          <TextField
            fullWidth
            size="small"
            label={t('backtest:form.stopLossPrice', {
              defaultValue: 'Stop loss',
            })}
            type="text"
            inputMode="decimal"
            value={stopLossEnabled ? (position.stop_loss_price ?? '') : ''}
            disabled={!stopLossEnabled}
            onChange={(event) =>
              update({ stop_loss_price: event.target.value })
            }
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 1.8 }}>
          <FormControl fullWidth size="small">
            <InputLabel>
              {t('common:tables.positions.status', { defaultValue: 'Status' })}
            </InputLabel>
            <Select
              label={t('common:tables.positions.status', {
                defaultValue: 'Status',
              })}
              value={status}
              onChange={(event) => {
                const nextStatus = event.target
                  .value as BacktestInitialPositionStatus;
                update({
                  status: nextStatus,
                  exit_price:
                    nextStatus === 'open'
                      ? undefined
                      : defaultExitPrice(position, nextStatus),
                  close_reason:
                    nextStatus === 'pending_rebuild'
                      ? 'stop_loss'
                      : nextStatus === 'closed'
                        ? position.close_reason || 'tp'
                        : '',
                });
              }}
            >
              {statusOptions.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>
        {status !== 'open' ? (
          <Grid size={{ xs: 6, sm: 1.8 }}>
            <TextField
              fullWidth
              size="small"
              label={t('backtest:form.exitPrice', { defaultValue: 'Exit' })}
              type="text"
              inputMode="decimal"
              value={position.exit_price ?? ''}
              onChange={(event) => update({ exit_price: event.target.value })}
            />
          </Grid>
        ) : null}
      </Grid>
      {status !== 'open' ? (
        <Box sx={{ mt: 1.5, maxWidth: 260 }}>
          <TextField
            fullWidth
            size="small"
            label={t('backtest:form.closeReason', {
              defaultValue: 'Close reason',
            })}
            value={position.close_reason ?? ''}
            disabled={status === 'pending_rebuild'}
            onChange={(event) => update({ close_reason: event.target.value })}
          />
        </Box>
      ) : null}
    </Box>
  );
}

interface SnowballUiConfig {
  pipSize: number;
  baseUnits: number;
  trendLotSize: number;
  rMax: number;
  fMax: number;
  mPips: number;
  counterTpMode: string;
  counterTpPips: number;
  counterTpStepAmount: number;
  counterTpMultiplier: number;
  stopLossEnabled: boolean;
  stopLossMode: string;
  stopLossPipsHead: number;
  stopLossPipsTail: number;
  stopLossPipsFlatSteps: number;
  stopLossPipsGamma: number;
  stopLossManualPips: number[];
  intervalMode: string;
  manualIntervals: number[];
  roundStepPips: number;
  nPipsHead: number;
  nPipsTail: number;
  nPipsFlatSteps: number;
  nPipsGamma: number;
}

function snowballConfig(
  config?: StrategyConfig,
  pipSize?: number | string
): SnowballUiConfig {
  const params = config?.parameters ?? {};
  const nHead = num(params.n_pips_head, 30);
  const nTail = num(params.n_pips_tail, 14);
  const nFlat = intNum(params.n_pips_flat_steps, 2);
  const nGamma = num(params.n_pips_gamma, 1.4);
  return {
    pipSize: num(pipSize, num(params.pip_size, 0.01)),
    baseUnits: intNum(params.base_units, 1000),
    trendLotSize: intNum(params.trend_lot_size, 1),
    rMax: intNum(params.r_max, 7),
    fMax: intNum(params.f_max, 3),
    mPips: num(params.m_pips, 50),
    counterTpMode: String(params.counter_tp_mode ?? 'weighted_avg'),
    counterTpPips: num(params.counter_tp_pips, 25),
    counterTpStepAmount: num(params.counter_tp_step_amount, 2.5),
    counterTpMultiplier: num(params.counter_tp_multiplier, 1.2),
    stopLossEnabled: boolValue(params.stop_loss_enabled, false),
    stopLossMode: String(params.stop_loss_mode ?? 'auto'),
    stopLossPipsHead: num(params.stop_loss_pips_head, nHead),
    stopLossPipsTail: num(params.stop_loss_pips_tail, nTail),
    stopLossPipsFlatSteps: intNum(params.stop_loss_pips_flat_steps, nFlat),
    stopLossPipsGamma: num(params.stop_loss_pips_gamma, nGamma),
    stopLossManualPips: numericArray(params.stop_loss_manual_pips),
    intervalMode: String(params.interval_mode ?? 'constant'),
    manualIntervals: numericArray(params.manual_intervals),
    roundStepPips: num(params.round_step_pips, 0.1),
    nPipsHead: nHead,
    nPipsTail: nTail,
    nPipsFlatSteps: nFlat,
    nPipsGamma: nGamma,
  };
}

function withDefaultPrices(
  position: BacktestInitialPosition,
  cycle: BacktestInitialPositionCycle,
  config: SnowballUiConfig
): BacktestInitialPosition {
  const entry = num(position.entry_price, NaN);
  if (!Number.isFinite(entry)) {
    return position;
  }
  const planned =
    position.planned_exit_price !== undefined &&
    position.planned_exit_price !== null
      ? position.planned_exit_price
      : defaultTakeProfit(position, cycle, config);
  const stopLoss =
    position.stop_loss_price !== undefined && position.stop_loss_price !== null
      ? position.stop_loss_price
      : defaultStopLoss(
          { ...position, planned_exit_price: planned },
          cycle,
          config
        );
  const status = position.status ?? 'open';
  return {
    ...position,
    planned_exit_price: fixed(planned),
    stop_loss_price: stopLoss == null ? undefined : fixed(stopLoss),
    exit_price:
      status === 'open'
        ? undefined
        : (position.exit_price ??
          defaultExitPrice({ ...position, stop_loss_price: stopLoss }, status)),
  };
}

function defaultTakeProfit(
  position: BacktestInitialPosition,
  cycle: BacktestInitialPositionCycle,
  config: SnowballUiConfig
) {
  const entry = num(position.entry_price, 0);
  const direction = cycle.direction;
  if (position.retracement_count === 0) {
    const raw = addPips(entry, direction, config.mPips, config.pipSize);
    if (position.layer_number <= 1) return raw;
    const bound = [...cycle.positions]
      .reverse()
      .find(
        (p) => p.layer_number === position.layer_number - 1
      )?.planned_exit_price;
    const boundNum = num(bound, NaN);
    if (!Number.isFinite(boundNum)) return raw;
    if (direction === 'long' && raw > boundNum) return boundNum;
    if (direction === 'short' && raw < boundNum) return boundNum;
    return raw;
  }
  if (config.counterTpMode === 'weighted_avg') {
    const prior = cycle.positions.filter(
      (p) =>
        p.layer_number === position.layer_number &&
        p.retracement_count < position.retracement_count
    );
    const currentUnits = num(position.units, 0);
    const totalUnits = prior.reduce(
      (sum, p) => sum + num(p.units, 0),
      currentUnits
    );
    const weighted = prior.reduce(
      (sum, p) => sum + num(p.entry_price, 0) * num(p.units, 0),
      entry * currentUnits
    );
    return totalUnits > 0 ? weighted / totalUnits : entry;
  }
  return addPips(
    entry,
    direction,
    counterTpPips(position.retracement_count, config),
    config.pipSize
  );
}

function defaultStopLoss(
  position: BacktestInitialPosition,
  cycle: BacktestInitialPositionCycle,
  config: SnowballUiConfig
) {
  if (!config.stopLossEnabled) return undefined;
  const entry = num(position.entry_price, 0);
  const direction = cycle.direction;
  const slotNumber = position.retracement_count + 1;
  if (config.stopLossMode === 'auto') {
    const interval = progressionPips(slotNumber, {
      mode: config.intervalMode,
      head: config.nPipsHead,
      tail: config.nPipsTail,
      flatSteps: config.nPipsFlatSteps,
      gamma: config.nPipsGamma,
      rMax: config.rMax,
      manualValues: config.manualIntervals,
      roundStep: config.roundStepPips,
    });
    const planned = num(position.planned_exit_price, entry);
    const tpPips = Math.abs(planned - entry) / config.pipSize;
    if (direction === 'long') {
      const nextEntry = entry - interval * config.pipSize;
      return position.retracement_count === 0 || tpPips < interval
        ? nextEntry
        : nextEntry - interval * config.pipSize;
    }
    const nextEntry = entry + interval * config.pipSize;
    return position.retracement_count === 0 || tpPips < interval
      ? nextEntry
      : nextEntry + interval * config.pipSize;
  }
  const slPips = progressionPips(slotNumber, {
    mode: config.stopLossMode,
    head: config.stopLossPipsHead,
    tail: config.stopLossPipsTail,
    flatSteps: config.stopLossPipsFlatSteps,
    gamma: config.stopLossPipsGamma,
    rMax: config.rMax,
    manualValues: config.stopLossManualPips,
    roundStep: config.roundStepPips,
  });
  return direction === 'long'
    ? entry - slPips * config.pipSize
    : entry + slPips * config.pipSize;
}

function counterTpPips(retracement: number, config: SnowballUiConfig) {
  const step = Math.max(1, retracement);
  let pips = config.counterTpPips;
  switch (config.counterTpMode) {
    case 'additive':
      pips = config.counterTpPips + config.counterTpStepAmount * (step - 1);
      break;
    case 'subtractive':
      pips = Math.max(
        0.1,
        config.counterTpPips - config.counterTpStepAmount * (step - 1)
      );
      break;
    case 'multiplicative':
      pips = config.counterTpPips * config.counterTpMultiplier ** (step - 1);
      break;
    case 'divisive':
      pips = Math.max(
        0.1,
        config.counterTpPips / config.counterTpMultiplier ** (step - 1)
      );
      break;
    default:
      pips = config.counterTpPips;
  }
  return roundToStep(pips, config.roundStepPips);
}

function progressionPips(
  slotNumber: number,
  values: {
    mode: string;
    head: number;
    tail: number;
    flatSteps: number;
    gamma: number;
    rMax: number;
    manualValues: number[];
    roundStep: number;
  }
) {
  if (values.mode === 'manual' && values.manualValues.length > 0) {
    const index = Math.min(
      Math.max(slotNumber - 1, 0),
      values.manualValues.length - 1
    );
    return roundToStep(values.manualValues[index], values.roundStep);
  }
  if (values.mode === 'constant')
    return roundToStep(values.head, values.roundStep);
  if (slotNumber <= values.flatSteps)
    return roundToStep(values.head, values.roundStep);
  const decaySteps = values.rMax - values.flatSteps;
  if (decaySteps <= 0) return roundToStep(values.tail, values.roundStep);
  const elapsedSteps = slotNumber - values.flatSteps;
  const progress = elapsedSteps / decaySteps;
  const curved = progress ** values.gamma;
  return roundToStep(
    Math.max(values.tail, values.head - (values.head - values.tail) * curved),
    values.roundStep
  );
}

function nextSlot(positionCount: number, rMax: number) {
  const perLayer = rMax + 1;
  return {
    layer: Math.floor(positionCount / perLayer) + 1,
    retracement: positionCount % perLayer,
  };
}

function slotLabel(layer: number, retracement: number) {
  return `L${layer}/R${retracement}`;
}

function defaultUnits(
  retracement: number,
  baseUnits: number,
  trendLotSize: number
) {
  return retracement === 0
    ? baseUnits * trendLotSize
    : baseUnits * (retracement + 1);
}

function defaultExitPrice(
  position: BacktestInitialPosition,
  status: BacktestInitialPositionStatus
) {
  return status === 'pending_rebuild'
    ? position.stop_loss_price || position.entry_price
    : position.planned_exit_price || position.entry_price;
}

function addPips(
  entry: number,
  direction: 'long' | 'short',
  pips: number,
  pipSize: number
) {
  return direction === 'long' ? entry + pips * pipSize : entry - pips * pipSize;
}

function num(value: unknown, fallback: number) {
  if (value === '' || value === null || value === undefined) return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function intNum(value: unknown, fallback: number) {
  return Math.trunc(num(value, fallback));
}

function boolValue(value: unknown, fallback: boolean) {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return value !== 0;
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    if (['true', '1', 'yes', 'on'].includes(normalized)) return true;
    if (['false', '0', 'no', 'off', ''].includes(normalized)) return false;
  }
  return fallback;
}

function normalizedStrategyType(value: string | null | undefined) {
  return String(value ?? '')
    .trim()
    .toLowerCase();
}

function numericArray(value: unknown) {
  return Array.isArray(value)
    ? value
        .map((item) => num(item, NaN))
        .filter((item) => Number.isFinite(item))
    : [];
}

function roundToStep(value: number, step: number) {
  if (!Number.isFinite(step) || step <= 0) return value;
  return Math.round(value / step) * step;
}

function fixed(
  value: number | string | null | undefined
): number | string | null | undefined {
  if (value === '' || value === null || value === undefined) {
    return value;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Number(parsed.toFixed(5)) : value;
}
