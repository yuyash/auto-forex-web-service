import { useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useTranslation } from 'react-i18next';
import { queryKeys } from '../config/reactQuery';
import { configurationsApi } from '../services/api/configurations';
import type { StrategyConfig } from '../types/configuration';
import { Breadcrumbs, PageContainer } from '../components/common';
import {
  SettingsComparisonTable,
  type SettingsComparisonItem,
} from '../components/comparison/SettingsComparisonTable';
import { parseCompareIds } from '../utils/compareParams';
import { buildParameterLabelMap } from '../utils/strategySchemaLabels';
import { getStrategyDisplayName, useStrategies } from '../hooks/useStrategies';

function configurationSettings(
  config: StrategyConfig,
  strategyName: string
): Record<string, unknown> {
  return {
    name: config.name,
    strategy_type: strategyName,
    description: config.description,
    revision: config.revision,
    config_hash: config.config_hash,
    parameters: config.parameters,
  };
}

export default function ConfigurationComparePage() {
  const { t, i18n } = useTranslation(['common', 'configuration']);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const ids = useMemo(() => parseCompareIds(searchParams), [searchParams]);
  const { strategies } = useStrategies();

  const queries = useQueries({
    queries: ids.map((id) => ({
      queryKey: queryKeys.configurations.detail(id),
      queryFn: () => configurationsApi.get(id),
      enabled: ids.length >= 2,
    })),
  });

  const isLoading = queries.some((query) => query.isLoading);
  const error = queries.find((query) => query.error)?.error;
  const configurations = queries
    .map((query) => query.data)
    .filter((config): config is StrategyConfig => Boolean(config));

  const labelMap = useMemo(() => {
    const map = new Map<string, string>([
      ['name', t('labels.name')],
      ['strategy_type', t('labels.strategyType')],
      ['description', t('labels.description')],
      [
        'revision',
        t('configuration:card.revision', { defaultValue: 'Revision' }),
      ],
      [
        'config_hash',
        t('comparison.configHash', { defaultValue: 'Config Hash' }),
      ],
    ]);

    for (const config of configurations) {
      const parameterLabels = buildParameterLabelMap(
        strategies,
        config.strategy_type,
        i18n.language
      );
      for (const [key, label] of parameterLabels) {
        map.set(`parameters.${key}`, label);
      }
    }

    return map;
  }, [configurations, i18n.language, strategies, t]);

  const items = useMemo<SettingsComparisonItem[]>(
    () =>
      configurations.map((config) => {
        const strategyName = getStrategyDisplayName(
          strategies,
          config.strategy_type
        );
        return {
          id: config.id,
          title: config.name,
          subtitle: strategyName,
          settings: configurationSettings(config, strategyName),
        };
      }),
    [configurations, strategies]
  );

  return (
    <PageContainer sx={{ mt: { xs: 1, sm: 1.5 }, mb: 1.5 }}>
      <Breadcrumbs />
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 1,
          flexWrap: 'wrap',
          mb: 1,
        }}
      >
        <Typography
          variant="h4"
          component="h1"
          sx={{ fontSize: { xs: '1.25rem', sm: '1.5rem' }, fontWeight: 600 }}
        >
          {t('comparison.configurationTitle', {
            defaultValue: 'Compare Strategy Configurations',
          })}
        </Typography>
        <Button
          variant="outlined"
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/configurations')}
        >
          {t('breadcrumbs.configurations')}
        </Button>
      </Box>

      {ids.length < 2 ? (
        <Alert severity="info">
          {t('comparison.selectAtLeastTwo', {
            defaultValue: 'Select at least two items to compare.',
          })}
        </Alert>
      ) : isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Alert severity="error">
          {error instanceof Error ? error.message : String(error)}
        </Alert>
      ) : (
        <SettingsComparisonTable
          items={items}
          labelMap={labelMap}
          keyOrder={[
            'name',
            'strategy_type',
            'description',
            'revision',
            'config_hash',
            'parameters',
          ]}
        />
      )}
    </PageContainer>
  );
}
