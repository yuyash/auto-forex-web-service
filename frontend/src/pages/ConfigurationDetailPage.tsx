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
import { Edit as EditIcon } from '@mui/icons-material';
import { Breadcrumbs } from '../components/common';
import { useConfiguration } from '../hooks/useConfigurations';
import { useStrategies, getStrategyDisplayName } from '../hooks/useStrategies';
import { STRATEGY_CONFIG_SCHEMAS } from '../components/configurations/strategyConfigSchemas';
import type { ConfigProperty, ConfigSchema } from '../types/strategy';

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
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export default function ConfigurationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const configId = id || '';
  const navigate = useNavigate();

  const { data: configuration, isLoading, error } = useConfiguration(configId);
  const { strategies } = useStrategies();

  // Resolve the schema for the current strategy type.
  // Prefer the frontend-defined schema (which includes group metadata)
  // over the API-returned one.
  const configSchema: ConfigSchema | undefined = (() => {
    if (!configuration) return undefined;
    const frontendSchema = STRATEGY_CONFIG_SCHEMAS[configuration.strategy_type];
    if (frontendSchema) return frontendSchema;
    const matched = strategies.find(
      (s) => s.id === configuration.strategy_type
    );
    return matched?.config_schema as ConfigSchema | undefined;
  })();

  /** Look up a property definition from the schema. */
  const propMeta = (key: string): ConfigProperty | undefined =>
    configSchema?.properties?.[key];

  /**
   * Friendly titles for parameters that may exist in saved configs
   * but are not part of the current schema (backend-only or legacy keys).
   */
  const EXTRA_PARAM_TITLES: Record<string, string> = {
    leverage: 'Leverage',
    floor_profiles: 'Floor Profiles',
    candle_lookback_count: 'Candle Lookback Count',
    candle_granularity_seconds: 'Candle Granularity (seconds)',
    margin_closeout_threshold: 'Margin Closeout Threshold',
  };

  /** Friendly display label for a parameter key. */
  const displayLabel = (key: string): string => {
    const meta = propMeta(key);
    if (meta?.title) return meta.title;
    if (EXTRA_PARAM_TITLES[key]) return EXTRA_PARAM_TITLES[key];
    return key
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
  };

  /** Build grouped parameter entries preserving schema order. */
  const groupedParams = (() => {
    if (!configuration?.parameters) return [];
    const params = configuration.parameters;
    const groups: Array<{
      name: string;
      entries: Array<{ key: string; value: unknown; description?: string }>;
    }> = [];
    const groupMap = new Map<
      string,
      Array<{ key: string; value: unknown; description?: string }>
    >();
    const seenGroups: string[] = [];

    // If we have a schema, iterate in schema order
    if (configSchema?.properties) {
      Object.entries(configSchema.properties).forEach(([key, prop]) => {
        if (!(key in params)) return;
        const groupName = prop.group || 'Other Parameters';
        if (!groupMap.has(groupName)) {
          groupMap.set(groupName, []);
          seenGroups.push(groupName);
        }
        groupMap.get(groupName)!.push({
          key,
          value: params[key],
          description: prop.description,
        });
      });
      // Add any params not in schema into "Other Parameters"
      const otherGroup = 'Other Parameters';
      Object.keys(params).forEach((key) => {
        if (configSchema.properties[key]) return;
        if (!groupMap.has(otherGroup)) {
          groupMap.set(otherGroup, []);
          seenGroups.push(otherGroup);
        }
        groupMap.get(otherGroup)!.push({ key, value: params[key] });
      });
    } else {
      // No schema — flat list
      const entries = Object.entries(params).map(([key, value]) => ({
        key,
        value,
      }));
      groupMap.set('', entries);
      seenGroups.push('');
    }

    seenGroups.forEach((name) => {
      const entries = groupMap.get(name);
      if (entries && entries.length > 0) {
        groups.push({ name, entries });
      }
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
          Failed to load configuration
        </Alert>
      )}

      {!isLoading && !error && !configuration && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Configuration not found
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
                Strategy configuration details
              </Typography>
            </Box>

            <Button
              variant="contained"
              startIcon={<EditIcon />}
              onClick={() =>
                navigate(`/configurations/${configuration.id}/edit`)
              }
            >
              Edit
            </Button>
          </Box>

          <Paper elevation={2} sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
              <Chip
                label={getStrategyDisplayName(
                  strategies,
                  configuration.strategy_type
                )}
                color="primary"
                size="small"
                variant="outlined"
              />
              <Chip
                label={`Created ${formatDate(configuration.created_at)}`}
                size="small"
                variant="outlined"
              />
              {configuration.is_in_use && (
                <Chip
                  label="In Use"
                  color="success"
                  size="small"
                  variant="filled"
                />
              )}
            </Box>

            {configuration.description && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Description
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {configuration.description}
                </Typography>
              </Box>
            )}

            <Divider sx={{ my: 2 }} />

            <Typography variant="subtitle2" gutterBottom>
              Parameters
            </Typography>

            {groupedParams.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No parameters saved for this configuration.
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
                            {formatValue(value)}
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
