import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { getStrategyDisplayName } from '../../../hooks/useStrategies';
import type { Strategy } from '../../../services/api/strategies';
import type { TaskExecution } from '../../../types/execution';
import type { ConfigProperty } from '../../../types/strategy';
import { buildParameterLabelMap } from '../../../utils/strategySchemaLabels';
import { StrategyParameterDialog } from './StrategyParameterDialog';

type HistoricalStrategyConfig = NonNullable<TaskExecution['strategy_config']>;

interface HistoricalStrategyConfigDialogProps {
  open: boolean;
  onClose: () => void;
  config?: HistoricalStrategyConfig | null;
  strategies: Strategy[];
}

function resolveSnapshot(config?: HistoricalStrategyConfig | null): {
  name: string;
  strategyType: string;
  parameters: Record<string, unknown>;
} {
  const initial = config?.initial as
    | {
        name?: string;
        strategy_type?: string;
        parameters?: Record<string, unknown>;
      }
    | undefined;
  const current = config?.current;

  return {
    name: current?.name ?? config?.name ?? initial?.name ?? '',
    strategyType:
      current?.strategy_type ??
      config?.strategy_type ??
      initial?.strategy_type ??
      '',
    parameters:
      current?.parameters ?? config?.parameters ?? initial?.parameters ?? {},
  };
}

export function HistoricalStrategyConfigDialog({
  open,
  onClose,
  config,
  strategies,
}: HistoricalStrategyConfigDialogProps) {
  const { t, i18n } = useTranslation(['common']);
  const snapshot = useMemo(() => resolveSnapshot(config), [config]);

  const schemaProperties = useMemo(() => {
    const strategy = strategies.find(
      (item) => item.id === snapshot.strategyType
    );
    const schema = strategy?.config_schema as
      | { properties?: Record<string, ConfigProperty> }
      | undefined;
    return schema?.properties;
  }, [snapshot.strategyType, strategies]);

  const paramLabelMap = useMemo(
    () =>
      buildParameterLabelMap(strategies, snapshot.strategyType, i18n.language),
    [i18n.language, snapshot.strategyType, strategies]
  );

  return (
    <StrategyParameterDialog
      open={open}
      onClose={onClose}
      title={snapshot.name || t('common:labels.strategyConfiguration')}
      strategyType={getStrategyDisplayName(strategies, snapshot.strategyType)}
      parameters={snapshot.parameters}
      snapshotSchemaProperties={schemaProperties}
      paramLabelMap={paramLabelMap}
      labels={{
        strategyType: t('common:labels.strategyType'),
      }}
    />
  );
}
