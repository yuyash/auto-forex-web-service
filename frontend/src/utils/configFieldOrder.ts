const FIELD_ORDER_PRIORITY: Record<string, number> = {
  r_max: 20,
  f_max: 21,
  post_r_max_base_factor: 22,
  refill_limit_enabled: 23,
  refill_up_to: 24,
  warmup_enabled: 40,
  warmup_initial_unit_ratio_pct: 41,
  warmup_unit_ramp_steps: 42,
  warmup_start_gate_enabled: 43,
  warmup_gate_spread_enabled: 44,
  warmup_gate_max_spread_pips: 45,
  warmup_gate_volatility_enabled: 46,
  warmup_gate_volatility_window_ticks: 47,
  warmup_gate_max_volatility_pips: 48,
  warmup_gate_trend_enabled: 49,
  warmup_gate_trend_window_ticks: 50,
  warmup_gate_max_trend_pips: 51,
  warmup_position_limit_enabled: 52,
  warmup_max_positions: 53,
  warmup_rebuild_limit_enabled: 54,
  warmup_max_rebuilds_per_tick: 55,
  warmup_completion_mode: 56,
  warmup_min_elapsed_minutes: 57,
  warmup_required_tp_closes: 58,
  stop_loss_enabled: 100,
  stop_loss_mode: 101,
  stop_loss_pips_head: 102,
  stop_loss_pips_tail: 103,
  stop_loss_pips_flat_steps: 104,
  stop_loss_pips_gamma: 105,
  stop_loss_manual_pips: 106,
  rebuild_enabled: 107,
  rebuild_cooldown_seconds: 108,
  rebuild_entry_price_mode: 109,
  rebuild_entry_buffer_pips: 110,
  rebuild_stop_loss_mode: 111,
  rebuild_stop_loss_manual_pips: 112,
  rebuild_take_profit_mode: 113,
  rebuild_take_profit_pips_head: 114,
  rebuild_take_profit_pips_tail: 115,
  rebuild_take_profit_pips_flat_steps: 116,
  rebuild_take_profit_pips_gamma: 117,
  rebuild_take_profit_manual_pips: 118,
  reseed_on_all_pending: 119,
};

function fieldPriority(fieldName: string): number {
  return FIELD_ORDER_PRIORITY[fieldName] ?? Number.MAX_SAFE_INTEGER;
}

export function orderConfigFieldTuples<T>(
  fields: [string, T][]
): [string, T][] {
  return [...fields].sort((a, b) => fieldPriority(a[0]) - fieldPriority(b[0]));
}

export function orderConfigEntries<T extends { key: string }>(
  entries: T[]
): T[] {
  return [...entries].sort(
    (a, b) => fieldPriority(a.key) - fieldPriority(b.key)
  );
}
