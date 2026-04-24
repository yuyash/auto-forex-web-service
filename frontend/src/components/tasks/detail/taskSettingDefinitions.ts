import type { TFunction } from 'i18next';
import type { TaskSettingDefinition } from './TaskSettingsList';
import {
  formatDateTimeSetting,
  type TaskSettingValue,
} from './taskSettingsFormat';

function formatBooleanWithTranslation(t: TFunction) {
  return (value: TaskSettingValue): string =>
    value ? t('common:labels.yes') : t('common:labels.no');
}

export function buildBacktestTaskSettingDefinitions(
  t: TFunction,
  timezone: string,
  language?: string
): Array<TaskSettingDefinition<Record<string, unknown>>> {
  const formatBoolean = formatBooleanWithTranslation(t);

  return [
    { key: 'name', label: t('common:labels.name') },
    { key: 'description', label: t('common:labels.description') },
    { key: 'config_name', label: t('common:labels.strategyConfiguration') },
    { key: 'strategy_type', label: t('common:labels.strategyType') },
    { key: 'data_source', label: t('backtest:detail.dataSource') },
    { key: 'instrument', label: t('common:labels.instrument') },
    { key: 'pip_size', label: t('common:labels.pipSize') },
    {
      key: 'start_time',
      label: t('backtest:detail.startTime'),
      format: (v) => formatDateTimeSetting(v, timezone, language),
    },
    {
      key: 'end_time',
      label: t('backtest:detail.endTime'),
      format: (v) => formatDateTimeSetting(v, timezone, language),
    },
    { key: 'initial_balance', label: t('backtest:detail.initialBalance') },
    {
      key: 'account_currency',
      label: t('common:labels.accountCurrency', 'Account currency'),
    },
    {
      key: 'commission_per_trade',
      label: t('backtest:detail.commissionPerTrade'),
    },
    {
      key: 'hedging_enabled',
      label: t('common:labels.hedgingEnabled', 'Hedging enabled'),
      format: formatBoolean,
    },
    {
      key: 'sell_on_stop',
      label: t('common:labels.sellOnStop'),
      format: formatBoolean,
    },
    { key: 'tick_granularity', label: t('backtest:detail.tickGranularity') },
    {
      key: 'tick_window_value_mode',
      label: t('backtest:detail.tickWindowValueMode'),
    },
    {
      key: 'drain_duration_hours',
      label: t('backtest:form.drainDurationHours', 'Drain duration (hours)'),
    },
    {
      key: 'market_idle_pre_close_minutes',
      label: t(
        'backtest:form.marketIdlePreCloseMinutes',
        'Market pre-close idle (minutes)'
      ),
    },
    {
      key: 'market_idle_resume_delay_minutes',
      label: t(
        'backtest:form.marketIdleResumeDelayMinutes',
        'Market resume delay (minutes)'
      ),
    },
    {
      key: 'market_close_enabled',
      label: t(
        'backtest:form.marketCloseEnabled',
        'Market close window enabled'
      ),
      format: formatBoolean,
    },
    {
      key: 'market_close_weekday',
      label: t('backtest:form.marketCloseWeekday', 'Market close weekday'),
    },
    {
      key: 'market_close_hour_utc',
      label: t('backtest:form.marketCloseHourUtc', 'Market close hour UTC'),
    },
    {
      key: 'market_open_weekday',
      label: t('backtest:form.marketOpenWeekday', 'Market open weekday'),
    },
    {
      key: 'market_open_hour_utc',
      label: t('backtest:form.marketOpenHourUtc', 'Market open hour UTC'),
    },
    {
      key: 'max_tick_gap_hours',
      label: t(
        'backtest:form.maxTickGapHours',
        'Max tick gap before fail (hours)'
      ),
    },
    {
      key: 'execution_id',
      label: t('common:labels.executionId', 'Execution ID'),
    },
    { key: 'debug_options', label: t('common:debug.title') },
  ];
}

export function buildTradingTaskSettingDefinitions(
  t: TFunction
): Array<TaskSettingDefinition<Record<string, unknown>>> {
  const formatBoolean = formatBooleanWithTranslation(t);

  return [
    { key: 'name', label: t('common:labels.name') },
    { key: 'description', label: t('common:labels.description') },
    { key: 'config_name', label: t('common:labels.strategyConfiguration') },
    { key: 'strategy_type', label: t('common:labels.strategyType') },
    { key: 'instrument', label: t('common:labels.instrument') },
    { key: 'pip_size', label: t('common:labels.pipSize') },
    { key: 'account_name', label: t('trading:detail.account', 'Account') },
    {
      key: 'account_type',
      label: t('trading:detail.accountType', 'Account type'),
    },
    {
      key: 'sell_on_stop',
      label: t('common:labels.sellOnStop'),
      format: formatBoolean,
    },
    {
      key: 'dry_run',
      label: t('trading:form.dryRun', 'Dry run'),
      format: formatBoolean,
    },
    {
      key: 'hedging_enabled',
      label: t('common:labels.hedgingEnabled', 'Hedging enabled'),
      format: formatBoolean,
    },
    {
      key: 'api_retry_max_attempts',
      label: t('trading:form.apiRetryMaxAttempts', 'API retry attempts'),
    },
    {
      key: 'api_retry_backoff_base_seconds',
      label: t(
        'trading:form.apiRetryBackoffBaseSeconds',
        'API retry base backoff'
      ),
    },
    {
      key: 'api_retry_backoff_max_seconds',
      label: t(
        'trading:form.apiRetryBackoffMaxSeconds',
        'API retry max backoff'
      ),
    },
    {
      key: 'drain_duration_hours',
      label: t('trading:form.drainDurationHours', 'Drain duration (hours)'),
    },
    {
      key: 'market_idle_pre_close_minutes',
      label: t(
        'trading:form.marketIdlePreCloseMinutes',
        'Market pre-close idle (minutes)'
      ),
    },
    {
      key: 'market_idle_resume_delay_minutes',
      label: t(
        'trading:form.marketIdleResumeDelayMinutes',
        'Market resume delay (minutes)'
      ),
    },
    {
      key: 'execution_id',
      label: t('common:labels.executionId', 'Execution ID'),
    },
    { key: 'debug_options', label: t('common:debug.title') },
  ];
}
