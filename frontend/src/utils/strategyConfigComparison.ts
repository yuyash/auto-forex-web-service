import type { TaskExecution } from '../types/execution';
import type { ConfigProperty } from '../types/strategy';
import {
  isObsoleteStrategyParameterKey,
  isParameterVisible,
} from './strategySchemaDependsOn';

type StrategyConfigSnapshot = NonNullable<TaskExecution['strategy_config']>;

interface BooleanLabels {
  yes: string;
  no: string;
}

interface StrategyComparisonSnapshot {
  strategyType: string;
  parameters: Record<string, unknown>;
}

interface BuildStrategyComparisonDataParams {
  configs: Array<StrategyConfigSnapshot | null | undefined>;
  schemaPropertiesByType?: Map<string, Record<string, ConfigProperty>>;
  language: string;
  labels: BooleanLabels;
}

export interface StrategyComparisonData {
  configs: Record<string, string>[];
  keys: string[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === 'object' && !Array.isArray(value);
}

function hasOwnKey(obj: Record<string, unknown>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(obj, key);
}

function stableValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stableValue);
  if (!isRecord(value)) return value;
  return Object.fromEntries(
    Object.keys(value)
      .sort()
      .map((key) => [key, stableValue(value[key])])
  );
}

function languageCandidates(language: string): string[] {
  const normalized = language.trim().toLowerCase();
  if (!normalized) return [];
  const base = normalized.split('-')[0];
  return [...new Set([normalized, base])];
}

function localizedEnumLabels(
  prop: ConfigProperty | undefined,
  language: string
): Record<string, string> | undefined {
  if (!prop) return undefined;
  for (const candidate of languageCandidates(language)) {
    const labels = prop[`enum_labels_${candidate}` as keyof ConfigProperty] as
      | Record<string, string>
      | undefined;
    if (labels) return labels;
  }
  return prop.enum_labels;
}

export function resolveStrategyComparisonSnapshot(
  config?: StrategyConfigSnapshot | null
): StrategyComparisonSnapshot {
  const current = config?.current;
  const initial = isRecord(config?.initial) ? config.initial : undefined;
  const currentParameters = isRecord(current?.parameters)
    ? current.parameters
    : undefined;
  const directParameters = isRecord(config?.parameters)
    ? config.parameters
    : undefined;
  const initialParameters = isRecord(initial?.parameters)
    ? initial.parameters
    : undefined;
  const initialStrategyType =
    typeof initial?.strategy_type === 'string' ? initial.strategy_type : '';

  return {
    strategyType:
      current?.strategy_type ??
      config?.strategy_type ??
      initialStrategyType ??
      '',
    parameters:
      currentParameters ?? directParameters ?? initialParameters ?? {},
  };
}

export function formatStrategyComparisonValue(
  value: unknown,
  prop: ConfigProperty | undefined,
  language: string,
  labels: BooleanLabels
): string {
  if (value === null || value === undefined || value === '') return '-';

  if (typeof value === 'string') {
    const enumLabels = localizedEnumLabels(prop, language);
    return enumLabels?.[value] ?? value;
  }

  if (typeof value === 'boolean') return value ? labels.yes : labels.no;
  if (typeof value === 'number' || typeof value === 'bigint') {
    return String(value);
  }

  if (Array.isArray(value)) {
    return value
      .map((item) =>
        formatStrategyComparisonValue(item, undefined, language, labels)
      )
      .join(', ');
  }

  if (typeof value === 'object') {
    return JSON.stringify(stableValue(value), null, 2);
  }

  return String(value);
}

export function buildStrategyComparisonData({
  configs,
  schemaPropertiesByType = new Map(),
  language,
  labels,
}: BuildStrategyComparisonDataParams): StrategyComparisonData {
  const snapshots = configs.map(resolveStrategyComparisonSnapshot);
  const keySet = new Set<string>();
  const strategyTypes = [
    ...new Set(snapshots.map((snapshot) => snapshot.strategyType)),
  ];

  for (const strategyType of strategyTypes) {
    const schemaProperties = schemaPropertiesByType.get(strategyType);
    if (!schemaProperties) continue;
    const snapshotsForType = snapshots.filter(
      (snapshot) => snapshot.strategyType === strategyType
    );

    for (const key of Object.keys(schemaProperties)) {
      if (
        snapshotsForType.some((snapshot) =>
          isParameterVisible(key, snapshot.parameters, schemaProperties)
        )
      ) {
        keySet.add(key);
      }
    }
  }

  for (const snapshot of snapshots) {
    const schemaProperties = schemaPropertiesByType.get(snapshot.strategyType);
    for (const key of Object.keys(snapshot.parameters)) {
      if (isObsoleteStrategyParameterKey(key)) continue;

      if (schemaProperties) {
        if (!isParameterVisible(key, snapshot.parameters, schemaProperties)) {
          continue;
        }
        if (!(key in schemaProperties)) {
          keySet.add(key);
        }
        continue;
      }

      keySet.add(key);
    }
  }

  const orderedKeys = [...keySet];

  const formattedConfigs = snapshots.map((snapshot) => {
    const schemaProperties = schemaPropertiesByType.get(snapshot.strategyType);
    const result: Record<string, string> = {};

    for (const key of orderedKeys) {
      if (
        schemaProperties &&
        !isParameterVisible(key, snapshot.parameters, schemaProperties)
      ) {
        continue;
      }

      const prop = schemaProperties?.[key];
      const rawValue = hasOwnKey(snapshot.parameters, key)
        ? snapshot.parameters[key]
        : prop?.default;

      if (rawValue === undefined) continue;
      result[key] = formatStrategyComparisonValue(
        rawValue,
        prop,
        language,
        labels
      );
    }

    return result;
  });

  return {
    configs: formattedConfigs,
    keys: orderedKeys.filter((key) =>
      formattedConfigs.some((config) => hasOwnKey(config, key))
    ),
  };
}
