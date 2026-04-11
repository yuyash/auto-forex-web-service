import { Box, Chip, Stack, Tooltip, Typography, alpha } from '@mui/material';
import { useTheme, type Theme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
import type {
  StrategyGridSlotState,
  StrategyGridState,
} from '../../../../types/strategyVisualization';

interface StrategyGridIndicatorProps {
  gridState?: StrategyGridState | null;
  compact?: boolean;
  title?: string;
  showLegend?: boolean;
  showSummary?: boolean;
}

export function StrategyGridIndicator({
  gridState,
  compact = false,
  title,
  showLegend = !compact,
  showSummary = !compact,
}: StrategyGridIndicatorProps) {
  const { t } = useTranslation(['common']);
  const theme = useTheme();

  if (!gridState || gridState.layers.length === 0) {
    return null;
  }

  const cellSize = compact ? 14 : 20;
  const headerWidth = compact ? 28 : 36;
  const summary = gridState.summary;
  const slotHeaders = Array.from(
    { length: summary.slot_count_per_layer },
    (_, index) => index
  );

  const renderStateChip = (state: StrategyGridSlotState) => (
    <Chip
      key={state}
      size="small"
      label={t(`common:strategyVisualization.grid.states.${state}`)}
      sx={{
        height: compact ? 18 : 22,
        fontSize: compact ? '0.65rem' : '0.75rem',
        bgcolor: alpha(stateMainColor(theme, state), 0.14),
        color: stateMainColor(theme, state),
        borderColor: alpha(stateMainColor(theme, state), 0.28),
      }}
      variant="outlined"
    />
  );

  return (
    <Box
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        p: compact ? 1 : 1.5,
        bgcolor: compact ? 'transparent' : 'background.default',
      }}
    >
      {title ? (
        <Typography variant={compact ? 'caption' : 'subtitle2'} sx={{ mb: 1 }}>
          {title}
        </Typography>
      ) : null}

      {showLegend ? (
        <Stack direction="row" spacing={0.75} sx={{ mb: 1, flexWrap: 'wrap' }}>
          {renderStateChip('filled')}
          {renderStateChip('stopped')}
          {renderStateChip('rebuilt')}
          {renderStateChip('empty')}
        </Stack>
      ) : null}

      <Box sx={{ overflowX: 'auto' }}>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: `${headerWidth}px repeat(${slotHeaders.length}, ${cellSize}px)`,
            gap: compact ? 4 : 6,
            alignItems: 'center',
            minWidth: 'fit-content',
          }}
        >
          <Box />
          {slotHeaders.map((slot) => (
            <Typography
              key={slot}
              variant="caption"
              color="text.secondary"
              sx={{
                textAlign: 'center',
                fontSize: compact ? '0.62rem' : '0.72rem',
              }}
            >
              R{slot}
            </Typography>
          ))}

          {gridState.layers.map((layer) => (
            <GridRow
              key={layer.layer}
              cellSize={cellSize}
              compact={compact}
              headerWidth={headerWidth}
              layer={layer}
            />
          ))}
        </Box>
      </Box>

      {showSummary ? (
        <Stack direction="row" spacing={0.75} sx={{ mt: 1, flexWrap: 'wrap' }}>
          <Chip
            size="small"
            label={t('common:strategyVisualization.grid.summary.layers', {
              count: summary.layer_count,
            })}
          />
          <Chip
            size="small"
            label={t('common:strategyVisualization.grid.summary.filled', {
              count: summary.filled,
            })}
          />
          <Chip
            size="small"
            label={t('common:strategyVisualization.grid.summary.stopped', {
              count: summary.stopped,
            })}
          />
          <Chip
            size="small"
            label={t('common:strategyVisualization.grid.summary.rebuilt', {
              count: summary.rebuilt,
            })}
          />
        </Stack>
      ) : null}
    </Box>
  );
}

function GridRow({
  layer,
  compact,
  cellSize,
  headerWidth,
}: {
  layer: StrategyGridState['layers'][number];
  compact: boolean;
  cellSize: number;
  headerWidth: number;
}) {
  const { t } = useTranslation(['common']);
  const theme = useTheme();

  return (
    <>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{
          width: headerWidth,
          textAlign: 'right',
          pr: 0.5,
          fontSize: compact ? '0.62rem' : '0.72rem',
        }}
      >
        L{layer.layer}
      </Typography>
      {layer.slots.map((slot) => {
        const color = stateMainColor(theme, slot.state);
        const tooltip = `L${layer.layer}/R${slot.slot} ${t(
          `common:strategyVisualization.grid.states.${slot.state}`
        )}`;

        return (
          <Tooltip key={`${layer.layer}-${slot.slot}`} title={tooltip}>
            <Box
              sx={{
                width: cellSize,
                height: cellSize,
                borderRadius: compact ? 0.75 : 1,
                border: '1px solid',
                borderColor:
                  slot.state === 'empty'
                    ? alpha(theme.palette.grey[600], 0.35)
                    : alpha(color, 0.35),
                bgcolor:
                  slot.state === 'empty'
                    ? alpha(theme.palette.grey[500], 0.12)
                    : alpha(color, 0.24),
              }}
            />
          </Tooltip>
        );
      })}
    </>
  );
}

function stateMainColor(theme: Theme, state: StrategyGridSlotState): string {
  if (state === 'filled') return theme.palette.success.main;
  if (state === 'stopped') return theme.palette.error.main;
  if (state === 'rebuilt') return theme.palette.info.main;
  return theme.palette.grey[500];
}

export default StrategyGridIndicator;
