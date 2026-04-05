import { useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Divider,
  Paper,
  Typography,
} from '@mui/material';
import {
  Edit as EditIcon,
  ContentCopy as ContentCopyIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { Breadcrumbs } from '../components/common';
import { useConfiguration } from '../hooks/useConfigurations';
import { useCopyConfiguration } from '../hooks/useConfigurationMutations';
import { useStrategies, getStrategyDisplayName } from '../hooks/useStrategies';
import { STRATEGY_CONFIG_SCHEMAS } from '../components/configurations/strategyConfigSchemas';
import type { ConfigProperty, ConfigSchema } from '../types/strategy';

/** Keys excluded from the detail view (not user-facing). */
const HIDDEN_KEYS = new Set(['pip_size']);

function formatDate(dateString?: string) {
  if (!dateString) return '';
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean')
    return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export default function ConfigurationDetailPage() {
  const { t, i18n } = useTranslation(['configuration', 'common']);
  const { id } = useParams<{ id: string }>();
  const configId = id || '';
  const navigate = useNavigate();

  const { data: configuration, isLoading, error } = useConfiguration(configId);
  const { strategies } = useStrategies();
  const copyMutation = useCopyConfiguration({
    onSuccess: (copied) => {
      navigate(`/configurations/${copied.id}`);
    },
  });

  const configSchema: ConfigSchema | undefined = (() => {
    if (!configuration) return undefined;
    const frontendSchema = STRATEGY_CONFIG_SCHEMAS[configuration.strategy_type];
    if (frontendSchema) return frontendSchema;
    const matched = strategies.find(
      (s) => s.id === configuration.strategy_type
    );
    return matched?.config_schema as ConfigSchema | undefined;
  })();

  /** Resolve a localized schema field (same pattern as StrategyConfigForm). */
  const localized = useCallback(
    (
      prop: ConfigProperty,
      field: 'title' | 'description' | 'group'
    ): string | undefined => {
      const langKey = `${field}_${i18n.language}` as keyof ConfigProperty;
      return (prop[langKey] as string | undefined) ?? prop[field];
    },
    [i18n.language]
  );

  /** Resolve a localized enum label. */
  const localizedEnumLabel = useCallback(
    (prop: ConfigProperty, value: string): string | undefined => {
      const langKey = `enum_labels_${i18n.language}` as keyof ConfigProperty;
      const langLabels = prop[langKey] as Record<string, string> | undefined;
      if (langLabels?.[value]) return langLabels[value];
      return prop.enum_labels?.[value];
    },
    [i18n.language]
  );

  /** Display label for a parameter key. */
  const displayLabel = (key: string): string => {
    const meta = configSchema?.properties?.[key];
    if (meta) {
      const l = localized(meta, 'title');
      if (l) return l;
    }
    return key
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
  };

  /** Format a parameter value, resolving enum labels when available. */
  const displayValue = (key: string, value: unknown): string => {
    const meta = configSchema?.properties?.[key];
    if (meta && typeof value === 'string') {
      const label = localizedEnumLabel(meta, value);
      if (label) return label;
    }
    return formatValue(value);
  };

  /** Build grouped parameter entries preserving schema order. */
  const groupedParams = (() => {
    if (!configuration?.parameters) return [];
    const params = configuration.parameters;
    type Entry = { key: string; value: unknown; description?: string };
    const groups: Array<{ name: string; entries: Entry[] }> = [];
    const groupMap = new Map<string, Entry[]>();
    const seenGroups: string[] = [];

    if (configSchema?.properties) {
      Object.entries(configSchema.properties).forEach(([key, prop]) => {
        if (!(key in params) || HIDDEN_KEYS.has(key)) return;
        const groupName =
          localized(prop, 'group') || t('configuration:form.otherParameters');
        if (!groupMap.has(groupName)) {
          groupMap.set(groupName, []);
          seenGroups.push(groupName);
        }
        groupMap.get(groupName)!.push({
          key,
          value: params[key],
          description: localized(prop, 'description'),
        });
      });
      const otherGroup = t('configuration:form.otherParameters');
      Object.keys(params).forEach((key) => {
        if (configSchema.properties[key] || HIDDEN_KEYS.has(key)) return;
        if (!groupMap.has(otherGroup)) {
          groupMap.set(otherGroup, []);
          seenGroups.push(otherGroup);
        }
        groupMap.get(otherGroup)!.push({ key, value: params[key] });
      });
    } else {
      const entries = Object.entries(params)
        .filter(([key]) => !HIDDEN_KEYS.has(key))
        .map(([key, value]) => ({ key, value }));
      groupMap.set('', entries);
      seenGroups.push('');
    }

    seenGroups.forEach((name) => {
      const entries = groupMap.get(name);
      if (entries && entries.length > 0) groups.push({ name, entries });
    });
    return groups;
  })();

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 4, px: 3 }}>
      <Breadcrumbs />

      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      )}

      {!isLoading && error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {t('common:errors.fetchFailed')}
        </Alert>
      )}

      {!isLoading && !error && !configuration && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {t('common:errors.taskNotFound')}
        </Alert>
      )}

      {!isLoading && !error && configuration && (
        <>
          <Box
            sx={{
              mb: 3,
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              gap: 2,
              flexWrap: 'wrap',
            }}
          >
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="h4" gutterBottom>
                {configuration.name}
              </Typography>
              <Typography variant="body1" color="text.secondary">
                {t('configuration:pages.detailSubtitle')}
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="outlined"
                startIcon={<ContentCopyIcon />}
                onClick={() => copyMutation.mutate({ id: configuration.id })}
              >
                {t('common:actions.copy')}
              </Button>
              <Button
                variant="contained"
                startIcon={<EditIcon />}
                onClick={() =>
                  navigate(`/configurations/${configuration.id}/edit`)
                }
              >
                {t('common:actions.edit')}
              </Button>
            </Box>
          </Box>

          <Paper elevation={2} sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
              <Chip
                label={getStrategyDisplayName(
                  strategies,
                  configuration.strategy_type
                )}
                color="primary"
                variant="outlined"
              />
              <Chip
                label={`${t('common:labels.created')} ${formatDate(configuration.created_at)}`}
                variant="outlined"
              />
              {configuration.is_in_use && (
                <Chip
                  label={t('common:labels.inUse')}
                  color="success"
                  variant="filled"
                />
              )}
            </Box>

            {configuration.description && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  {t('common:labels.description')}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {configuration.description}
                </Typography>
              </Box>
            )}

            <Divider sx={{ my: 2 }} />

            <Typography variant="subtitle2" gutterBottom>
              {t('common:labels.parameters')}
            </Typography>

            {groupedParams.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                {t('configuration:empty.noParametersSaved')}
              </Typography>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {groupedParams.map(({ name: groupName, entries }, groupIdx) => (
                  <Box key={groupName || '__ungrouped'}>
                    {groupName && (
                      <>
                        {groupIdx > 0 && <Divider sx={{ mt: 1, mb: 1 }} />}
                        <Typography
                          variant="subtitle2"
                          color="text.secondary"
                          sx={{ display: 'block', mb: 0.5 }}
                        >
                          {groupName}
                        </Typography>
                      </>
                    )}
                    <Box
                      sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 0.75,
                      }}
                    >
                      {entries.map(({ key, value, description }) => (
                        <Box
                          key={key}
                          sx={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'baseline',
                            gap: 2,
                          }}
                        >
                          <Box sx={{ minWidth: 0 }}>
                            <Typography
                              variant="body2"
                              sx={{ fontWeight: 600 }}
                            >
                              {displayLabel(key)}
                            </Typography>
                            {description && (
                              <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{ display: 'block', lineHeight: 1.3 }}
                              >
                                {description}
                              </Typography>
                            )}
                          </Box>
                          <Typography
                            variant="body2"
                            color="text.secondary"
                            sx={{
                              textAlign: 'right',
                              wordBreak: 'break-word',
                              flexShrink: 0,
                            }}
                          >
                            {displayValue(key, value)}
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                  </Box>
                ))}
              </Box>
            )}
          </Paper>
        </>
      )}
    </Container>
  );
}
