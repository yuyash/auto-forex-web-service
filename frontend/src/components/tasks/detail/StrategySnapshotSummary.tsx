import {
  Alert,
  Box,
  CircularProgress,
  Divider,
  Typography,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import type {
  StrategySnapshotCard,
  StrategySnapshotResponse,
} from '../../../types/strategyVisualization';

interface StrategySnapshotSummaryProps {
  snapshot: StrategySnapshotResponse | null;
  isLoading?: boolean;
  error?: Error | null;
}

export function StrategySnapshotSummary({
  snapshot,
  isLoading = false,
  error = null,
}: StrategySnapshotSummaryProps) {
  const { t } = useTranslation(['common', 'strategy']);
  const cards = snapshot?.snapshot.cards ?? [];

  if (error) {
    return (
      <Alert severity="warning" sx={{ mt: 2 }}>
        {error.message}
      </Alert>
    );
  }

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (!snapshot || cards.length === 0) {
    return null;
  }

  return (
    <Box>
      <Divider sx={{ my: 2 }} />
      <Box
        sx={{
          display: 'flex',
          alignItems: 'baseline',
          gap: 1,
          flexWrap: 'wrap',
          mb: 1.5,
        }}
      >
        <Typography variant="h6">
          {t('common:labels.strategySnapshot', 'Strategy Snapshot')}
        </Typography>
        {snapshot.snapshot.status ? (
          <Typography variant="body2" color="text.secondary">
            {snapshot.snapshot.status}
          </Typography>
        ) : null}
      </Box>
      <Box
        sx={{
          display: 'grid',
          gap: 1,
          gridTemplateColumns: {
            xs: 'repeat(2, minmax(0, 1fr))',
            sm: 'repeat(3, minmax(0, 1fr))',
            lg: 'repeat(4, minmax(0, 1fr))',
            xl: 'repeat(6, minmax(0, 1fr))',
          },
        }}
      >
        {cards.map((card) => (
          <SnapshotTile key={card.id} card={card} />
        ))}
      </Box>
    </Box>
  );
}

function SnapshotTile({ card }: { card: StrategySnapshotCard }) {
  const { t } = useTranslation(['strategy']);
  const fallbackLabel = card.id.replace(/_/g, ' ');
  const labelKey = normalizeStrategyLabelKey(card.label_key);

  return (
    <Box
      sx={{
        border: 1,
        borderColor: 'divider',
        borderRadius: 1,
        p: 1.25,
        minWidth: 0,
      }}
    >
      <Typography variant="caption" color="text.secondary" noWrap>
        {labelKey
          ? t(labelKey, { defaultValue: fallbackLabel })
          : fallbackLabel}
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 600 }} noWrap>
        {formatSnapshotValue(card.value)}
      </Typography>
    </Box>
  );
}

function normalizeStrategyLabelKey(labelKey?: string | null): string | null {
  if (!labelKey) return null;
  return labelKey.startsWith('strategy.')
    ? labelKey.slice('strategy.'.length)
    : labelKey;
}

function formatSnapshotValue(value: unknown): string {
  if (value == null || value === '') return '-';
  if (typeof value === 'number')
    return Number.isFinite(value) ? String(value) : '-';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (Array.isArray(value)) return value.length === 0 ? '-' : value.join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}
