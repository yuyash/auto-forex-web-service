import type { TaskExecution } from '../types/execution';

type StrategyConfigSnapshot = NonNullable<TaskExecution['strategy_config']>;

interface CanEditDisplayedStrategyConfigParams {
  configId?: string | number | null;
  config?: StrategyConfigSnapshot | null;
  isViewingHistorical?: boolean;
  currentRevision?: number | null;
  currentHash?: string | null;
}

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

export function isStrategyConfigSnapshotCurrent(
  config: StrategyConfigSnapshot | null | undefined,
  currentRevision?: number | null,
  currentHash?: string | null
): boolean {
  const snapshotHash = getStrategyConfigSnapshotHash(config);
  if (snapshotHash && currentHash) {
    return snapshotHash === currentHash;
  }

  const snapshotRevision = getStrategyConfigSnapshotRevision(config);
  return Boolean(
    snapshotRevision &&
      currentRevision &&
      Number(snapshotRevision) === Number(currentRevision)
  );
}

export function canEditDisplayedStrategyConfig({
  configId,
  config,
  isViewingHistorical = false,
  currentRevision,
  currentHash,
}: CanEditDisplayedStrategyConfigParams): boolean {
  if (!configId) {
    return false;
  }

  if (!isViewingHistorical) {
    return true;
  }

  return Boolean(
    config &&
      String(config.id) === String(configId) &&
      isStrategyConfigSnapshotCurrent(config, currentRevision, currentHash)
  );
}

export function formatStrategyConfigRevisionLabel(
  name: string,
  revision?: number | null
): string {
  if (!revision) {
    return name;
  }
  return `${name} Rev.${revision}`;
}
