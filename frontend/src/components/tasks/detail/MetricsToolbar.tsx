/**
 * MetricsToolbar - Controls for metrics granularity, time range, and refresh.
 */

import { useState } from 'react';
import {
  Box,
  ToggleButton,
  ToggleButtonGroup,
  TextField,
  IconButton,
  Tooltip,
  Collapse,
  Button,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import FilterListIcon from '@mui/icons-material/FilterList';
import SettingsIcon from '@mui/icons-material/Settings';
import { useTranslation } from 'react-i18next';

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
}: MetricsToolbarProps) {
  const { t } = useTranslation('common');
  const [showRange, setShowRange] = useState(!!since || !!until);

  return (
    <Box sx={{ mb: 1.5 }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          flexWrap: 'wrap',
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
        >
          {INTERVAL_OPTIONS.map((opt) => (
            <ToggleButton
              key={opt.value}
              value={opt.value}
              sx={{ px: 1.5, py: 0.25, fontSize: '0.75rem' }}
            >
              {opt.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>

        <Tooltip title="Time range filter">
          <IconButton
            size="small"
            onClick={() => setShowRange((v) => !v)}
            color={showRange ? 'primary' : 'default'}
          >
            <FilterListIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        <Tooltip title="Refresh">
          <span>
            <IconButton size="small" onClick={onRefresh} disabled={isLoading}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>

        {onConfigureCharts ? (
          <Tooltip title={t('metrics.configureCharts', 'Chart settings')}>
            <IconButton size="small" onClick={onConfigureCharts}>
              <SettingsIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ) : null}
      </Box>

      <Collapse in={showRange}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            mt: 1,
            flexWrap: 'wrap',
          }}
        >
          <TextField
            label="From"
            type="datetime-local"
            size="small"
            value={since}
            onChange={(e) => onSinceChange(e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            sx={{ width: 220 }}
          />
          <TextField
            label="To"
            type="datetime-local"
            size="small"
            value={until}
            onChange={(e) => onUntilChange(e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            sx={{ width: 220 }}
          />
          {(since || until) && (
            <Button
              size="small"
              onClick={() => {
                onSinceChange('');
                onUntilChange('');
              }}
            >
              Clear
            </Button>
          )}
        </Box>
      </Collapse>
    </Box>
  );
}
