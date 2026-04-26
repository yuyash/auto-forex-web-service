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
import { LineChart } from '@mui/x-charts/LineChart';
import type { ReactNode } from 'react';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import type {
  AdaptiveNetMetricSignal,
  AdaptiveNetDecisionHistoryPoint,
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

function formatDuration(seconds?: number | null): string {
  if (seconds == null || !Number.isFinite(seconds)) return '-';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return remainingSeconds > 0
    ? `${minutes}m ${remainingSeconds}s`
    : `${minutes}m`;
}

function directionIcon(units?: number) {
  if (!units) return <SwapHorizIcon fontSize="small" />;
  return units > 0 ? (
    <TrendingUpIcon fontSize="small" />
  ) : (
    <TrendingDownIcon fontSize="small" />
  );
}

function decisionAction(
  currentNet: number,
  targetNet: number,
  orderUnits: number
) {
  if (orderUnits === 0) return 'hold';
  if (
    currentNet !== 0 &&
    Math.sign(currentNet) !== Math.sign(targetNet) &&
    targetNet !== 0
  ) {
    return 'reverse';
  }
  if (Math.abs(targetNet) > Math.abs(currentNet)) return 'increase';
  return 'reduce';
}

function metricTone(score: number): 'success' | 'error' | 'default' {
  if (score > 0.05) return 'success';
  if (score < -0.05) return 'error';
  return 'default';
}

function buildFallbackHistory(
  decision: AdaptiveNetStrategyState['latest_decision'],
  metrics: AdaptiveNetMetricSignal[],
  currentNet: number,
  targetNet: number,
  orderUnits: number,
  action: string
): AdaptiveNetDecisionHistoryPoint[] {
  if (!decision) return [];
  return [
    {
      timestamp: new Date().toISOString(),
      current_net_units: currentNet,
      target_net_units: targetNet,
      order_units: orderUnits,
      action,
      edge: decision.edge,
      confidence: decision.confidence,
      probability_long: decision.probability_long,
      probability_short: decision.probability_short,
      risk_multiplier: decision.risk_multiplier,
      metric_signals: decision.metric_signals?.length
        ? decision.metric_signals
        : metrics,
    },
  ];
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
  const action = decisionAction(currentNet, targetNet, orderUnits);
  const history =
    state?.decision_history && state.decision_history.length > 0
      ? state.decision_history
      : buildFallbackHistory(
          decision,
          metrics,
          currentNet,
          targetNet,
          orderUnits,
          action
        );
  void cycles;
  void summary;
  const directionLabel = (units?: number): string => {
    if (!units) return t('adaptiveNet.directions.flat');
    return units > 0
      ? t('adaptiveNet.directions.netLong')
      : t('adaptiveNet.directions.netShort');
  };

  return (
    <Stack spacing={2}>
      {!state && <Alert severity="info">{t('adaptiveNet.noState')}</Alert>}

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
              label={t('adaptiveNet.metrics.window', {
                count: state?.lookback_points ?? 0,
                duration: formatDuration(state?.window_seconds),
              })}
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
          <MetricHistoryCharts history={history} />
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
                {t('adaptiveNet.prediction.title')}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {t('adaptiveNet.prediction.description')}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {t('adaptiveNet.prediction.directionalEdgeHelp')}
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
          <PredictionHistoryChart history={history} />
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
                {t('adaptiveNet.decision.title')}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {t('adaptiveNet.decision.description')}
              </Typography>
            </Box>
            <Chip
              size="small"
              color={
                action === 'increase'
                  ? 'success'
                  : action === 'reduce'
                    ? 'warning'
                    : action === 'reverse'
                      ? 'error'
                      : 'default'
              }
              label={t(`adaptiveNet.decision.actions.${action}`)}
            />
          </Stack>

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
              icon={directionIcon(targetNet)}
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
              label={t('adaptiveNet.decision.elapsed')}
              value={formatDuration(state?.rebalance_elapsed_seconds)}
              caption={t('adaptiveNet.decision.ticks', {
                count: state?.rebalance_tick_delta ?? 0,
              })}
              icon={<SwapHorizIcon fontSize="small" />}
            />
          </Box>
          <DecisionHistoryChart history={history} />
        </Stack>
      </Paper>
    </Stack>
  );
}

function formatHistoryTime(value: string): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return value;
  return date.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function chartIndexes(history: AdaptiveNetDecisionHistoryPoint[]): number[] {
  return history.map((_, index) => index);
}

function NoHistoryFallback() {
  const { t } = useTranslation('strategy');
  return (
    <Typography variant="body2" color="text.secondary">
      {t('adaptiveNet.charts.noHistory')}
    </Typography>
  );
}

function MetricHistoryCharts({
  history,
}: {
  history: AdaptiveNetDecisionHistoryPoint[];
}) {
  const { t } = useTranslation('strategy');
  if (history.length < 2) return <NoHistoryFallback />;

  const metricNames = Array.from(
    new Set(
      history.flatMap((point) =>
        (point.metric_signals ?? []).map((metric) => metric.name)
      )
    )
  );
  const indexes = chartIndexes(history);

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' },
        gap: 2,
      }}
    >
      <HistoryLineChart
        title={t('adaptiveNet.charts.metricScores')}
        history={history}
        indexes={indexes}
        min={-1}
        max={1}
        series={metricNames.map((name) => ({
          label: t(`adaptiveNet.metricNames.${name}`, name.replace(/_/g, ' ')),
          data: history.map((point) =>
            toNumber(
              point.metric_signals.find((metric) => metric.name === name)
                ?.direction_score
            )
          ),
        }))}
      />
      <HistoryLineChart
        title={t('adaptiveNet.charts.metricConfidence')}
        history={history}
        indexes={indexes}
        min={0}
        max={1}
        series={metricNames.map((name) => ({
          label: t(`adaptiveNet.metricNames.${name}`, name.replace(/_/g, ' ')),
          data: history.map((point) =>
            toNumber(
              point.metric_signals.find((metric) => metric.name === name)
                ?.confidence
            )
          ),
        }))}
      />
    </Box>
  );
}

function PredictionHistoryChart({
  history,
}: {
  history: AdaptiveNetDecisionHistoryPoint[];
}) {
  const { t } = useTranslation('strategy');
  if (history.length < 2) return <NoHistoryFallback />;
  const indexes = chartIndexes(history);
  return (
    <HistoryLineChart
      title={t('adaptiveNet.charts.prediction')}
      history={history}
      indexes={indexes}
      min={-1}
      max={1}
      series={[
        {
          label: t('adaptiveNet.prediction.directionalEdge'),
          data: history.map((point) => toNumber(point.edge)),
        },
        {
          label: t('adaptiveNet.prediction.decisionConfidence'),
          data: history.map((point) => toNumber(point.confidence)),
        },
      ]}
    />
  );
}

function DecisionHistoryChart({
  history,
}: {
  history: AdaptiveNetDecisionHistoryPoint[];
}) {
  const { t } = useTranslation('strategy');
  if (history.length < 2) return <NoHistoryFallback />;
  const indexes = chartIndexes(history);
  return (
    <HistoryLineChart
      title={t('adaptiveNet.charts.decision')}
      history={history}
      indexes={indexes}
      series={[
        {
          label: t('adaptiveNet.summary.currentNet'),
          data: history.map((point) => Number(point.current_net_units ?? 0)),
        },
        {
          label: t('adaptiveNet.summary.targetNet'),
          data: history.map((point) => Number(point.target_net_units ?? 0)),
        },
        {
          label: t('adaptiveNet.summary.nextOrder'),
          data: history.map((point) => Number(point.order_units ?? 0)),
        },
      ]}
    />
  );
}

function HistoryLineChart({
  title,
  history,
  indexes,
  series,
  min,
  max,
}: {
  title: string;
  history: AdaptiveNetDecisionHistoryPoint[];
  indexes: number[];
  series: Array<{ label: string; data: number[] }>;
  min?: number;
  max?: number;
}) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        {title}
      </Typography>
      <LineChart
        height={220}
        xAxis={[
          {
            data: indexes,
            valueFormatter: (value: number) =>
              formatHistoryTime(history[Number(value)]?.timestamp ?? ''),
          },
        ]}
        yAxis={[{ min, max }]}
        series={series.map((item) => ({
          ...item,
          showMark: false,
        }))}
        margin={{ top: 24, right: 16, bottom: 24, left: 48 }}
      />
    </Box>
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

export default AdaptiveNetStrategyPanel;
