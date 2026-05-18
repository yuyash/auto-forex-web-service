import type {
  CycleTrade,
  StrategyCycle,
  StrategyGridLayer,
  StrategyGridSlot,
  StrategyGridSlotState,
  StrategyGridState,
} from '../../../../types/strategyVisualization';

function getSlotBuildCountKey(layer: number, slot: number): string {
  return `${layer}:${slot}`;
}

function isOpenTrade(trade: CycleTrade): boolean {
  return (
    trade.execution_method === 'open_position' ||
    trade.execution_method === 'rebuild_position'
  );
}

function resolveTradeSlot(
  cycle: StrategyCycle,
  trade: CycleTrade,
  slotByPositionId: Map<string, { layer: number; slot: number }>
): { layer: number; slot: number } | null {
  if (trade.position_id) {
    const existing = slotByPositionId.get(trade.position_id);
    if (existing) {
      return existing;
    }
  }

  const isInitialEntry = trade.id === cycle.cycle_id;
  const layer = isInitialEntry ? 1 : trade.layer_index;
  const slot = isInitialEntry ? 0 : trade.retracement_count;

  if (layer == null || slot == null) {
    return null;
  }

  const resolved = { layer, slot };
  if (trade.position_id && isOpenTrade(trade)) {
    slotByPositionId.set(trade.position_id, resolved);
  }
  return resolved;
}

export function buildSlotBuildCounts(
  cycle: StrategyCycle | null
): Record<string, number> {
  if (!cycle) return {};

  const countsFromGridState = slotBuildCountsFromGridState(cycle.grid_state);
  if (countsFromGridState) return countsFromGridState;

  const uniquePositionIdsBySlot = new Map<string, Set<string>>();
  const slotByPositionId = new Map<string, { layer: number; slot: number }>();

  for (const trade of cycle.trades) {
    if (!isOpenTrade(trade) || !trade.position_id) continue;

    const resolved = resolveTradeSlot(cycle, trade, slotByPositionId);
    if (!resolved) continue;

    const key = getSlotBuildCountKey(resolved.layer, resolved.slot);
    const positionIds = uniquePositionIdsBySlot.get(key) ?? new Set<string>();
    positionIds.add(trade.position_id);
    uniquePositionIdsBySlot.set(key, positionIds);
  }

  return Object.fromEntries(
    Array.from(uniquePositionIdsBySlot.entries(), ([key, positionIds]) => [
      key,
      positionIds.size,
    ])
  );
}

function slotBuildCountsFromGridState(
  gridState?: StrategyGridState | null
): Record<string, number> | null {
  if (!gridState) return null;

  const counts: Record<string, number> = {};
  let foundPersistedCount = false;
  for (const layer of gridState.layers) {
    for (const slot of layer.slots) {
      if (typeof slot.build_count !== 'number') continue;
      foundPersistedCount = true;
      counts[getSlotBuildCountKey(layer.layer, slot.slot)] = slot.build_count;
    }
  }

  return foundPersistedCount ? counts : null;
}

export function gridHasPositions(gridState: StrategyGridState): boolean {
  return gridState.layers.some((layer) =>
    layer.slots.some((slot) => slot.state !== 'empty')
  );
}

export function buildDisplayGridState(
  cycle: StrategyCycle | null
): StrategyGridState | null | undefined {
  if (!cycle?.grid_state) return cycle?.grid_state;

  const currentGridState = cycle.grid_state;
  const slotByPositionId = new Map<string, { layer: number; slot: number }>();
  const historicalStateByKey = new Map<string, StrategyGridSlotState>();
  let maxLayer = 0;
  let maxSlot = 0;

  const updateHistoricalState = (
    layer: number,
    slot: number,
    nextState: StrategyGridSlotState
  ) => {
    maxLayer = Math.max(maxLayer, layer);
    maxSlot = Math.max(maxSlot, slot);
    const key = getSlotBuildCountKey(layer, slot);
    historicalStateByKey.set(key, nextState);
  };

  for (const trade of cycle.trades) {
    const resolved = resolveTradeSlot(cycle, trade, slotByPositionId);
    if (!resolved) continue;

    if (trade.execution_method === 'rebuild_position') {
      updateHistoricalState(resolved.layer, resolved.slot, 'rebuilt');
      continue;
    }

    if (trade.execution_method === 'stop_loss') {
      updateHistoricalState(resolved.layer, resolved.slot, 'stopped');
      continue;
    }

    if (isOpenTrade(trade)) {
      updateHistoricalState(resolved.layer, resolved.slot, 'filled');
      continue;
    }

    updateHistoricalState(resolved.layer, resolved.slot, 'empty');
  }

  for (const layer of currentGridState.layers) {
    maxLayer = Math.max(maxLayer, layer.layer);
    for (const slot of layer.slots) {
      maxSlot = Math.max(maxSlot, slot.slot);
    }
  }

  const currentStateByKey = new Map<string, StrategyGridSlot>();
  for (const layer of currentGridState.layers) {
    for (const slot of layer.slots) {
      currentStateByKey.set(getSlotBuildCountKey(layer.layer, slot.slot), slot);
    }
  }

  const layers: StrategyGridLayer[] = [];
  const summary = {
    filled: 0,
    stopped: 0,
    rebuilt: 0,
    empty: 0,
    layer_count: 0,
    slot_count_per_layer: maxSlot + 1,
  };

  for (let layer = 1; layer <= maxLayer; layer++) {
    const slots: StrategyGridSlot[] = [];
    for (let slot = 0; slot <= maxSlot; slot++) {
      const key = getSlotBuildCountKey(layer, slot);
      const currentSlot = currentStateByKey.get(key);
      const historicalState = historicalStateByKey.get(key);

      let state: StrategyGridSlotState = 'empty';
      if (currentSlot && currentSlot.state !== 'empty') {
        state = currentSlot.state;
      } else if (
        historicalState === 'filled' ||
        historicalState === 'rebuilt' ||
        historicalState === 'stopped'
      ) {
        state = historicalState;
      }

      summary[state] += 1;
      slots.push({
        slot,
        state,
        position_id: currentSlot?.position_id ?? null,
        build_count: currentSlot?.build_count,
      });
    }

    layers.push({ layer, slots });
  }

  summary.layer_count = layers.length;

  return {
    layers,
    summary,
  };
}
