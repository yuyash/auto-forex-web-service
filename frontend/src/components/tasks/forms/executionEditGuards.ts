const EXECUTION_SETTING_FIELDS = new Set([
  'config_id',
  'config',
  'instrument',
  'pip_size',
  'data_source',
  'start_time',
  'end_time',
  'initial_balance',
  'account_currency',
  'tick_granularity',
  'tick_window_value_mode',
  'hedging_enabled',
  'account_id',
]);

export function hasDirtyExecutionSettings(
  dirtyFields: Record<string, unknown> | undefined
): boolean {
  if (!dirtyFields) return false;
  return Object.keys(dirtyFields).some((field) =>
    EXECUTION_SETTING_FIELDS.has(field)
  );
}
