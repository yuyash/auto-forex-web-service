import { useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useTranslation } from 'react-i18next';
import { queryKeys } from '../config/reactQuery';
import { backtestTasksApi } from '../services/api/backtestTasks';
import type { BacktestTask } from '../types/backtestTask';
import { Breadcrumbs, PageContainer } from '../components/common';
import {
  SettingsComparisonTable,
  type SettingsComparisonItem,
} from '../components/comparison/SettingsComparisonTable';
import { parseCompareIds } from '../utils/compareParams';
import { getStrategyDisplayName, useStrategies } from '../hooks/useStrategies';

function setIfPresent(
  target: Record<string, unknown>,
  key: string,
  value: unknown
) {
  if (value === undefined || value === null || value === '') return;
  target[key] = value;
}

function backtestTaskSettings(
  task: BacktestTask,
  strategyName: string
): Record<string, unknown> {
  const settings: Record<string, unknown> = {};
  setIfPresent(settings, 'name', task.name);
  setIfPresent(settings, 'description', task.description);
  setIfPresent(settings, 'strategy_type', strategyName);
  setIfPresent(settings, 'config_name', task.config_name);
  setIfPresent(settings, 'config_revision', task.config_revision);
  setIfPresent(settings, 'config_hash', task.config_hash);
  setIfPresent(settings, 'data_source', task.data_source);
  setIfPresent(settings, 'start_time', task.start_time);
  setIfPresent(settings, 'end_time', task.end_time);
  setIfPresent(settings, 'instrument', task.instrument);
  setIfPresent(settings, 'initial_balance', task.initial_balance);
  setIfPresent(settings, 'account_currency', task.account_currency);
  setIfPresent(settings, 'display_currency', task.display_currency);
  setIfPresent(settings, 'commission_per_trade', task.commission_per_trade);
  setIfPresent(settings, 'pip_size', task.pip_size);
  setIfPresent(settings, 'tick_granularity', task.tick_granularity);
  setIfPresent(settings, 'tick_window_value_mode', task.tick_window_value_mode);
  setIfPresent(settings, 'sell_at_completion', task.sell_at_completion);
  setIfPresent(settings, 'sell_on_stop', task.sell_on_stop);
  setIfPresent(settings, 'hedging_enabled', task.hedging_enabled);
  setIfPresent(settings, 'in_memory_mode', task.in_memory_mode);
  setIfPresent(settings, 'drain_duration_hours', task.drain_duration_hours);
  setIfPresent(
    settings,
    'market_idle_pre_close_minutes',
    task.market_idle_pre_close_minutes
  );
  setIfPresent(
    settings,
    'market_idle_resume_delay_minutes',
    task.market_idle_resume_delay_minutes
  );
  setIfPresent(settings, 'market_close_enabled', task.market_close_enabled);
  setIfPresent(settings, 'market_close_weekday', task.market_close_weekday);
  setIfPresent(settings, 'market_close_hour_utc', task.market_close_hour_utc);
  setIfPresent(settings, 'market_open_weekday', task.market_open_weekday);
  setIfPresent(settings, 'market_open_hour_utc', task.market_open_hour_utc);
  setIfPresent(settings, 'max_tick_gap_hours', task.max_tick_gap_hours);
  setIfPresent(settings, 'spread_filter_enabled', task.spread_filter_enabled);
  setIfPresent(settings, 'max_spread_pips', task.max_spread_pips);
  setIfPresent(
    settings,
    'oanda_candle_filter_enabled',
    task.oanda_candle_filter_enabled
  );
  setIfPresent(
    settings,
    'oanda_candle_filter_account_name',
    task.oanda_candle_filter_account_name
  );
  setIfPresent(
    settings,
    'oanda_candle_filter_granularity',
    task.oanda_candle_filter_granularity
  );
  setIfPresent(
    settings,
    'oanda_candle_filter_tolerance_pips',
    task.oanda_candle_filter_tolerance_pips
  );
  setIfPresent(settings, 'holidays_enabled', task.holidays_enabled);
  setIfPresent(settings, 'excluded_dates', task.excluded_dates);
  setIfPresent(
    settings,
    'initial_positions_enabled',
    task.initial_positions_enabled
  );
  setIfPresent(
    settings,
    'initial_position_cycles',
    task.initial_position_cycles
  );
  setIfPresent(settings, 'debug_options', task.debug_options);
  return settings;
}

export default function BacktestTasksComparePage() {
  const { t } = useTranslation(['common', 'backtest']);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const ids = useMemo(() => parseCompareIds(searchParams), [searchParams]);
  const { strategies } = useStrategies();

  const queries = useQueries({
    queries: ids.map((id) => ({
      queryKey: queryKeys.backtestTasks.detail(id),
      queryFn: () => backtestTasksApi.get(id),
      enabled: ids.length >= 2,
    })),
  });

  const isLoading = queries.some((query) => query.isLoading);
  const error = queries.find((query) => query.error)?.error;
  const tasks = queries
    .map((query) => query.data)
    .filter((task): task is BacktestTask => Boolean(task));

  const labelMap = useMemo(
    () =>
      new Map<string, string>([
        ['name', t('labels.name')],
        ['description', t('labels.description')],
        ['strategy_type', t('labels.strategyType')],
        ['config_name', t('labels.strategyConfiguration')],
        [
          'config_revision',
          t('comparison.configRevision', {
            defaultValue: 'Config Revision',
          }),
        ],
        [
          'config_hash',
          t('comparison.configHash', { defaultValue: 'Config Hash' }),
        ],
        ['data_source', t('backtest:detail.dataSource')],
        ['start_time', t('backtest:detail.startTime')],
        ['end_time', t('backtest:detail.endTime')],
        ['instrument', t('labels.instrument')],
        ['initial_balance', t('backtest:detail.initialBalance')],
        ['account_currency', t('labels.accountCurrency')],
        ['display_currency', t('labels.displayCurrency')],
        ['commission_per_trade', t('backtest:detail.commissionPerTrade')],
        ['pip_size', t('labels.pipSize')],
        ['tick_granularity', t('backtest:detail.tickGranularity')],
        ['tick_window_value_mode', t('backtest:detail.tickWindowValueMode')],
        ['sell_at_completion', t('backtest:form.closePositionsAtCompletion')],
        ['sell_on_stop', t('labels.sellOnStop')],
        ['hedging_enabled', t('labels.hedgingEnabled')],
        [
          'in_memory_mode',
          t('backtest:form.inMemoryMode', { defaultValue: 'In-memory mode' }),
        ],
        [
          'drain_duration_hours',
          t('backtest:form.drainDurationHours', {
            defaultValue: 'Drain duration (h)',
          }),
        ],
        [
          'market_idle_pre_close_minutes',
          t('backtest:form.marketIdlePreCloseMinutes', {
            defaultValue: 'Market idle before close (min)',
          }),
        ],
        [
          'market_idle_resume_delay_minutes',
          t('backtest:form.marketIdleResumeDelayMinutes', {
            defaultValue: 'Market resume delay (min)',
          }),
        ],
        [
          'market_close_enabled',
          t('backtest:form.marketCloseEnabled', {
            defaultValue: 'Apply weekly market close',
          }),
        ],
        [
          'market_close_weekday',
          t('backtest:form.marketCloseWeekday', {
            defaultValue: 'Market close weekday',
          }),
        ],
        [
          'market_close_hour_utc',
          t('backtest:form.marketCloseHourUtc', {
            defaultValue: 'Market close hour UTC',
          }),
        ],
        [
          'market_open_weekday',
          t('backtest:form.marketOpenWeekday', {
            defaultValue: 'Market open weekday',
          }),
        ],
        [
          'market_open_hour_utc',
          t('backtest:form.marketOpenHourUtc', {
            defaultValue: 'Market open hour UTC',
          }),
        ],
        [
          'max_tick_gap_hours',
          t('backtest:form.maxTickGapHours', {
            defaultValue: 'Max tick gap (h)',
          }),
        ],
        [
          'spread_filter_enabled',
          t('backtest:form.spreadFilterEnabled', {
            defaultValue: 'Skip wide-spread ticks',
          }),
        ],
        [
          'max_spread_pips',
          t('backtest:form.maxSpreadPips', {
            defaultValue: 'Max spread (pips)',
          }),
        ],
        [
          'oanda_candle_filter_enabled',
          t('backtest:form.oandaCandleFilterEnabled', {
            defaultValue: 'Validate ticks with OANDA candles',
          }),
        ],
        [
          'oanda_candle_filter_account_name',
          t('backtest:form.oandaCandleFilterAccount', {
            defaultValue: 'OANDA candle account',
          }),
        ],
        [
          'oanda_candle_filter_granularity',
          t('backtest:form.oandaCandleGranularity', {
            defaultValue: 'Candle granularity',
          }),
        ],
        [
          'oanda_candle_filter_tolerance_pips',
          t('backtest:form.oandaCandleTolerancePips', {
            defaultValue: 'Candle tolerance (pips)',
          }),
        ],
        [
          'holidays_enabled',
          t('backtest:form.holidaysEnabled', {
            defaultValue: 'Skip major FX holidays',
          }),
        ],
        [
          'excluded_dates',
          t('backtest:form.excludedDates', {
            defaultValue: 'Additional closed windows',
          }),
        ],
        [
          'initial_positions_enabled',
          t('backtest:form.initialPositionsEnabled'),
        ],
        ['initial_position_cycles', t('backtest:form.initialPositionCycles')],
        [
          'debug_options',
          t('comparison.debugOptions', { defaultValue: 'Debug Options' }),
        ],
      ]),
    [t]
  );

  const items = useMemo<SettingsComparisonItem[]>(
    () =>
      tasks.map((task) => {
        const strategyName = getStrategyDisplayName(
          strategies,
          task.strategy_type
        );
        return {
          id: task.id,
          title: task.name,
          subtitle: `${strategyName} / ${task.instrument}`,
          settings: backtestTaskSettings(task, strategyName),
        };
      }),
    [strategies, tasks]
  );

  return (
    <PageContainer sx={{ mt: { xs: 1, sm: 1.5 }, mb: 1.5 }}>
      <Breadcrumbs />
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 1,
          flexWrap: 'wrap',
          mb: 1,
        }}
      >
        <Typography
          variant="h4"
          component="h1"
          sx={{ fontSize: { xs: '1.25rem', sm: '1.5rem' }, fontWeight: 600 }}
        >
          {t('comparison.backtestTaskTitle', {
            defaultValue: 'Compare Backtest Tasks',
          })}
        </Typography>
        <Button
          variant="outlined"
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/backtest-tasks')}
        >
          {t('breadcrumbs.backtestTasks')}
        </Button>
      </Box>

      {ids.length < 2 ? (
        <Alert severity="info">
          {t('comparison.selectAtLeastTwo', {
            defaultValue: 'Select at least two items to compare.',
          })}
        </Alert>
      ) : isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Alert severity="error">
          {error instanceof Error ? error.message : String(error)}
        </Alert>
      ) : (
        <SettingsComparisonTable
          items={items}
          labelMap={labelMap}
          keyOrder={[
            'name',
            'description',
            'strategy_type',
            'config_name',
            'config_revision',
            'config_hash',
            'data_source',
            'start_time',
            'end_time',
            'instrument',
            'initial_balance',
            'account_currency',
            'display_currency',
            'commission_per_trade',
            'pip_size',
            'tick_granularity',
            'tick_window_value_mode',
            'sell_at_completion',
            'sell_on_stop',
            'hedging_enabled',
            'in_memory_mode',
            'drain_duration_hours',
            'market_idle_pre_close_minutes',
            'market_idle_resume_delay_minutes',
            'market_close_enabled',
            'market_close_weekday',
            'market_close_hour_utc',
            'market_open_weekday',
            'market_open_hour_utc',
            'max_tick_gap_hours',
            'spread_filter_enabled',
            'max_spread_pips',
            'oanda_candle_filter_enabled',
            'oanda_candle_filter_account_name',
            'oanda_candle_filter_granularity',
            'oanda_candle_filter_tolerance_pips',
            'holidays_enabled',
            'excluded_dates',
            'initial_positions_enabled',
            'initial_position_cycles',
            'debug_options',
          ]}
        />
      )}
    </PageContainer>
  );
}
