import {
  Alert,
  Box,
  Chip,
  LinearProgress,
  Paper,
  Stack,
  Typography,
  alpha,
} from '@mui/material';
import type { ReactNode } from 'react';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import TimelineIcon from '@mui/icons-material/Timeline';
import type {
  AdaptiveNetMetricSignal,
  AdaptiveNetStrategyState,
  StrategyCycle,
  StrategyCyclesSummary,
} from '../../../../types/strategyVisualization';
import {
  formatAppNumber,
  formatAppPercent,
} from '../../../../utils/numberFormat';
import { useTranslation } from 'react-i18next';

interface AdaptiveNetStrategyPanelProps {
  state?: AdaptiveNetStrategyState | null;
  cycles: StrategyCycle[];
  summary: StrategyCyclesSummary;
}

function toNumber(value: string | number | undefined | null): number {
  if (value === undefined || value === null || value === '') return 0;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function formatProbability(value?: string): string {
  return formatAppPercent(toNumber(value) * 100, 1);
}

function formatUnits(value?: number): string {
  return formatAppNumber(value ?? 0, {
    maximumFractionDigits: 0,
    signed: true,
  });
}

function directionIcon(units?: number) {
  if (!units) return <SwapHorizIcon fontSize="small" />;
  return units > 0 ? (
    <TrendingUpIcon fontSize="small" />
  ) : (
    <TrendingDownIcon fontSize="small" />
  );
}

function metricTone(score: number): 'success' | 'error' | 'default' {
  if (score > 0.05) return 'success';
  if (score < -0.05) return 'error';
  return 'default';
}

export function AdaptiveNetStrategyPanel({
  state,
  cycles,
  summary,
}: AdaptiveNetStrategyPanelProps) {
  const { t } = useTranslation('strategy');
  const decision = state?.latest_decision ?? null;
  const metrics = decision?.metric_signals ?? state?.metric_signals ?? [];
  const currentNet = state?.current_net_units ?? 0;
  const targetNet = decision?.target_net_units ?? state?.target_net_units ?? 0;
  const orderUnits = decision?.order_units ?? targetNet - currentNet;
  const activeTrades = cycles
    .flatMap((cycle) => cycle.trades)
    .filter((trade) => trade.execution_method === 'open_position')
    .slice(-6)
    .reverse();
  const directionLabel = (units?: number): string => {
    if (!units) return t('adaptiveNet.directions.flat');
    return units > 0
      ? t('adaptiveNet.directions.netLong')
      : t('adaptiveNet.directions.netShort');
  };

  return (
    <Stack spacing={2}>
      {!state && <Alert severity="info">{t('adaptiveNet.noState')}</Alert>}

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: {
            xs: '1fr',
            md: 'repeat(4, minmax(0, 1fr))',
          },
          gap: 1.5,
        }}
      >
        <SummaryTile
          label={t('adaptiveNet.summary.currentNet')}
          value={formatUnits(currentNet)}
          caption={directionLabel(currentNet)}
          icon={directionIcon(currentNet)}
        />
        <SummaryTile
          label={t('adaptiveNet.summary.targetNet')}
          value={formatUnits(targetNet)}
          caption={directionLabel(targetNet)}
          icon={<TimelineIcon fontSize="small" />}
        />
        <SummaryTile
          label={t('adaptiveNet.summary.nextOrder')}
          value={formatUnits(orderUnits)}
          caption={
            orderUnits === 0
              ? t('adaptiveNet.summary.noRebalance')
              : t('adaptiveNet.summary.deltaToTarget')
          }
          icon={<SwapHorizIcon fontSize="small" />}
        />
        <SummaryTile
          label={t('adaptiveNet.summary.openPosition')}
          value={formatAppNumber(state?.open_units ?? 0, {
            maximumFractionDigits: 0,
          })}
          caption={
            state?.open_position_id?.slice(0, 8) ??
            t('adaptiveNet.summary.noPosition')
          }
          icon={directionIcon(currentNet)}
        />
      </Box>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack spacing={1.5}>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            justifyContent="space-between"
            spacing={1}
          >
            <Box>
              <Typography variant="h6">
                {t('adaptiveNet.prediction.title')}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {t('adaptiveNet.prediction.description')}
              </Typography>
            </Box>
            <Stack direction="row" spacing={1} flexWrap="wrap">
              <Chip
                size="small"
                color="success"
                label={t('adaptiveNet.prediction.longProbability', {
                  value: formatProbability(decision?.probability_long),
                })}
              />
              <Chip
                size="small"
                color="error"
                label={t('adaptiveNet.prediction.shortProbability', {
                  value: formatProbability(decision?.probability_short),
                })}
              />
              <Chip
                size="small"
                label={t('adaptiveNet.prediction.riskMultiplier', {
                  value: formatAppNumber(toNumber(decision?.risk_multiplier), {
                    maximumFractionDigits: 2,
                  }),
                })}
              />
            </Stack>
          </Stack>

          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
              gap: 2,
            }}
          >
            <SignalBar
              label={t('adaptiveNet.prediction.directionalEdge')}
              value={toNumber(decision?.edge)}
            />
            <SignalBar
              label={t('adaptiveNet.prediction.decisionConfidence')}
              value={toNumber(decision?.confidence)}
              absolute
            />
          </Box>
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack spacing={1.5}>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            justifyContent="space-between"
            spacing={1}
          >
            <Box>
              <Typography variant="h6">
                {t('adaptiveNet.metrics.title')}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {t('adaptiveNet.metrics.description')}
              </Typography>
            </Box>
            <Chip
              size="small"
              label={t('adaptiveNet.metrics.count', { count: metrics.length })}
              variant="outlined"
            />
          </Stack>

          <Box sx={{ display: 'grid', gap: 1 }}>
            {metrics.map((metric) => (
              <MetricRow key={metric.name} metric={metric} />
            ))}
            {metrics.length === 0 && (
              <Typography variant="body2" color="text.secondary">
                {t('adaptiveNet.metrics.warmingUp')}
              </Typography>
            )}
          </Box>
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack spacing={1.5}>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            justifyContent="space-between"
            spacing={1}
          >
            <Box>
              <Typography variant="h6">
                {t('adaptiveNet.mechanism.title')}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {t('adaptiveNet.mechanism.description')}
              </Typography>
            </Box>
            <Stack direction="row" spacing={1}>
              <Chip
                size="small"
                label={t('adaptiveNet.mechanism.tradeCount', {
                  count: summary.total_trades,
                })}
              />
              <Chip
                size="small"
                label={t('adaptiveNet.mechanism.activeCount', {
                  count: summary.active_count,
                })}
              />
            </Stack>
          </Stack>

          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' },
              gap: 1,
            }}
          >
            <MechanismStep
              title={t('adaptiveNet.mechanism.steps.predict.title')}
              body={t('adaptiveNet.mechanism.steps.predict.body')}
            />
            <MechanismStep
              title={t('adaptiveNet.mechanism.steps.size.title')}
              body={t('adaptiveNet.mechanism.steps.size.body')}
            />
            <MechanismStep
              title={t('adaptiveNet.mechanism.steps.rebalance.title')}
              body={t('adaptiveNet.mechanism.steps.rebalance.body')}
            />
          </Box>

          {activeTrades.length > 0 && (
            <Box sx={{ display: 'grid', gap: 0.75 }}>
              <Typography variant="subtitle2">
                {t('adaptiveNet.recentOpens.title')}
              </Typography>
              {activeTrades.map((trade) => (
                <Stack
                  key={trade.id}
                  direction="row"
                  spacing={1}
                  alignItems="center"
                  justifyContent="space-between"
                  sx={{
                    py: 0.75,
                    borderBottom: '1px solid',
                    borderColor: 'divider',
                  }}
                >
                  <Chip
                    size="small"
                    color={trade.direction === 'buy' ? 'success' : 'error'}
                    label={trade.direction ?? '-'}
                  />
                  <Typography variant="body2" sx={{ flex: 1 }}>
                    {formatAppNumber(trade.units, { maximumFractionDigits: 0 })}{' '}
                    {t('adaptiveNet.recentOpens.unitsAt', {
                      price: trade.price,
                    })}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {trade.position_id?.slice(0, 8) ?? '-'}
                  </Typography>
                </Stack>
              ))}
            </Box>
          )}
        </Stack>
      </Paper>
    </Stack>
  );
}

function SummaryTile({
  label,
  value,
  caption,
  icon,
}: {
  label: string;
  value: string;
  caption: string;
  icon: ReactNode;
}) {
  return (
    <Paper variant="outlined" sx={{ p: 1.5, minHeight: 112 }}>
      <Stack spacing={1}>
        <Stack direction="row" spacing={1} alignItems="center">
          {icon}
          <Typography variant="body2" color="text.secondary">
            {label}
          </Typography>
        </Stack>
        <Typography variant="h5" sx={{ overflowWrap: 'anywhere' }}>
          {value}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {caption}
        </Typography>
      </Stack>
    </Paper>
  );
}

function SignalBar({
  label,
  value,
  absolute = false,
}: {
  label: string;
  value: number;
  absolute?: boolean;
}) {
  const display = absolute ? Math.abs(value) : value;
  const normalized = Math.min(Math.abs(display), 1) * 100;
  const color =
    value > 0 ? 'success.main' : value < 0 ? 'error.main' : 'grey.500';
  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" spacing={1}>
        <Typography variant="body2">{label}</Typography>
        <Typography variant="body2" color="text.secondary">
          {formatAppNumber(value, {
            minimumFractionDigits: 3,
            maximumFractionDigits: 3,
            signed: !absolute,
          })}
        </Typography>
      </Stack>
      <LinearProgress
        variant="determinate"
        value={normalized}
        sx={{
          mt: 0.75,
          height: 8,
          borderRadius: 1,
          bgcolor: (theme) => alpha(theme.palette.text.primary, 0.08),
          '& .MuiLinearProgress-bar': { bgcolor: color },
        }}
      />
    </Box>
  );
}

function MetricRow({ metric }: { metric: AdaptiveNetMetricSignal }) {
  const { t } = useTranslation('strategy');
  const score = toNumber(metric.direction_score);
  const confidence = toNumber(metric.confidence);
  const multiplier = toNumber(metric.size_multiplier);
  return (
    <Paper variant="outlined" sx={{ p: 1.25 }}>
      <Stack spacing={1}>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          justifyContent="space-between"
          spacing={1}
        >
          <Stack direction="row" spacing={1} alignItems="center">
            <Chip
              size="small"
              color={metricTone(score)}
              label={t(
                `adaptiveNet.metricNames.${metric.name}`,
                metric.name.replace(/_/g, ' ')
              )}
            />
            <Typography variant="caption" color="text.secondary">
              {t(`adaptiveNet.metricReasons.${metric.name}`, {
                defaultValue: metric.reason ?? '',
              })}
            </Typography>
          </Stack>
          <Stack direction="row" spacing={1}>
            <Chip
              size="small"
              variant="outlined"
              label={t('adaptiveNet.metrics.score', {
                value: formatAppNumber(score, {
                  maximumFractionDigits: 2,
                  signed: true,
                }),
              })}
            />
            <Chip
              size="small"
              variant="outlined"
              label={t('adaptiveNet.metrics.confidence', {
                value: formatAppPercent(confidence * 100, 0),
              })}
            />
            <Chip
              size="small"
              variant="outlined"
              label={t('adaptiveNet.metrics.sizeMultiplier', {
                value: formatAppNumber(multiplier, {
                  maximumFractionDigits: 2,
                }),
              })}
            />
          </Stack>
        </Stack>
      </Stack>
    </Paper>
  );
}

function MechanismStep({ title, body }: { title: string; body: string }) {
  return (
    <Box
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        p: 1.25,
        minHeight: 112,
      }}
    >
      <Typography variant="subtitle2">{title}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
        {body}
      </Typography>
    </Box>
  );
}

export default AdaptiveNetStrategyPanel;
