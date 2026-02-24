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

export interface OverlaySettings {
  sma20: boolean;
  sma50: boolean;
  ema12: boolean;
  ema26: boolean;
  bollinger: boolean;
  volume: boolean;
  supportResistance: boolean;
  markers: boolean;
}

export const DEFAULT_OVERLAY_SETTINGS: OverlaySettings = {
  sma20: true,
  sma50: false,
  ema12: false,
  ema26: false,
  bollinger: true,
  volume: true,
  supportResistance: false,
  markers: true,
};

interface Props {
  settings: OverlaySettings;
  onChange: (settings: OverlaySettings) => void;
}

export default function ChartOverlayControls({ settings, onChange }: Props) {
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);
  const open = Boolean(anchorEl);

  const toggle = (key: keyof OverlaySettings) => {
    onChange({ ...settings, [key]: !settings[key] });
  };

  return (
    <>
      <Tooltip title="Chart overlays">
        <IconButton
          size="small"
          onClick={(e) => setAnchorEl(e.currentTarget)}
          aria-label="Toggle chart overlays"
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
              label="SMA 20"
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
              label="SMA 50"
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
              label="EMA 12"
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
              label="EMA 26"
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
              label="Bollinger Bands"
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
              label="Volume"
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
              label="Support / Resistance"
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
              label="Signal Markers"
            />
          </FormGroup>
        </Box>
      </Popover>
    </>
  );
}
