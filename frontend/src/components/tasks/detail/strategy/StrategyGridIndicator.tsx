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
  showSlotBuildCounts?: boolean;
  slotBuildCounts?: Record<string, number>;
}

export function StrategyGridIndicator({
  gridState,
  compact = false,
  title,
  showLegend = !compact,
  showSummary = !compact,
  showSlotBuildCounts = false,
  slotBuildCounts,
}: StrategyGridIndicatorProps) {
  const { t } = useTranslation(['common']);
  const theme = useTheme();

  if (!gridState || gridState.layers.length === 0) {
    return null;
  }

  const cellHeight = compact ? 14 : 20;
  const cellWidth = compact ? 14 : showSlotBuildCounts ? 36 : 20;
  const headerWidth = cellHeight;
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
        p: compact ? 0.5 : 1,
        bgcolor: compact ? 'transparent' : 'background.default',
      }}
    >
      {title ? (
        <Typography
          variant={compact ? 'caption' : 'subtitle2'}
          sx={{ mb: 0.5 }}
        >
          {title}
        </Typography>
      ) : null}

      {showLegend ? (
        <Stack direction="row" spacing={0.5} sx={{ mb: 0.5, flexWrap: 'wrap' }}>
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
            gridTemplateColumns: `${headerWidth}px repeat(${slotHeaders.length}, ${cellWidth}px)`,
            gap: '4px',
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
                lineHeight: 1,
              }}
            >
              R{slot}
            </Typography>
          ))}

          {gridState.layers.map((layer) => (
            <GridRow
              key={layer.layer}
              cellHeight={cellHeight}
              cellWidth={cellWidth}
              compact={compact}
              headerWidth={headerWidth}
              layer={layer}
              showSlotBuildCounts={showSlotBuildCounts}
              slotBuildCounts={slotBuildCounts}
            />
          ))}
        </Box>
      </Box>

      {showSummary ? (
        <Stack direction="row" spacing={0.5} sx={{ mt: 0.5, flexWrap: 'wrap' }}>
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
  cellHeight,
  cellWidth,
  headerWidth,
  showSlotBuildCounts,
  slotBuildCounts,
}: {
  layer: StrategyGridState['layers'][number];
  compact: boolean;
  cellHeight: number;
  cellWidth: number;
  headerWidth: number;
  showSlotBuildCounts: boolean;
  slotBuildCounts?: Record<string, number>;
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
          textAlign: 'center',
          fontSize: compact ? '0.62rem' : '0.72rem',
          lineHeight: 1,
        }}
      >
        L{layer.layer}
      </Typography>
      {layer.slots.map((slot) => {
        const color = stateMainColor(theme, slot.state);
        const buildCount = Math.min(
          slotBuildCounts?.[getSlotBuildCountKey(layer.layer, slot.slot)] ?? 0,
          999
        );
        const tooltip = `L${layer.layer}/R${slot.slot} ${t(
          `common:strategyVisualization.grid.states.${slot.state}`
        )}`;

        return (
          <Tooltip key={`${layer.layer}-${slot.slot}`} title={tooltip}>
            <Box
              sx={{
                width: cellWidth,
                height: cellHeight,
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
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {showSlotBuildCounts ? (
                <Typography
                  component="span"
                  sx={{
                    fontSize: compact ? '0.55rem' : '0.72rem',
                    fontWeight: 700,
                    lineHeight: 1,
                    color:
                      slot.state === 'empty'
                        ? theme.palette.text.secondary
                        : color,
                  }}
                >
                  {buildCount}
                </Typography>
              ) : null}
            </Box>
          </Tooltip>
        );
      })}
    </>
  );
}

function stateMainColor(theme: Theme, state: StrategyGridSlotState): string {
  if (state === 'filled') return theme.palette.success.main;
  if (state === 'stopped') return theme.palette.error.main;
  if (state === 'rebuilt') return theme.palette.warning.main;
  return theme.palette.grey[500];
}

function getSlotBuildCountKey(layer: number, slot: number): string {
  return `${layer}:${slot}`;
}

export default StrategyGridIndicator;
