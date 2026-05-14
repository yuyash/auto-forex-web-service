import { useState } from 'react';
import {
  Alert,
  Box,
  IconButton,
  ListItemText,
  MenuItem,
  MenuList,
  Popover,
  Switch,
  Tooltip,
  Typography,
} from '@mui/material';
import CurrencyExchangeIcon from '@mui/icons-material/CurrencyExchange';
import BarChartIcon from '@mui/icons-material/BarChart';
import TimerIcon from '@mui/icons-material/Timer';
import { useTranslation } from 'react-i18next';
import ChartOverlayControls from './ChartOverlayControls';
import type { OverlaySettings } from './chartOverlaySettings';
import type { Granularity } from '../../types/chart';

interface GranularityOption {
  value: string;
  label: string;
}

interface DashboardChartToolbarProps {
  instrument: string;
  granularity: Granularity;
  autoRefreshEnabled: boolean;
  refreshInterval: number;
  instruments: string[];
  granularities: GranularityOption[];
  intervals: Array<{ value: number; label: string }>;
  usingInstrumentFallback: boolean;
  usingGranularityFallback: boolean;
  overlays: OverlaySettings;
  onOverlaysChange: (settings: OverlaySettings) => void;
  onInstrumentChange: (value: string) => void;
  onGranularityChange: (value: string) => void;
  onAutoRefreshToggle: (checked: boolean) => void;
  onRefreshIntervalChange: (value: number) => void;
}

export default function DashboardChartToolbar({
  instrument,
  granularity,
  autoRefreshEnabled,
  refreshInterval,
  instruments,
  granularities,
  intervals,
  usingInstrumentFallback,
  usingGranularityFallback,
  overlays,
  onOverlaysChange,
  onInstrumentChange,
  onGranularityChange,
  onAutoRefreshToggle,
  onRefreshIntervalChange,
}: DashboardChartToolbarProps) {
  const { t } = useTranslation(['dashboard', 'common']);
  const [instrumentAnchor, setInstrumentAnchor] =
    useState<HTMLButtonElement | null>(null);
  const [granularityAnchor, setGranularityAnchor] =
    useState<HTMLButtonElement | null>(null);
  const [intervalAnchor, setIntervalAnchor] =
    useState<HTMLButtonElement | null>(null);

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        gap: 0.75,
        flexWrap: 'wrap',
        mb: 0.75,
        flexShrink: 0,
      }}
    >
      {usingInstrumentFallback && (
        <Alert severity="warning" sx={{ width: '100%' }}>
          {t('common:tables.trend.instrumentFallbackWarning')}
        </Alert>
      )}
      {usingGranularityFallback && (
        <Alert severity="warning" sx={{ width: '100%' }}>
          {t('common:tables.trend.granularityFallbackWarning')}
        </Alert>
      )}
      <Typography variant="subtitle2" sx={{ fontWeight: 600, mr: 'auto' }}>
        {t('dashboard:chart.title')}
      </Typography>

      <ChartOverlayControls settings={overlays} onChange={onOverlaysChange} />

      <Tooltip
        title={`${t('dashboard:chart.currencyPair')}: ${instrument.replace('_', '/')}`}
      >
        <IconButton
          size="small"
          onClick={(event) => setInstrumentAnchor(event.currentTarget)}
          aria-label={t('common:accessibility.selectInstrument')}
        >
          <CurrencyExchangeIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Popover
        open={Boolean(instrumentAnchor)}
        anchorEl={instrumentAnchor}
        onClose={() => setInstrumentAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      >
        <MenuList dense>
          {instruments.map((value) => (
            <MenuItem
              key={value}
              selected={value === instrument}
              onClick={() => {
                onInstrumentChange(value);
                setInstrumentAnchor(null);
              }}
            >
              <ListItemText>{value.replace('_', '/')}</ListItemText>
            </MenuItem>
          ))}
        </MenuList>
      </Popover>

      <Tooltip title={`${t('dashboard:chart.granularity')}: ${granularity}`}>
        <IconButton
          size="small"
          onClick={(event) => setGranularityAnchor(event.currentTarget)}
          aria-label={t('common:accessibility.selectGranularity')}
        >
          <BarChartIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Popover
        open={Boolean(granularityAnchor)}
        anchorEl={granularityAnchor}
        onClose={() => setGranularityAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      >
        <MenuList dense>
          {granularities.map((option) => (
            <MenuItem
              key={option.value}
              selected={option.value === granularity}
              onClick={() => {
                onGranularityChange(option.value);
                setGranularityAnchor(null);
              }}
            >
              <ListItemText>{option.value}</ListItemText>
            </MenuItem>
          ))}
        </MenuList>
      </Popover>

      <Switch
        size="small"
        checked={autoRefreshEnabled}
        onChange={(event) => onAutoRefreshToggle(event.target.checked)}
        inputProps={{ 'aria-label': t('common:accessibility.autoRefresh') }}
      />

      <Tooltip title={`Interval: ${refreshInterval}s`}>
        <span>
          <IconButton
            size="small"
            onClick={(event) => setIntervalAnchor(event.currentTarget)}
            disabled={!autoRefreshEnabled}
            aria-label={t('common:accessibility.selectRefreshInterval')}
          >
            <TimerIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <Popover
        open={Boolean(intervalAnchor)}
        anchorEl={intervalAnchor}
        onClose={() => setIntervalAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      >
        <MenuList dense>
          {intervals.map(({ value, label }) => (
            <MenuItem
              key={value}
              selected={value === refreshInterval}
              onClick={() => {
                onRefreshIntervalChange(value);
                setIntervalAnchor(null);
              }}
            >
              <ListItemText>{label}</ListItemText>
            </MenuItem>
          ))}
        </MenuList>
      </Popover>
    </Box>
  );
}
