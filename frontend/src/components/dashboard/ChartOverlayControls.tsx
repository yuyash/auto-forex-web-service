/**
 * ChartOverlayControls — toggle panel for chart indicators and decorations.
 */
import { useState } from 'react';
import {
  Box,
  IconButton,
  Popover,
  FormGroup,
  FormControlLabel,
  Checkbox,
  Typography,
  Divider,
  Tooltip,
} from '@mui/material';
import TuneIcon from '@mui/icons-material/Tune';
import { useTranslation } from 'react-i18next';
import type { OverlaySettings } from './chartOverlaySettings';

interface Props {
  settings: OverlaySettings;
  onChange: (settings: OverlaySettings) => void;
}

export default function ChartOverlayControls({ settings, onChange }: Props) {
  const { t } = useTranslation('dashboard');
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);
  const open = Boolean(anchorEl);

  const toggle = (key: keyof OverlaySettings) => {
    onChange({ ...settings, [key]: !settings[key] });
  };

  return (
    <>
      <Tooltip title={t('overlays.chartOverlays')}>
        <IconButton
          size="small"
          onClick={(e) => setAnchorEl(e.currentTarget)}
          aria-label={t('overlays.chartOverlays')}
        >
          <TuneIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
      >
        <Box sx={{ p: 1.5, minWidth: 180 }}>
          <Typography
            variant="caption"
            sx={{ mb: 0.5, fontWeight: 600, display: 'block' }}
          >
            Indicators
          </Typography>
          <FormGroup sx={{ gap: 0 }}>
            <FormControlLabel
              sx={{ m: 0, py: 0 }}
              control={
                <Checkbox
                  size="small"
                  sx={{ p: 0.25 }}
                  checked={settings.sma20}
                  onChange={() => toggle('sma20')}
                />
              }
              label={t('overlays.sma20')}
            />
            <FormControlLabel
              sx={{ m: 0, py: 0 }}
              control={
                <Checkbox
                  size="small"
                  sx={{ p: 0.25 }}
                  checked={settings.sma50}
                  onChange={() => toggle('sma50')}
                />
              }
              label={t('overlays.sma50')}
            />
            <FormControlLabel
              sx={{ m: 0, py: 0 }}
              control={
                <Checkbox
                  size="small"
                  sx={{ p: 0.25 }}
                  checked={settings.ema12}
                  onChange={() => toggle('ema12')}
                />
              }
              label={t('overlays.ema12')}
            />
            <FormControlLabel
              sx={{ m: 0, py: 0 }}
              control={
                <Checkbox
                  size="small"
                  sx={{ p: 0.25 }}
                  checked={settings.ema26}
                  onChange={() => toggle('ema26')}
                />
              }
              label={t('overlays.ema26')}
            />
            <FormControlLabel
              sx={{ m: 0, py: 0 }}
              control={
                <Checkbox
                  size="small"
                  sx={{ p: 0.25 }}
                  checked={settings.bollinger}
                  onChange={() => toggle('bollinger')}
                />
              }
              label={t('overlays.bollingerBands')}
            />
            <FormControlLabel
              sx={{ m: 0, py: 0 }}
              control={
                <Checkbox
                  size="small"
                  sx={{ p: 0.25 }}
                  checked={settings.volume}
                  onChange={() => toggle('volume')}
                />
              }
              label={t('overlays.volume')}
            />
          </FormGroup>
          <Divider sx={{ my: 0.5 }} />
          <Typography
            variant="caption"
            sx={{ mb: 0.5, fontWeight: 600, display: 'block' }}
          >
            Annotations
          </Typography>
          <FormGroup sx={{ gap: 0 }}>
            <FormControlLabel
              sx={{ m: 0, py: 0 }}
              control={
                <Checkbox
                  size="small"
                  sx={{ p: 0.25 }}
                  checked={settings.supportResistance}
                  onChange={() => toggle('supportResistance')}
                />
              }
              label={t('overlays.supportResistance')}
            />
            <FormControlLabel
              sx={{ m: 0, py: 0 }}
              control={
                <Checkbox
                  size="small"
                  sx={{ p: 0.25 }}
                  checked={settings.markers}
                  onChange={() => toggle('markers')}
                />
              }
              label={t('overlays.signalMarkers')}
            />
          </FormGroup>
        </Box>
      </Popover>
    </>
  );
}
