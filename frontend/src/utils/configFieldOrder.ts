const FIELD_ORDER_PRIORITY: Record<string, number> = {
  stop_loss_enabled: 100,
  stop_loss_mode: 101,
  stop_loss_pips_head: 102,
  stop_loss_pips_tail: 103,
  stop_loss_pips_flat_steps: 104,
  stop_loss_pips_gamma: 105,
  stop_loss_manual_pips: 106,
  rebuild_enabled: 107,
  complete_cycle_when_empty: 108,
  disable_loss_cut_after_rebuild: 109,
  rebuild_stop_loss_mode: 110,
  rebuild_stop_loss_manual_pips: 111,
  rebuild_take_profit_mode: 112,
  rebuild_take_profit_pips_head: 113,
  rebuild_take_profit_pips_tail: 114,
  rebuild_take_profit_pips_flat_steps: 115,
  rebuild_take_profit_pips_gamma: 116,
  rebuild_take_profit_manual_pips: 117,
  grid_order_validation_enabled: 118,
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
