/**
 * MetricsToolbar - Controls for metrics granularity, time range, and refresh.
 */

import { useState } from 'react';
import {
  Box,
  ToggleButton,
  ToggleButtonGroup,
  IconButton,
  Tooltip,
  Collapse,
  Button,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import FilterListIcon from '@mui/icons-material/FilterList';
import SettingsIcon from '@mui/icons-material/Settings';
import { useTranslation } from 'react-i18next';
import { DateRangeFilter } from '../../common/DateRangeFilter';
import { TableFilterBar } from '../../common/TableFilterBar';
import { tableFilterDateRangeSx } from '../../common/tableFilterLayout';

const INTERVAL_OPTIONS = [
  { value: 0, label: 'Auto' },
  { value: 1, label: '1m' },
  { value: 5, label: '5m' },
  { value: 15, label: '15m' },
  { value: 60, label: '1h' },
  { value: 240, label: '4h' },
  { value: 1440, label: '1d' },
] as const;

export interface MetricsToolbarProps {
  interval: number;
  since: string;
  until: string;
  onIntervalChange: (interval: number) => void;
  onSinceChange: (since: string) => void;
  onUntilChange: (until: string) => void;
  onRefresh: () => void | Promise<void>;
  onConfigureCharts?: () => void;
  isLoading?: boolean;
  /**
   * If provided, renders a loss-cut overlay toggle in the toolbar.
   * Leaving either prop undefined hides the control entirely.
   */
  showLossCutMarkers?: boolean;
  onToggleLossCutMarkers?: (next: boolean) => void;
  lossCutMarkerCount?: number;
}

export function MetricsToolbar({
  interval,
  since,
  until,
  onIntervalChange,
  onSinceChange,
  onUntilChange,
  onRefresh,
  onConfigureCharts,
  isLoading,
  showLossCutMarkers,
  onToggleLossCutMarkers,
  lossCutMarkerCount,
}: MetricsToolbarProps) {
  const { t } = useTranslation('common');
  const [showRange, setShowRange] = useState(!!since || !!until);

  return (
    <Box sx={{ mb: { xs: 0.75, sm: 1.5 } }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: { xs: 'stretch', sm: 'center' },
          gap: 1,
          flexWrap: 'wrap',
          p: 0,
        }}
      >
        <ToggleButtonGroup
          value={interval}
          exclusive
          onChange={(_e, val) => {
            if (val !== null) onIntervalChange(val);
          }}
          size="small"
          aria-label="Granularity"
          sx={{
            flex: { xs: '1 1 100%', sm: '0 1 auto' },
            display: 'flex',
            minWidth: 0,
            '& .MuiToggleButtonGroup-grouped': {
              flex: { xs: 1, sm: '0 0 auto' },
              minWidth: 0,
            },
          }}
        >
          {INTERVAL_OPTIONS.map((opt) => (
            <ToggleButton
              key={opt.value}
              value={opt.value}
              sx={{
                px: { xs: 0.75, sm: 1.5 },
                py: 0.25,
                fontSize: '0.75rem',
                whiteSpace: 'nowrap',
              }}
            >
              {opt.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>

        <Box
          sx={{
            display: 'flex',
            gap: 0.5,
            alignItems: 'center',
            justifyContent: { xs: 'flex-end', sm: 'flex-start' },
            flex: { xs: '1 1 100%', sm: '0 0 auto' },
          }}
        >
          <Tooltip title="Time range filter">
            <IconButton
              size="small"
              onClick={() => setShowRange((v) => !v)}
              color={showRange ? 'primary' : 'default'}
            >
              <FilterListIcon fontSize="small" />
            </IconButton>
          </Tooltip>

          <Tooltip title={t('metrics.refreshAllCharts', 'Refresh all charts')}>
            <span>
              <IconButton
                size="small"
                onClick={() => {
                  void onRefresh();
                }}
                disabled={isLoading}
                aria-label={t('metrics.refreshAllCharts', 'Refresh all charts')}
              >
                <RefreshIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>

          {onToggleLossCutMarkers != null ? (
            <Tooltip
              title={t('metrics.toggleLossCutMarkers', 'Show loss-cut markers')}
            >
              <ToggleButton
                size="small"
                value="loss-cut"
                selected={Boolean(showLossCutMarkers)}
                onChange={() => onToggleLossCutMarkers(!showLossCutMarkers)}
                sx={{
                  px: 1,
                  py: 0.25,
                  fontSize: '0.7rem',
                  lineHeight: 1.1,
                  whiteSpace: 'nowrap',
                  border: '1px solid',
                  borderColor: 'divider',
                }}
                aria-label={t(
                  'metrics.toggleLossCutMarkers',
                  'Show loss-cut markers'
                )}
              >
                {t('metrics.lossCut', 'Loss-cut')}
                {lossCutMarkerCount != null && lossCutMarkerCount > 0
                  ? ` (${lossCutMarkerCount})`
                  : ''}
              </ToggleButton>
            </Tooltip>
          ) : null}

          {onConfigureCharts ? (
            <Tooltip title={t('metrics.configureCharts', 'Chart settings')}>
              <IconButton size="small" onClick={onConfigureCharts}>
                <SettingsIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          ) : null}
        </Box>
      </Box>

      <Collapse in={showRange}>
        <TableFilterBar sx={{ mt: 1 }}>
          <DateRangeFilter
            from={since}
            to={until}
            onFromChange={onSinceChange}
            onToChange={onUntilChange}
            fromLabel="From"
            toLabel="To"
            sx={tableFilterDateRangeSx}
            fieldSx={{ width: { xs: '100%', sm: 220 } }}
          />
          {(since || until) && (
            <Button
              size="small"
              sx={{ alignSelf: { xs: 'stretch', sm: 'center' } }}
              onClick={() => {
                onSinceChange('');
                onUntilChange('');
              }}
            >
              Clear
            </Button>
          )}
        </TableFilterBar>
      </Collapse>
    </Box>
  );
}
