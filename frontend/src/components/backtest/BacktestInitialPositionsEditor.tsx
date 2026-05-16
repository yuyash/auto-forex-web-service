import {
  Add as AddIcon,
  CheckCircleOutline as EnableIcon,
  Delete as DeleteIcon,
  HighlightOff as DisableIcon,
  Download as ImportIcon,
  RemoveCircleOutline as RemoveIcon,
  RestartAlt as ResetIcon,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
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
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { initialPositionImportsApi } from '../../services/api';
import type { TickDataPoint } from '../../services/api/market';
import type {
  InitialPositionImportSource,
  InitialPositionTaskType,
} from '../../services/api/initialPositionImports';
import type {
  BacktestInitialPosition,
  BacktestInitialPositionCycle,
  BacktestInitialPositionStatus,
} from '../../types/backtestTask';
import type { StrategyConfig } from '../../types/configuration';
import { DEFAULT_PIP_SIZE } from '../../utils/instruments';

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
  taskType?: InitialPositionTaskType;
  currentTaskId?: string;
  showFirstTickInfo?: boolean;
  allowOandaImport?: boolean;
  accountId?: number | string;
  configId?: string;
  instrument?: string;
  error?: string;
  resetBaselineEnabled?: boolean;
  resetBaselineValue?: BacktestInitialPositionCycle[];
}

interface InitialPositionOrderWarning {
  type:
    | 'duplicate'
    | 'layerOutOfRange'
    | 'retracementOutOfRange'
    | 'missingLayer'
    | 'layerStart'
    | 'missingRetracement';
  cycleNumber: number;
  positionNumber?: number;
  actual: string;
  duplicateOf?: number;
  maxLayer?: number;
  maxRetracement?: number;
  missingLayer?: number;
  missingRetracement?: number;
}

interface SlotAddress {
  layer: number;
  retracement: number;
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
  taskType = 'backtest',
  currentTaskId,
  showFirstTickInfo = true,
  allowOandaImport = false,
  accountId,
  configId,
  instrument,
  error,
  resetBaselineEnabled = false,
  resetBaselineValue = [],
}: BacktestInitialPositionsEditorProps) {
  const { t } = useTranslation(['backtest', 'common']);
  const [selectedSourceKey, setSelectedSourceKey] = useState('');
  const [importing, setImporting] = useState<'task' | 'oanda' | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [selectedAddSlotKeys, setSelectedAddSlotKeys] = useState<
    Record<number, string>
  >({});
  const [anchorShiftEnabledByCycle, setAnchorShiftEnabledByCycle] = useState<
    Record<number, boolean>
  >({});
  const [crossCycleAnchorShiftEnabled, setCrossCycleAnchorShiftEnabled] =
    useState(true);
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
    () => initialPositionOrderWarnings(value, config),
    [config, value]
  );
  const importSourcesQuery = useQuery({
    queryKey: ['initial-position-import-sources'],
    queryFn: () => initialPositionImportsApi.listSources(),
    enabled: enabled && canUseInitialPositions,
    staleTime: 30_000,
  });
  const importSources = importSourcesQuery.data?.results ?? [];
  const canImportFromOanda = Boolean(
    allowOandaImport && accountId && configId && instrument
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

  useEffect(() => {
    setAnchorShiftEnabledByCycle((current) =>
      Object.fromEntries(
        Object.entries(current).filter(([cycleIndex]) => {
          const index = Number(cycleIndex);
          return Number.isInteger(index) && index >= 0 && index < value.length;
        })
      )
    );
  }, [value.length]);

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
    setAnchorShiftEnabledByCycle((current) =>
      Object.fromEntries(
        Object.entries(current).flatMap(([rawIndex, isEnabled]) => {
          const index = Number(rawIndex);
          if (!Number.isInteger(index) || index === cycleIndex) {
            return [];
          }
          return [[index > cycleIndex ? index - 1 : index, isEnabled]];
        })
      )
    );
  };

  const addPosition = (cycleIndex: number, slot: SlotAddress) => {
    updateCycle(cycleIndex, (cycle) => {
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
      return {
        ...cycle,
        positions: sortPositionsBySlot([...cycle.positions, position]),
      };
    });
  };

  const removeLastPosition = (cycleIndex: number) => {
    updateCycle(cycleIndex, (cycle) => ({
      ...cycle,
      positions: cycle.positions.slice(0, -1),
    }));
  };

  const importFromTask = async () => {
    const source = parseImportSourceKey(selectedSourceKey, importSources);
    if (!source) return;
    setImporting('task');
    setImportError(null);
    try {
      const result = await initialPositionImportsApi.importFromTask({
        source_task_type: source.task_type,
        source_task_id: source.id,
        target_task_type: taskType,
      });
      onChange(appendImportedCycles(value, result.cycles));
    } catch {
      setImportError(
        t('backtest:form.initialPositionImportFailed', {
          defaultValue: 'Could not import initial positions.',
        })
      );
    } finally {
      setImporting(null);
    }
  };

  const importFromOanda = async () => {
    if (!canImportFromOanda) return;
    setImporting('oanda');
    setImportError(null);
    try {
      const result = await initialPositionImportsApi.importFromOanda({
        account_id: accountId!,
        config_id: configId!,
        instrument: instrument!,
      });
      onChange(appendImportedCycles(value, result.cycles));
    } catch {
      setImportError(
        t('backtest:form.initialPositionOandaImportFailed', {
          defaultValue: 'Could not import open OANDA positions.',
        })
      );
    } finally {
      setImporting(null);
    }
  };

  const setAllCycleAnchorShiftEnabled = (isEnabled: boolean) => {
    setAnchorShiftEnabledByCycle(
      Object.fromEntries(value.map((_, index) => [index, isEnabled]))
    );
  };

  const resetInitialPositions = () => {
    setImportError(null);
    setSelectedAddSlotKeys({});
    setCrossCycleAnchorShiftEnabled(true);
    setAllCycleAnchorShiftEnabled(true);
    onEnabledChange(resetBaselineEnabled);
    onChange(cloneInitialPositionCycles(resetBaselineValue));
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
          {importError ? <Alert severity="error">{importError}</Alert> : null}

          <Stack
            direction={{ xs: 'column', md: 'row' }}
            spacing={1}
            sx={{ alignItems: { xs: 'stretch', md: 'center' } }}
          >
            <FormControl size="small" sx={{ minWidth: { md: 360 } }}>
              <InputLabel>
                {t('backtest:form.initialPositionImportTask', {
                  defaultValue: 'Import source task',
                })}
              </InputLabel>
              <Select
                label={t('backtest:form.initialPositionImportTask', {
                  defaultValue: 'Import source task',
                })}
                value={selectedSourceKey}
                onChange={(event) => setSelectedSourceKey(event.target.value)}
                disabled={importSourcesQuery.isLoading}
              >
                <MenuItem value="">
                  <em>
                    {importSourcesQuery.isLoading
                      ? t('common:status.loading')
                      : t('backtest:form.selectImportSourceTask', {
                          defaultValue: 'Select a task',
                        })}
                  </em>
                </MenuItem>
                {importSources.map((source) => (
                  <MenuItem
                    key={importSourceKey(source)}
                    value={importSourceKey(source)}
                  >
                    {t('backtest:form.initialPositionImportSourceLabel', {
                      type:
                        source.task_type === 'backtest'
                          ? t('common:navigation.backtest')
                          : t('common:navigation.trading'),
                      name: source.name,
                      status: t(`common:status.${source.status}`, {
                        defaultValue: source.status,
                      }),
                      instrument: source.instrument
                        ? t('backtest:form.initialPositionImportInstrument', {
                            instrument: source.instrument,
                          })
                        : '',
                    })}
                    {source.task_type === taskType &&
                    source.id === currentTaskId
                      ? ` (${t('common:labels.currentTask')})`
                      : ''}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Button
              variant="outlined"
              startIcon={
                importing === 'task' ? (
                  <CircularProgress size={16} />
                ) : (
                  <ImportIcon />
                )
              }
              disabled={!selectedSourceKey || importing !== null}
              onClick={importFromTask}
            >
              {t('common:actions.import', { defaultValue: 'Import' })}
            </Button>
            {allowOandaImport ? (
              <Button
                variant="outlined"
                startIcon={
                  importing === 'oanda' ? (
                    <CircularProgress size={16} />
                  ) : (
                    <ImportIcon />
                  )
                }
                disabled={!canImportFromOanda || importing !== null}
                onClick={importFromOanda}
              >
                {t('backtest:form.importOandaOpenPositions', {
                  defaultValue: 'Import OANDA open positions',
                })}
              </Button>
            ) : null}
          </Stack>

          {orderWarnings.length > 0 ? (
            <Alert severity="error">
              <Stack spacing={0.5}>
                {orderWarnings.map((warning, index) => (
                  <Typography
                    key={`${warning.type}-${warning.cycleNumber}-${warning.positionNumber ?? 'cycle'}-${warning.actual}-${index}`}
                    variant="body2"
                  >
                    {formatInitialPositionIssue(warning, t)}
                  </Typography>
                ))}
              </Stack>
            </Alert>
          ) : null}

          {showFirstTickInfo ? (
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
          ) : null}

          <Stack
            direction={{ xs: 'column', lg: 'row' }}
            spacing={1}
            sx={{ alignItems: { xs: 'stretch', lg: 'center' } }}
          >
            <FormControlLabel
              sx={{ ml: 0 }}
              control={
                <Checkbox
                  size="small"
                  checked={crossCycleAnchorShiftEnabled}
                  onChange={(event) =>
                    setCrossCycleAnchorShiftEnabled(event.target.checked)
                  }
                />
              }
              label={
                <Typography variant="body2">
                  {t('backtest:form.initialPositionCrossCycleAnchorShift', {
                    defaultValue: 'Use C1 as anchor for all cycles',
                  })}
                </Typography>
              }
            />
            <Stack
              direction={{ xs: 'column', sm: 'row' }}
              spacing={1}
              sx={{ alignItems: { xs: 'stretch', sm: 'center' } }}
            >
              <Button
                size="small"
                variant="outlined"
                startIcon={<EnableIcon />}
                onClick={() => setAllCycleAnchorShiftEnabled(true)}
                sx={{ width: { xs: '100%', sm: 'auto' } }}
              >
                {t('backtest:form.enableAllCycleAnchorShift', {
                  defaultValue: 'Enable all cycle adjustments',
                })}
              </Button>
              <Button
                size="small"
                variant="outlined"
                startIcon={<DisableIcon />}
                onClick={() => setAllCycleAnchorShiftEnabled(false)}
                sx={{ width: { xs: '100%', sm: 'auto' } }}
              >
                {t('backtest:form.disableAllCycleAnchorShift', {
                  defaultValue: 'Disable all cycle adjustments',
                })}
              </Button>
              <Button
                size="small"
                variant="outlined"
                color="warning"
                startIcon={<ResetIcon />}
                onClick={resetInitialPositions}
                sx={{ width: { xs: '100%', sm: 'auto' } }}
              >
                {t('backtest:form.resetInitialPositions', {
                  defaultValue: 'Reset initial positions',
                })}
              </Button>
            </Stack>
          </Stack>

          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={1}
            sx={{ alignItems: { xs: 'stretch', sm: 'center' } }}
          >
            <Button
              size="small"
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={() => addCycle('long')}
              sx={{ width: { xs: '100%', sm: 'auto' } }}
            >
              {t('backtest:form.addLongCycle', { defaultValue: 'Long cycle' })}
            </Button>
            <Button
              size="small"
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={() => addCycle('short')}
              sx={{ width: { xs: '100%', sm: 'auto' } }}
            >
              {t('backtest:form.addShortCycle', {
                defaultValue: 'Short cycle',
              })}
            </Button>
          </Stack>

          {value.map((cycle, cycleIndex) => {
            const addSlots = nextAvailableSlots(cycle, config);
            const selectedSlotKey = selectedAddSlotKey(
              cycleIndex,
              addSlots,
              selectedAddSlotKeys
            );
            const selectedSlot = parseSlotKey(selectedSlotKey);
            const canAdd = selectedSlot !== null;
            const anchorShiftEnabled = isCycleAnchorShiftEnabled(
              anchorShiftEnabledByCycle,
              cycleIndex
            );
            return (
              <Paper
                key={`${cycle.direction}-${cycleIndex}`}
                variant="outlined"
                sx={{ p: { xs: 1.5, sm: 2 }, borderRadius: 1 }}
              >
                <Stack spacing={2}>
                  <Stack
                    direction={{ xs: 'column', sm: 'row' }}
                    spacing={1}
                    sx={{
                      alignItems: { xs: 'stretch', sm: 'center' },
                      justifyContent: 'space-between',
                    }}
                  >
                    <Stack
                      direction={{ xs: 'column', sm: 'row' }}
                      spacing={1}
                      sx={{
                        alignItems: { xs: 'stretch', sm: 'center' },
                        flexWrap: 'wrap',
                      }}
                    >
                      <Chip
                        size="small"
                        label={t('backtest:form.initialPositionCycleTempId', {
                          defaultValue: 'C{{cycle}}',
                          cycle: cycleIndex + 1,
                        })}
                      />
                      <FormControl
                        size="small"
                        sx={{ width: { xs: '100%', sm: 160 } }}
                      >
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
                      <Stack
                        direction="row"
                        spacing={1}
                        sx={{
                          alignItems: 'center',
                          justifyContent: {
                            xs: 'space-between',
                            sm: 'flex-start',
                          },
                          minWidth: 0,
                          width: { xs: '100%', sm: 'auto' },
                        }}
                      >
                        <FormControlLabel
                          sx={{
                            ml: 0,
                            mr: 0,
                            alignItems: 'center',
                            flex: 1,
                            minWidth: 0,
                          }}
                          control={
                            <Checkbox
                              size="small"
                              checked={anchorShiftEnabled}
                              onChange={(event) =>
                                setAnchorShiftEnabledByCycle((current) => ({
                                  ...current,
                                  [cycleIndex]: event.target.checked,
                                }))
                              }
                            />
                          }
                          label={
                            <Typography
                              variant="body2"
                              sx={{ overflowWrap: 'anywhere' }}
                            >
                              {t('backtest:form.initialPositionAnchorShift', {
                                defaultValue:
                                  'Auto-adjust this cycle from L1/R0',
                              })}
                            </Typography>
                          }
                        />
                        <Tooltip
                          title={t('common:actions.delete', {
                            defaultValue: 'Delete',
                          })}
                        >
                          <IconButton
                            onClick={() => removeCycle(cycleIndex)}
                            sx={{ flexShrink: 0 }}
                          >
                            <DeleteIcon />
                          </IconButton>
                        </Tooltip>
                      </Stack>
                    </Stack>
                  </Stack>

                  {cycle.positions.map((position, positionIndex) => (
                    <SeedPositionRow
                      key={`${position.layer_number}-${position.retracement_count}-${positionIndex}`}
                      position={position}
                      positionNumber={positionIndex + 1}
                      onChange={(next) =>
                        onChange(
                          updatePositionInCycles(
                            value,
                            cycleIndex,
                            positionIndex,
                            next,
                            config,
                            anchorShiftEnabledByCycle,
                            crossCycleAnchorShiftEnabled
                          )
                        )
                      }
                      stopLossEnabled={config.stopLossEnabled}
                    />
                  ))}

                  <Stack
                    direction={{ xs: 'column', sm: 'row' }}
                    spacing={1}
                    sx={{ alignItems: { xs: 'stretch', sm: 'center' } }}
                  >
                    <FormControl
                      size="small"
                      sx={{ width: { xs: '100%', sm: 150 } }}
                      disabled={addSlots.length === 0}
                    >
                      <InputLabel>
                        {t('backtest:form.nextInitialPositionSlot', {
                          defaultValue: 'Next position',
                        })}
                      </InputLabel>
                      <Select
                        label={t('backtest:form.nextInitialPositionSlot', {
                          defaultValue: 'Next position',
                        })}
                        value={selectedSlotKey}
                        onChange={(event) =>
                          setSelectedAddSlotKeys((current) => ({
                            ...current,
                            [cycleIndex]: event.target.value,
                          }))
                        }
                      >
                        {addSlots.length === 0 ? (
                          <MenuItem value="">
                            {t('backtest:form.gridFull', {
                              defaultValue: 'Grid full',
                            })}
                          </MenuItem>
                        ) : (
                          addSlots.map((slot) => (
                            <MenuItem key={slotKey(slot)} value={slotKey(slot)}>
                              {slotLabel(slot.layer, slot.retracement)}
                            </MenuItem>
                          ))
                        )}
                      </Select>
                    </FormControl>
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<AddIcon />}
                      disabled={!canAdd}
                      sx={{ width: { xs: '100%', sm: 'auto' } }}
                      onClick={() => {
                        if (selectedSlot) {
                          addPosition(cycleIndex, selectedSlot);
                        }
                      }}
                    >
                      {t('common:actions.add', { defaultValue: 'Add' })}
                    </Button>
                    <Button
                      size="small"
                      variant="text"
                      startIcon={<RemoveIcon />}
                      disabled={cycle.positions.length === 0}
                      sx={{ width: { xs: '100%', sm: 'auto' } }}
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
  config: SnowballUiConfig
): InitialPositionOrderWarning[] {
  return cycles.flatMap((cycle, cycleIndex) => {
    const warnings: InitialPositionOrderWarning[] = [];
    const seen = new Map<string, number>();
    const validPositions: Array<{
      positionNumber: number;
      layer: number;
      retracement: number;
    }> = [];

    cycle.positions.forEach((position, positionIndex) => {
      const layer = intNum(position.layer_number, 0);
      const retracement = intNum(position.retracement_count, 0);
      const actualLabel = slotLabel(layer, retracement);
      const key = `${layer}:${retracement}`;

      if (layer < 1 || layer > config.fMax) {
        warnings.push({
          type: 'layerOutOfRange',
          cycleNumber: cycleIndex + 1,
          positionNumber: positionIndex + 1,
          actual: actualLabel,
          maxLayer: config.fMax,
        });
      }

      if (retracement < 0 || retracement > config.rMax) {
        warnings.push({
          type: 'retracementOutOfRange',
          cycleNumber: cycleIndex + 1,
          positionNumber: positionIndex + 1,
          actual: actualLabel,
          maxRetracement: config.rMax,
        });
      }

      if (seen.has(key)) {
        warnings.push({
          type: 'duplicate',
          cycleNumber: cycleIndex + 1,
          positionNumber: positionIndex + 1,
          actual: actualLabel,
          duplicateOf: seen.get(key),
        });
      } else {
        seen.set(key, positionIndex + 1);
      }

      if (
        seen.get(key) === positionIndex + 1 &&
        layer >= 1 &&
        layer <= config.fMax &&
        retracement >= 0 &&
        retracement <= config.rMax
      ) {
        validPositions.push({
          positionNumber: positionIndex + 1,
          layer,
          retracement,
        });
      }
    });

    const byLayer = new Map<number, typeof validPositions>();
    validPositions.forEach((item) => {
      byLayer.set(item.layer, [...(byLayer.get(item.layer) ?? []), item]);
    });
    const maxLayer = Math.max(0, ...Array.from(byLayer.keys()));

    for (let layer = 1; layer <= maxLayer; layer += 1) {
      const layerPositions = byLayer.get(layer) ?? [];
      if (layerPositions.length === 0) {
        const offender = validPositions.find((item) => item.layer > layer);
        warnings.push({
          type: 'missingLayer',
          cycleNumber: cycleIndex + 1,
          positionNumber: offender?.positionNumber,
          actual: offender
            ? slotLabel(offender.layer, offender.retracement)
            : `L${layer}`,
          missingLayer: layer,
        });
        continue;
      }

      const byRetracement = new Map<number, (typeof validPositions)[number]>();
      layerPositions.forEach((item) => {
        byRetracement.set(item.retracement, item);
      });
      const maxRetracement = Math.max(...Array.from(byRetracement.keys()));
      if (!byRetracement.has(0)) {
        const offender = [...layerPositions].sort(
          (left, right) => left.retracement - right.retracement
        )[0];
        warnings.push({
          type: 'layerStart',
          cycleNumber: cycleIndex + 1,
          positionNumber: offender.positionNumber,
          actual: slotLabel(offender.layer, offender.retracement),
          missingRetracement: 0,
        });
        continue;
      }

      for (
        let retracement = 0;
        retracement <= maxRetracement;
        retracement += 1
      ) {
        if (byRetracement.has(retracement)) {
          continue;
        }
        const offender = [...layerPositions]
          .filter((item) => item.retracement > retracement)
          .sort((left, right) => left.retracement - right.retracement)[0];
        warnings.push({
          type: 'missingRetracement',
          cycleNumber: cycleIndex + 1,
          positionNumber: offender.positionNumber,
          actual: slotLabel(offender.layer, offender.retracement),
          missingRetracement: retracement,
        });
        break;
      }
    }

    return warnings;
  });
}

function updatePositionInCycle(
  cycle: BacktestInitialPositionCycle,
  positionIndex: number,
  next: BacktestInitialPosition,
  config: SnowballUiConfig,
  anchorShiftEnabled: boolean
): BacktestInitialPositionCycle {
  const previous = cycle.positions[positionIndex];
  const delta =
    previous && anchorShiftEnabled && isAnchorSlot(previous)
      ? entryPriceDelta(previous, next)
      : null;

  if (previous && delta !== null && delta !== 0) {
    const shiftedPositions = cycle.positions.map((position, index) =>
      index === positionIndex
        ? shiftAnchorPositionPrices(previous, next, delta)
        : shiftPositionPrices(position, delta, true)
    );
    const shiftedCycle = { ...cycle, positions: shiftedPositions };
    return {
      ...shiftedCycle,
      positions: shiftedPositions.map((position) =>
        normalizePositionForConfig(
          withDefaultPrices(position, shiftedCycle, config),
          config
        )
      ),
    };
  }

  return {
    ...cycle,
    positions: cycle.positions.map((item, index) =>
      index === positionIndex
        ? normalizePositionForConfig(
            withDefaultPrices(next, cycle, config),
            config
          )
        : item
    ),
  };
}

function updatePositionInCycles(
  cycles: BacktestInitialPositionCycle[],
  cycleIndex: number,
  positionIndex: number,
  next: BacktestInitialPosition,
  config: SnowballUiConfig,
  anchorShiftEnabledByCycle: Record<number, boolean>,
  crossCycleAnchorShiftEnabled: boolean
): BacktestInitialPositionCycle[] {
  const cycle = cycles[cycleIndex];
  const previous = cycle?.positions[positionIndex];
  const delta =
    previous && isAnchorSlot(previous) ? entryPriceDelta(previous, next) : null;
  const shouldShiftAcrossCycles =
    cycleIndex === 0 &&
    crossCycleAnchorShiftEnabled &&
    delta !== null &&
    delta !== 0;

  if (!shouldShiftAcrossCycles) {
    return cycles.map((current, index) =>
      index === cycleIndex
        ? updatePositionInCycle(
            current,
            positionIndex,
            next,
            config,
            isCycleAnchorShiftEnabled(anchorShiftEnabledByCycle, index)
          )
        : current
    );
  }

  return cycles.map((current, index) => {
    if (!isCycleAnchorShiftEnabled(anchorShiftEnabledByCycle, index)) {
      return index === cycleIndex
        ? updatePositionInCycle(current, positionIndex, next, config, false)
        : current;
    }

    return index === cycleIndex
      ? updatePositionInCycle(current, positionIndex, next, config, true)
      : shiftCyclePrices(current, delta, config);
  });
}

function shiftCyclePrices(
  cycle: BacktestInitialPositionCycle,
  delta: number,
  config: SnowballUiConfig
): BacktestInitialPositionCycle {
  const shiftedPositions = cycle.positions.map((position) =>
    shiftPositionPrices(position, delta, true)
  );
  const shiftedCycle = { ...cycle, positions: shiftedPositions };
  return {
    ...shiftedCycle,
    positions: shiftedPositions.map((position) =>
      normalizePositionForConfig(
        withDefaultPrices(position, shiftedCycle, config),
        config
      )
    ),
  };
}

function isCycleAnchorShiftEnabled(
  anchorShiftEnabledByCycle: Record<number, boolean>,
  cycleIndex: number
) {
  return anchorShiftEnabledByCycle[cycleIndex] ?? true;
}

function isAnchorSlot(position: BacktestInitialPosition) {
  return (
    intNum(position.layer_number, 0) === 1 &&
    intNum(position.retracement_count, -1) === 0
  );
}

function entryPriceDelta(
  previous: BacktestInitialPosition,
  next: BacktestInitialPosition
) {
  const previousEntry = num(previous.entry_price, NaN);
  const nextEntry = num(next.entry_price, NaN);
  if (!Number.isFinite(previousEntry) || !Number.isFinite(nextEntry)) {
    return null;
  }
  return nextEntry - previousEntry;
}

function shiftAnchorPositionPrices(
  previous: BacktestInitialPosition,
  next: BacktestInitialPosition,
  delta: number
): BacktestInitialPosition {
  const status = next.status ?? previous.status ?? 'open';
  return {
    ...next,
    planned_exit_price: shiftPrice(previous.planned_exit_price, delta),
    stop_loss_price: shiftPrice(previous.stop_loss_price, delta),
    exit_price:
      status === 'open' ? undefined : shiftPrice(previous.exit_price, delta),
  };
}

function shiftPositionPrices(
  position: BacktestInitialPosition,
  delta: number,
  includeEntry: boolean
): BacktestInitialPosition {
  return {
    ...position,
    entry_price: includeEntry
      ? shiftRequiredPrice(position.entry_price, delta)
      : position.entry_price,
    planned_exit_price: shiftPrice(position.planned_exit_price, delta),
    stop_loss_price: shiftPrice(position.stop_loss_price, delta),
    exit_price: shiftPrice(position.exit_price, delta),
  };
}

function shiftRequiredPrice(value: number | string, delta: number) {
  const current = num(value, NaN);
  return Number.isFinite(current)
    ? Number((current + delta).toFixed(5))
    : value;
}

function shiftPrice(value: number | string | null | undefined, delta: number) {
  const current = num(value, NaN);
  return Number.isFinite(current) ? fixed(current + delta) : value;
}

function formatInitialPositionIssue(
  warning: InitialPositionOrderWarning,
  t: ReturnType<typeof useTranslation>['t']
) {
  const base = {
    cycle: warning.cycleNumber,
    position: warning.positionNumber,
    actual: warning.actual,
  };
  switch (warning.type) {
    case 'duplicate':
      return t('backtest:form.initialPositionDuplicateWarning', {
        defaultValue:
          'Cycle C{{cycle}} position P{{position}} duplicates {{actual}}.',
        ...base,
      });
    case 'layerOutOfRange':
      return t('backtest:form.initialPositionLayerOutOfRangeWarning', {
        defaultValue:
          'Cycle C{{cycle}} position P{{position}} uses {{actual}}, but max layer is L{{maxLayer}}.',
        ...base,
        maxLayer: warning.maxLayer,
      });
    case 'retracementOutOfRange':
      return t('backtest:form.initialPositionRetracementOutOfRangeWarning', {
        defaultValue:
          'Cycle C{{cycle}} position P{{position}} uses {{actual}}, but max retracement is R{{maxRetracement}}.',
        ...base,
        maxRetracement: warning.maxRetracement,
      });
    case 'missingLayer':
      return t('backtest:form.initialPositionMissingLayerWarning', {
        defaultValue:
          'Cycle C{{cycle}} position P{{position}} cannot use {{actual}} because L{{missingLayer}} is missing.',
        ...base,
        missingLayer: warning.missingLayer,
      });
    case 'layerStart':
      return t('backtest:form.initialPositionLayerStartWarning', {
        defaultValue:
          'Cycle C{{cycle}} position P{{position}} cannot use {{actual}} because each layer must start at R0.',
        ...base,
      });
    case 'missingRetracement':
      return t('backtest:form.initialPositionMissingRetracementWarning', {
        defaultValue:
          'Cycle C{{cycle}} position P{{position}} cannot use {{actual}} because R{{missingRetracement}} is missing before it.',
        ...base,
        missingRetracement: warning.missingRetracement,
      });
    default:
      return warning.actual;
  }
}

function nextAvailableSlots(
  cycle: BacktestInitialPositionCycle,
  config: SnowballUiConfig
): SlotAddress[] {
  const slotsByLayer = new Map<number, Set<number>>();
  cycle.positions.forEach((position) => {
    const layer = intNum(position.layer_number, 0);
    const retracement = intNum(position.retracement_count, -1);
    if (
      layer < 1 ||
      layer > config.fMax ||
      retracement < 0 ||
      retracement > config.rMax
    ) {
      return;
    }
    if (!slotsByLayer.has(layer)) {
      slotsByLayer.set(layer, new Set<number>());
    }
    slotsByLayer.get(layer)?.add(retracement);
  });

  if (slotsByLayer.size === 0) {
    return [{ layer: 1, retracement: 0 }];
  }

  const slots: SlotAddress[] = [];
  const maxLayer = Math.max(...Array.from(slotsByLayer.keys()));
  for (let layer = 1; layer <= Math.min(maxLayer, config.fMax); layer += 1) {
    const retracements = slotsByLayer.get(layer);
    if (!retracements || !retracements.has(0)) {
      continue;
    }
    const maxRetracement = Math.max(...Array.from(retracements));
    if (!isContiguousRetracementPrefix(retracements, maxRetracement)) {
      continue;
    }
    if (maxRetracement < config.rMax) {
      slots.push({ layer, retracement: maxRetracement + 1 });
    }
  }

  if (canAddNextLayer(slotsByLayer, maxLayer, config.fMax)) {
    slots.push({ layer: maxLayer + 1, retracement: 0 });
  }

  return slots;
}

function canAddNextLayer(
  slotsByLayer: Map<number, Set<number>>,
  maxLayer: number,
  fMax: number
) {
  if (maxLayer >= fMax) {
    return false;
  }
  for (let layer = 1; layer <= maxLayer; layer += 1) {
    if (!slotsByLayer.get(layer)?.has(0)) {
      return false;
    }
  }
  return true;
}

function isContiguousRetracementPrefix(
  retracements: Set<number>,
  maxRetracement: number
) {
  for (let retracement = 0; retracement <= maxRetracement; retracement += 1) {
    if (!retracements.has(retracement)) {
      return false;
    }
  }
  return true;
}

function selectedAddSlotKey(
  cycleIndex: number,
  slots: SlotAddress[],
  selected: Record<number, string>
) {
  const current = selected[cycleIndex];
  if (current && slots.some((slot) => slotKey(slot) === current)) {
    return current;
  }
  return slots[0] ? slotKey(slots[0]) : '';
}

function slotKey(slot: SlotAddress) {
  return `${slot.layer}:${slot.retracement}`;
}

function parseSlotKey(value: string): SlotAddress | null {
  const [rawLayer, rawRetracement] = value.split(':');
  const layer = Number(rawLayer);
  const retracement = Number(rawRetracement);
  if (!Number.isInteger(layer) || !Number.isInteger(retracement)) {
    return null;
  }
  return { layer, retracement };
}

function sortPositionsBySlot(positions: BacktestInitialPosition[]) {
  return [...positions].sort((left, right) => {
    const leftLayer = intNum(left.layer_number, 0);
    const rightLayer = intNum(right.layer_number, 0);
    if (leftLayer !== rightLayer) {
      return leftLayer - rightLayer;
    }
    return (
      intNum(left.retracement_count, 0) - intNum(right.retracement_count, 0)
    );
  });
}

function normalizeCyclesForConfig(
  cycles: BacktestInitialPositionCycle[],
  config: SnowballUiConfig
): BacktestInitialPositionCycle[] {
  return cycles.map((cycle) => {
    const normalizedPositions = sortPositionsBySlot(
      cycle.positions.map((position) =>
        normalizePositionForConfig(position, config)
      )
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

function cloneInitialPositionCycles(cycles: BacktestInitialPositionCycle[]) {
  return cycles.map((cycle) => ({
    ...cycle,
    positions: cycle.positions.map((position) => ({ ...position })),
  }));
}

function appendImportedCycles(
  current: BacktestInitialPositionCycle[],
  imported: BacktestInitialPositionCycle[]
) {
  if (imported.length === 0) return current;
  return [
    ...current,
    ...imported.map((cycle) => ({
      ...cycle,
      positions: sortPositionsBySlot(cycle.positions),
    })),
  ];
}

function importSourceKey(source: InitialPositionImportSource) {
  return `${source.task_type}:${source.id}`;
}

function parseImportSourceKey(
  value: string,
  sources: InitialPositionImportSource[]
) {
  return sources.find((source) => importSourceKey(source) === value);
}

function formatTickTimestamp(timestamp: string) {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? timestamp : date.toLocaleString();
}

function SeedPositionRow({
  position,
  positionNumber,
  onChange,
  stopLossEnabled,
}: {
  position: BacktestInitialPosition;
  positionNumber: number;
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
          <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap' }}>
            <Chip
              size="small"
              label={t('backtest:form.initialPositionPositionTempId', {
                defaultValue: 'P{{position}}',
                position: positionNumber,
              })}
            />
            <Chip
              size="small"
              variant="outlined"
              label={`L${position.layer_number}/R${position.retracement_count}`}
            />
          </Stack>
        </Grid>
        <Grid size={{ xs: 12, sm: 1.6 }}>
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
        <Grid size={{ xs: 12, sm: 1.8 }}>
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
        <Grid size={{ xs: 12, sm: 1.8 }}>
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
        <Grid size={{ xs: 12, sm: 1.8 }}>
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
        <Grid size={{ xs: 12, sm: 1.8 }}>
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
          <Grid size={{ xs: 12, sm: 1.8 }}>
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
        <Box sx={{ mt: 1.5, maxWidth: { xs: 'none', sm: 260 } }}>
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
    pipSize: num(pipSize, num(params.pip_size, Number(DEFAULT_PIP_SIZE))),
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
  const layer = intNum(position.layer_number, 0);
  const retracement = intNum(position.retracement_count, 0);
  if (retracement === 0) {
    const raw = addPips(entry, direction, config.mPips, config.pipSize);
    if (layer <= 1) return raw;
    const bound = [...cycle.positions]
      .reverse()
      .find((p) => intNum(p.layer_number, 0) === layer - 1)?.planned_exit_price;
    const boundNum = num(bound, NaN);
    if (!Number.isFinite(boundNum)) return raw;
    if (direction === 'long' && raw > boundNum) return boundNum;
    if (direction === 'short' && raw < boundNum) return boundNum;
    return raw;
  }
  if (config.counterTpMode === 'weighted_avg') {
    const prior = cycle.positions.filter(
      (p) =>
        intNum(p.layer_number, 0) === layer &&
        intNum(p.retracement_count, 0) < retracement
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
    counterTpPips(retracement, config),
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
  const retracement = intNum(position.retracement_count, 0);
  const slotNumber = retracement + 1;
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
      return retracement === 0 || tpPips < interval
        ? nextEntry
        : nextEntry - interval * config.pipSize;
    }
    const nextEntry = entry + interval * config.pipSize;
    return retracement === 0 || tpPips < interval
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
