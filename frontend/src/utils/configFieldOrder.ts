const FIELD_ORDER_PRIORITY: Record<string, number> = {
  r_max: 20,
  f_max: 21,
  post_r_max_base_factor: 22,
  refill_limit_enabled: 23,
  refill_up_to: 24,
  stop_loss_enabled: 100,
  stop_loss_mode: 101,
  stop_loss_pips_head: 102,
  stop_loss_pips_tail: 103,
  stop_loss_pips_flat_steps: 104,
  stop_loss_pips_gamma: 105,
  stop_loss_manual_pips: 106,
  rebuild_enabled: 107,
  rebuild_entry_price_mode: 108,
  rebuild_stop_loss_mode: 109,
  rebuild_stop_loss_manual_pips: 110,
  rebuild_take_profit_mode: 111,
  rebuild_take_profit_pips_head: 112,
  rebuild_take_profit_pips_tail: 113,
  rebuild_take_profit_pips_flat_steps: 114,
  rebuild_take_profit_pips_gamma: 115,
  rebuild_take_profit_manual_pips: 116,
  reseed_on_all_pending: 117,
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
