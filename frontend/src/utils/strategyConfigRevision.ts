import type { TaskExecution } from '../types/execution';

type StrategyConfigSnapshot = NonNullable<TaskExecution['strategy_config']>;

export function getStrategyConfigSnapshotName(
  config?: StrategyConfigSnapshot | null
): string {
  return config?.current?.name ?? config?.name ?? '';
}

export function getStrategyConfigSnapshotType(
  config?: StrategyConfigSnapshot | null
): string {
  return config?.current?.strategy_type ?? config?.strategy_type ?? '';
}

export function getStrategyConfigSnapshotRevision(
  config?: StrategyConfigSnapshot | null
): number | null {
  const value =
    config?.current?.configuration_revision ?? config?.configuration_revision;
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function getStrategyConfigSnapshotHash(
  config?: StrategyConfigSnapshot | null
): string | null {
  return (
    config?.current?.configuration_hash ??
    config?.configuration_hash ??
    config?.config_hash ??
    null
  );
}

export function formatStrategyConfigRevisionLabel(
  name: string,
  revision?: number | null
): string {
  if (!revision) {
    return name;
  }
  return `${name} rev.${revision}`;
}
